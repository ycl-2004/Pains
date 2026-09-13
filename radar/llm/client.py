"""Model access with ordered fallback, spend accounting and conservative soft-budget admission.

Fallback strategy for every stage:
1. Consecutive OpenRouter models that share an output mode go out as ONE request with `models=[...]`.
   OpenRouter itself moves to the next model on provider errors, rate limits, downtime, context-length
   and moderation failures.
2. Output mode is picked per model from OpenRouter's public catalog: models with `structured_outputs`
   get strict `json_schema`; the rest get `json_object` with the schema written into the prompt.
3. OpenRouter does not fall back on bad output, so we do: a truncated answer, non-JSON, or a schema
   validation failure moves on to the next route group.
4. Direct-provider routes such as `deepseek:deepseek-flash` are their own request, usually last in the chain.
5. Running out of budget stops the stage immediately; it never triggers a fallback.
"""

import itertools
import json
import os
import re
import hashlib
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeVar

import openai
import pydantic
from pydantic import BaseModel

from radar import config
from radar.models import UsageRecord

PROMPTS_DIR = Path(__file__).parent / "prompts"

OutputMode = Literal["json_schema", "json_object"]


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_env: str
    output_mode: OutputMode
    # Accepts OpenRouter's extensions: `models` fallback list, `provider` routing, `plugins` (web, healing),
    # and a model catalog that lists each model's `supported_parameters`.
    openrouter_api: bool


