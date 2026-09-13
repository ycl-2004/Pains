"""Model access through OpenAI-compatible APIs, with an ordered fallback chain, spend accounting and a hard cap.

Fallback strategy for every stage:
1. Consecutive OpenRouter models go out as ONE request with `models=[...]`. OpenRouter itself moves to the
   next model on provider errors, rate limits, downtime, context-length and moderation failures.
2. OpenRouter does not fall back on bad output, so we do: a truncated answer, non-JSON, or a schema
   validation failure moves on to the next route group.
3. Direct-provider routes such as `deepseek:deepseek-flash` are their own request, usually last in the chain.
4. Running out of budget stops the stage immediately; it never triggers a fallback.
"""

import json
import os
import re
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


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_env: str
    output_mode: Literal["json_schema", "json_object"]
    # Accepts OpenRouter's body extensions: `models` fallback list, `provider` routing, `plugins` (web, healing).
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
            groups[-1] = RouteGroup(provider, groups[-1].models + (model,))
        else:
            groups.append(RouteGroup(provider, (model,)))
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
                 env: Mapping[str, str] = os.environ) -> None:
        self.budget = budget
        self.notes: list[str] = []
        self._clients: dict[str, object | None] = dict(clients or {})
        self._env = env

    def complete(self, stage: str, *, system: str, user: str, schema: type[T], routes: Iterable[str],
                 max_tokens: int, web_search: bool = False) -> T:
        failures: list[str] = []
        for group in parse_routes(routes):
            if web_search and not group.provider.openrouter_api:
                failures.append(f"{group.label} 不支持联网搜索")
                continue
            client = self._client(group.provider)
            if client is None:
                failures.append(f"{group.label} 缺少 {group.provider.key_env}")
                continue
            self.budget.ensure_room(stage)
            try:
                response = client.chat.completions.create(**self._request(group, system, user, schema, max_tokens, web_search))
            except openai.APIError as error:
                failures.append(f"{group.label} 调用失败（{type(error).__name__}）")
                continue

            served = response.model or group.models[0]
            self.budget.record(stage, group.provider, served, response.usage, web_search=web_search)
            choice = response.choices[0] if response.choices else None
            if choice is None or choice.finish_reason == "length":
                failures.append(f"{served} 输出为空或被截断")
                continue
            try:
                result = schema.model_validate_json(_extract_json(choice.message.content))
            except pydantic.ValidationError as error:
                failures.append(f"{served} 输出不符合结构（{error.error_count()} 处错误）")
                continue
            if failures:
                self.notes.append(f"{stage} 降级到 {served}：{'；'.join(failures)}")
            return result
        raise StageFailed(f"{stage} 的所有模型都失败：{'；'.join(failures) or '没有配置模型'}")

    def _client(self, provider: Provider):
        if provider.name not in self._clients:
            key = self._env.get(provider.key_env)
            self._clients[provider.name] = (
                openai.OpenAI(api_key=key, base_url=provider.base_url, timeout=900, max_retries=2) if key else None
            )
        return self._clients[provider.name]

    def _request(self, group: RouteGroup, system: str, user: str, schema: type[BaseModel], max_tokens: int,
                 web_search: bool) -> dict:
        request = {"model": group.models[0], "max_tokens": max_tokens}
        if group.provider.output_mode == "json_schema":
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


def _extract_json(content: str | None) -> str:
    text = (content or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    return fenced.group(1) if fenced else text