PROVIDERS: dict[str, Provider] = {
    "openrouter": Provider("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "json_schema", True),
    "deepseek": Provider("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY", "json_object", False),
}
DEFAULT_PROVIDER = PROVIDERS["openrouter"]

# USD per 1M (input, output) tokens for providers that do not report cost in the response.
# DeepSeek peak-hour cache-miss rates from its pricing page (2026-09): deliberately conservative.
LIST_PRICES: dict[str, tuple[float, float]] = {
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
}
UNKNOWN_PRICE = (5.0, 25.0)

T = TypeVar("T", bound=BaseModel)


class BudgetExceeded(RuntimeError):
    pass


class StageFailed(RuntimeError):
    """Every route for a stage failed to produce usable output."""


@dataclass(frozen=True)
class RouteGroup:
    provider: Provider
    models: tuple[str, ...]
    output_mode: OutputMode

    @property
    def label(self) -> str:
        return f"{self.provider.name}:{' > '.join(self.models)}"


def parse_routes(entries: Iterable[str]) -> list[RouteGroup]:
    """`vendor/model` means OpenRouter; `deepseek:model` means that provider's own API.

    OpenRouter slugs may carry suffixes such as `:free`, so only a known provider name counts as a prefix.
    """
    groups: list[RouteGroup] = []
    for entry in entries:
        prefix, separator, rest = entry.partition(":")
        if separator and rest and prefix in PROVIDERS:
            provider, model = PROVIDERS[prefix], rest
        else:
            provider, model = DEFAULT_PROVIDER, entry
        if groups and groups[-1].provider is provider and provider.openrouter_api:
            groups[-1] = RouteGroup(provider, groups[-1].models + (model,), provider.output_mode)
        else:
            groups.append(RouteGroup(provider, (model,), provider.output_mode))
    return groups


def strict_schema(model: type[BaseModel]) -> dict:
    """JSON Schema for strict structured output: closed objects, every property required, no defaults."""

    def tighten(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
                for child in node["properties"].values():
                    tighten(child)
            node.pop("default", None)
            for key, value in node.items():
                if key != "properties":
                    tighten(value)
        elif isinstance(node, list):
            for value in node:
                tighten(value)
        return node

    return tighten(model.model_json_schema())


def llm_problem(env: Mapping[str, str] = os.environ) -> str | None:
    """Why a full run cannot start, or None when models and at least one needed key are configured."""
    if not config.TRIAGE_MODELS or not config.ANALYZE_MODELS:
        return "没有配置模型：请设置 RADAR_TRIAGE_MODELS 和 RADAR_ANALYZE_MODELS（逗号分隔，按优先级排列）"
    chain = config.TRIAGE_MODELS + config.ANALYZE_MODELS + config.FALLBACK_MODELS
    key_names = sorted({group.provider.key_env for group in parse_routes(chain)})
    if not any(env.get(name) for name in key_names):
        return f"没有模型凭据：请设置 {' 或 '.join(key_names)}"
    return None


def load_prompt(name: str, **values: str) -> str:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"{{{key}}}", value)
    return text


class Budget:
    def __init__(self, max_cost_usd: float) -> None:
        if not math.isfinite(max_cost_usd) or max_cost_usd < 0:
            raise ValueError("Budget must be finite and nonnegative")
        self.max_cost_usd = max_cost_usd
        self.records: list[UsageRecord] = []

    @property
    def spent(self) -> float:
        return sum(record.cost_usd for record in self.records)

    def ensure_room(self, stage: str) -> None:
        if self.spent >= self.max_cost_usd:
            raise BudgetExceeded(f"{stage} 前已花费 ${self.spent:.2f}，达到上限 ${self.max_cost_usd:.2f}")

    def record(self, stage: str, provider: Provider, model: str, usage, *, web_search: bool) -> UsageRecord:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        details = getattr(usage, "prompt_tokens_details", None)
        cost = getattr(usage, "cost", None)  # OpenRouter reports the actual charge on every response
        if cost is None:
            input_price, output_price = LIST_PRICES.get(model, UNKNOWN_PRICE)
            cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
        record = UsageRecord(
            stage=stage,
            provider=provider.name,
            model=model,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cache_read_input_tokens=(getattr(details, "cached_tokens", 0) or 0) if details else 0,
            cache_creation_input_tokens=(getattr(details, "cache_write_tokens", 0) or 0) if details else 0,
            web_search_requests=1 if web_search else 0,
            cost_usd=round(float(cost), 6),
        )
        self.records.append(record)
        return record


class LLM:
    """The only way stages reach a model, so fallback and accounting behave the same everywhere."""

    def __init__(self, budget: Budget, *, clients: Mapping[str, object] | None = None,
                 env: Mapping[str, str] = os.environ, cache_dir: Path | None = None) -> None:
        self.budget = budget
        self.notes: list[str] = []
        self._clients: dict[str, object | None] = dict(clients or {})
        self._catalogs: dict[str, dict[str, frozenset[str]]] = {}
        self._env = env
        self.cache_dir = cache_dir
        self._prices: dict[str, tuple[float, float]] = {}
        self._last_cache: Path | None = None

    def discard_last_cache(self):
        if self._last_cache and self._last_cache.exists():
            self._last_cache.replace(self._last_cache.with_suffix(".invalid.json"))

    def complete(self, stage: str, *, system: str, user: str, schema: type[T], routes: Iterable[str],
                 max_tokens: int, web_search: bool = False) -> T:
        from radar.privacy import redact
        system, user = redact(system), redact(user)
        routes = tuple(routes)
        digest = hashlib.sha256(json.dumps([stage, system, user, strict_schema(schema), routes, max_tokens,
                                            web_search], ensure_ascii=False).encode()).hexdigest()
        cache = self.cache_dir / f"{digest}.json" if self.cache_dir else None
        self._last_cache = cache
        if cache and cache.exists():
            saved = json.loads(cache.read_text())
            self.notes.append(f"{stage} 复用已完成调用（本次无新增费用）")
            return schema.model_validate(saved["output"])
        failures: list[str] = []
        for group in self._resolve_output_modes(parse_routes(routes)):
            if web_search and not group.provider.openrouter_api:
                failures.append(f"{group.label} 不支持联网搜索")
                continue
            client = self._client(group.provider)
            if client is None:
                failures.append(f"{group.label} 缺少 {group.provider.key_env}")
                continue
            self.budget.ensure_room(stage)
            request = self._request(group, system, user, schema, max_tokens, web_search)
            # Conservative admission estimate; provider-side caps are still required for a hard billing limit.
            prices = [self._prices.get(model, LIST_PRICES.get(model, UNKNOWN_PRICE)) for model in group.models]
            input_price = max(p[0] for p in prices)
            output_price = max(p[1] for p in prices)
            input_estimate = len(json.dumps(request, ensure_ascii=False).encode()) * input_price / 1_000_000
            room = self.budget.max_cost_usd - self.budget.spent - input_estimate - (0.10 if web_search else 0)
            allowed = min(max_tokens, int(room * 1_000_000 / output_price)) if output_price else max_tokens
            if room < 0 or allowed < min(256, max_tokens):
                failures.append(f"{group.label} 预计费用超过剩余预算")
                continue
            request["max_tokens"] = allowed
            try:
                response = client.chat.completions.create(**request)
            except openai.APIError as error:
                failures.append(f"{group.label} 调用失败（{describe_error(error)}）")
                continue

            served = response.model or group.models[0]
            self.budget.record(stage, group.provider, served, response.usage, web_search=web_search)
            if self.budget.spent > self.budget.max_cost_usd:
                self.notes.append("实际费用超过软预算；已停止后续调用。请在服务商设置硬额度。")
            choice = response.choices[0] if response.choices else None
            if choice is None or choice.finish_reason == "length":
                failures.append(f"{served} 输出为空或被截断")
                continue
            try:
                result = schema.model_validate_json(_extract_json(choice.message.content))
            except pydantic.ValidationError as error:
                failures.append(f"{served} 输出不符合结构（{error.error_count()} 处错误）")
                continue
            if web_search and hasattr(result, "sources"):
                # Official contract: https://openrouter.ai/docs/guides/features/plugins/web-search
                from radar.evidence import canonical_url
                cited = set()
                for annotation in getattr(choice.message, "annotations", None) or []:
                    value = annotation if isinstance(annotation, dict) else annotation.model_dump()
                    url = (value.get("url_citation") or {}).get("url")
                    if url:
                        try:
                            cited.add(canonical_url(url))
                        except ValueError:
                            pass
                try:
                    grounded = bool(result.sources) and all(canonical_url(s.url) in cited for s in result.sources)
                except ValueError:
                    grounded = False
                if not grounded:
                    failures.append(f"{served} 方案来源未匹配搜索返回的引用")
                    continue
            if failures:
                self.notes.append(f"{stage} 降级到 {served}：{'；'.join(failures)}")
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                temporary = cache.with_suffix(".tmp")
                temporary.write_text(json.dumps({"stage": stage, "model": served, "system": system, "input": user,
                                                  "output": result.model_dump(mode="json"),
                                                  "usage": self.budget.records[-1].model_dump()}, ensure_ascii=False))
                temporary.replace(cache)
            return result
        raise StageFailed(f"{stage} 的所有模型都失败：{'；'.join(failures) or '没有配置模型'}")

    def _resolve_output_modes(self, groups: list[RouteGroup]) -> list[RouteGroup]:
        """Split OpenRouter groups where adjacent models need different output modes, keeping chain order."""
        resolved: list[RouteGroup] = []
        for group in groups:
            if not group.provider.openrouter_api:
                resolved.append(group)
                continue
            for mode, models in itertools.groupby(group.models, key=lambda model: self._output_mode(group.provider, model)):
                resolved.append(RouteGroup(group.provider, tuple(models), mode))
        return resolved

    def _output_mode(self, provider: Provider, model: str) -> OutputMode:
        catalog = self._catalog(provider)
        parameters = catalog.get(model, catalog.get(model.partition(":")[0]))
        if parameters is None:
            return provider.output_mode  # not in the catalog: let the provider accept or reject strict mode
        return "json_schema" if "structured_outputs" in parameters else "json_object"

    def _catalog(self, provider: Provider) -> dict[str, frozenset[str]]:
        if provider.name not in self._catalogs:
            client = self._client(provider)
            catalog: dict[str, frozenset[str]] = {}
            if client is not None:
                try:
                    for item in client.models.list():
                        catalog[item.id] = frozenset(getattr(item, "supported_parameters", None) or ())
                        pricing = getattr(item, "pricing", None)
                        if isinstance(pricing, dict):
                            try:
                                price = (float(pricing["prompt"]) * 1_000_000, float(pricing["completion"]) * 1_000_000)
                                if all(math.isfinite(p) and p >= 0 for p in price):
                                    self._prices[item.id] = price
                            except (ValueError, KeyError, TypeError):
                                pass
                except openai.APIError as error:
                    self.notes.append(f"读取 {provider.name} 模型目录失败（{describe_error(error)}），全部按严格结构化输出请求")
            self._catalogs[provider.name] = catalog
        return self._catalogs[provider.name]

    def _client(self, provider: Provider):
        if provider.name not in self._clients:
            key = self._env.get(provider.key_env)
            self._clients[provider.name] = (
                openai.OpenAI(api_key=key, base_url=provider.base_url, timeout=180, max_retries=0) if key else None
            )
        return self._clients[provider.name]

    def _request(self, group: RouteGroup, system: str, user: str, schema: type[BaseModel], max_tokens: int,
                 web_search: bool) -> dict:
        request = {"model": group.models[0], "max_tokens": max_tokens}
        if group.output_mode == "json_schema":
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "strict": True, "schema": strict_schema(schema)},
            }
        else:
            # JSON mode only guarantees syntax, so the schema travels in the prompt and validation stays client-side.
            system = (f"{system}\n\n只输出一个 JSON 对象（json），不要输出其他文字。它必须符合下面的 JSON Schema：\n"
                      f"{json.dumps(strict_schema(schema), ensure_ascii=False)}")
            request["response_format"] = {"type": "json_object"}
        request["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]

        if group.provider.openrouter_api:
            plugins = [{"id": "response-healing"}]
            if web_search:
                plugins.append({"id": "web", "max_results": config.SOLUTION_CHECK_SEARCHES})
            extra = {"provider": {"require_parameters": True}, "plugins": plugins}
            if len(group.models) > 1:
                extra["models"] = list(group.models)
            request["extra_body"] = extra
        return request


def describe_error(error: openai.APIError) -> str:
    """Class, HTTP status and the provider's message: the class name alone cannot explain a 400."""
    status = getattr(error, "status_code", None)
    message = " ".join(str(getattr(error, "message", None) or error).split())[:240]
    return f"{type(error).__name__}{f' {status}' if status else ''}: {message}"


def _extract_json(content: str | None) -> str:
    text = (content or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    return fenced.group(1) if fenced else text
