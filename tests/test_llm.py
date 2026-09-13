"""LLM layer with stub OpenAI-compatible clients: routing, fallback, accounting, stage payloads. No network."""

import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx2
import openai

from radar.llm.analyze import check_solutions, run_analysis
from radar.llm.client import LLM, Budget, BudgetExceeded, StageFailed, parse_routes, strict_schema
from radar.llm.triage import run_triage
from radar.models import AnalysisResult, Cluster, Ledger, RawItem, SolutionCheck, TriageResult, TriageVerdict


def verdict(key: str, *, pain: bool = True, codable: bool = True) -> TriageVerdict:
    return TriageVerdict(key=key, is_pain_point=pain, codable=codable, who="w", pain="p", loss="l", workaround="",
                         kind="workaround", reject_reason="")


VALID = TriageResult(verdicts=[verdict("hackernews:1")]).model_dump_json()


def response(content, *, model="vendor/a", finish="stop", cost=None, prompt=1000, completion=200):
    usage = SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, prompt_tokens_details=None,
                            **({"cost": cost} if cost is not None else {}))
    return SimpleNamespace(model=model, usage=usage,
                           choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content))])


class Recorder:
    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, **kwargs})
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def stub_client(*results, catalog=()):
    """`catalog` stands in for OpenRouter's model list: (model id, supported_parameters) pairs, or an exception."""
    recorder = Recorder(results)

    def list_models():
        if isinstance(catalog, Exception):
            raise catalog
        return [SimpleNamespace(id=model, supported_parameters=list(parameters)) for model, parameters in catalog]

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=recorder)),
                             models=SimpleNamespace(list=list_models))
    return client, recorder


def complete(llm: LLM, routes, **overrides):
    arguments = dict(system="sys", user="usr", schema=TriageResult, routes=routes, max_tokens=100) | overrides
    return llm.complete("triage", **arguments)


class RoutingContractTest(unittest.TestCase):
    def test_openrouter_models_group_and_direct_providers_split(self):
        groups = parse_routes(["a/x", "b/y:free", "deepseek:deepseek-flash", "c/z"])
        self.assertEqual([g.output_mode for g in groups], ["json_schema", "json_object", "json_schema"])
        self.assertEqual([(g.provider.name, g.models) for g in groups], [
            ("openrouter", ("a/x", "b/y:free")), ("deepseek", ("deepseek-flash",)), ("openrouter", ("c/z",))])

    def test_strict_schema_closes_nested_objects(self):
        schema = strict_schema(TriageResult)
        verdict_schema = schema["$defs"]["TriageVerdict"]
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(verdict_schema["additionalProperties"])
        self.assertEqual(set(verdict_schema["required"]), set(TriageVerdict.model_fields))


class FallbackContractTest(unittest.TestCase):
    def test_openrouter_request_shape_and_reported_cost(self):
        client, calls = stub_client(response(VALID, cost=0.004))
        budget = Budget(1)
        llm = LLM(budget, clients={"openrouter": client})
        self.assertEqual(complete(llm, ["a/x", "b/y"]).verdicts[0].key, "hackernews:1")
        call = calls.calls[0]
        self.assertEqual(call["model"], "a/x")
        self.assertEqual(call["extra_body"]["models"], ["a/x", "b/y"])
        self.assertTrue(call["extra_body"]["provider"]["require_parameters"])
        self.assertEqual(call["response_format"]["type"], "json_schema")
        self.assertTrue(call["response_format"]["json_schema"]["strict"])
        self.assertAlmostEqual(budget.spent, 0.004)
        self.assertEqual(llm.notes, [])

    def test_bad_output_falls_back_to_direct_provider_with_schema_in_prompt(self):
        openrouter, _ = stub_client(response("not json", cost=0.001))
        deepseek, deepseek_calls = stub_client(response(f"```json\n{VALID}\n```", model="deepseek-flash"))
        budget = Budget(1)
        llm = LLM(budget, clients={"openrouter": openrouter, "deepseek": deepseek})
        self.assertEqual(len(complete(llm, ["a/x", "deepseek:deepseek-flash"]).verdicts), 1)
        call = deepseek_calls.calls[0]
        self.assertEqual(call["response_format"], {"type": "json_object"})
        self.assertIn("JSON Schema", call["messages"][0]["content"])
        self.assertNotIn("extra_body", call)
        self.assertAlmostEqual(budget.spent, 0.001 + (1000 * 0.30 + 200 * 1.20) / 1_000_000)
        self.assertEqual(len(llm.notes), 1)
        self.assertIn("deepseek-flash", llm.notes[0])

    def test_catalog_picks_json_mode_per_model_and_keeps_chain_order(self):
        catalog = [("q/flash", ["response_format"]), ("a/x", ["response_format", "structured_outputs"]),
                   ("b/y", ["response_format", "structured_outputs"])]
        client, calls = stub_client(response("{}", model="q/flash", cost=0), response(VALID, cost=0), catalog=catalog)
        llm = LLM(Budget(1), clients={"openrouter": client})
        self.assertEqual(len(complete(llm, ["q/flash", "a/x", "b/y"]).verdicts), 1)
        first, second = calls.calls
        self.assertEqual((first["model"], first["response_format"]), ("q/flash", {"type": "json_object"}))
        self.assertIn("JSON Schema", first["messages"][0]["content"])
        self.assertNotIn("models", first["extra_body"])
        self.assertEqual(second["response_format"]["type"], "json_schema")
        self.assertEqual(second["extra_body"]["models"], ["a/x", "b/y"])

    def test_catalog_failure_falls_back_to_strict_mode_with_a_note(self):
        timeout = openai.APITimeoutError(request=httpx2.Request("GET", "https://openrouter.ai/api/v1/models"))
        client, calls = stub_client(response(VALID, cost=0), catalog=timeout)
        llm = LLM(Budget(1), clients={"openrouter": client})
        complete(llm, ["q/flash"])
        self.assertEqual(calls.calls[0]["response_format"]["type"], "json_schema")
        self.assertIn("模型目录", llm.notes[0])

    def test_truncated_output_moves_on(self):
        client, _ = stub_client(response("{", finish="length", cost=0), response(VALID, model="c/z", cost=0))
        llm = LLM(Budget(1), clients={"openrouter": client, "deepseek": None})
        self.assertEqual(len(complete(llm, ["a/x", "deepseek:deepseek-flash", "c/z"]).verdicts), 1)

    def test_api_error_then_missing_key_fails_the_stage(self):
        timeout = openai.APITimeoutError(request=httpx2.Request("POST", "https://openrouter.ai/api/v1/chat/completions"))
        client, _ = stub_client(timeout)
        llm = LLM(Budget(1), clients={"openrouter": client}, env={})
        with self.assertRaises(StageFailed) as caught:
            complete(llm, ["a/x", "deepseek:deepseek-flash"])
        self.assertIn("APITimeoutError", str(caught.exception))
        self.assertIn("DEEPSEEK_API_KEY", str(caught.exception))

    def test_web_search_uses_plugin_and_skips_providers_without_it(self):
        client, calls = stub_client(response(VALID, cost=0))
        llm = LLM(Budget(1), clients={"openrouter": client, "deepseek": object()})
        complete(llm, ["deepseek:deepseek-flash", "a/x"], web_search=True)
        self.assertIn({"id": "web", "max_results": 5}, calls.calls[0]["extra_body"]["plugins"])
        self.assertIn("不支持联网搜索", llm.notes[0])

    def test_budget_blocks_before_any_call(self):
        client, calls = stub_client()
        with self.assertRaises(BudgetExceeded):
            complete(LLM(Budget(0), clients={"openrouter": client}), ["a/x"])
        self.assertEqual(calls.calls, [])


class FakeLLM:
    def __init__(self, *results):
        self.complete = Recorder(results)


def raw(external_id: str) -> RawItem:
    return RawItem(source="hackernews", external_id=external_id, url=f"https://news.ycombinator.com/item?id={external_id}",
                   title=f"title {external_id}", created_at=datetime(2026, 9, 12, tzinfo=timezone.utc))


def ledger() -> Ledger:
    return Ledger(updated_at=datetime(2026, 9, 12, tzinfo=timezone.utc), signals=[], clusters=[
        Cluster(id="OP-001", name="existing", status="active", first_detected="2026-09-12", last_detected="2026-09-12")])


class StageTest(unittest.TestCase):
    def test_triage_keeps_codable_pain_and_skips_failed_chunks(self):
        parsed = TriageResult(verdicts=[verdict("hackernews:1"), verdict("hackernews:2", codable=False)])
        llm = FakeLLM(parsed, StageFailed("all models failed"))
        kept, judged, notes = run_triage(llm, [raw("1"), raw("2"), raw("3"), raw("4")], routes=["a/x"], chunk_size=3)
        self.assertEqual([item.external_id for item, _ in kept], ["1"])
        self.assertEqual([item.external_id for item in judged], ["1", "2"])  # item 3 got no verdict, 4 was skipped
        self.assertEqual(len(notes), 2)
        self.assertIn("hackernews:3", llm.complete.calls[0]["user"])

    def test_analysis_payload_carries_ledger_signals_and_rubric(self):
        llm = FakeLLM(AnalysisResult(updates=[], new_signals=[], top_opportunity_ids=[], summary="ok"))
        self.assertEqual(run_analysis(llm, ledger(), [(raw("9"), verdict("hackernews:9"))], routes=["a/x"]).summary, "ok")
        call = llm.complete.calls[0]
        self.assertIs(call["schema"], AnalysisResult)
        self.assertNotIn("{rubric}", call["system"])
        self.assertIn("OP-001", call["user"])
        self.assertIn("item?id=9", call["user"])

    def test_solution_check_requests_web_search(self):
        from radar.models import Evidence
        check = SolutionCheck(existing_solutions=["Tool X"], why_insufficient="gap", solution_class="B", sources=[
            Evidence(url="https://example.com/tool", platform="official", date=None, date_basis="checked", kind="official_doc", paraphrase="tool", engagement="")])
        llm = FakeLLM(check)
        self.assertEqual(check_solutions(llm, ledger().clusters[0], today="2026-09-13", routes=["a/x"]), check)
        call = llm.complete.calls[0]
        self.assertTrue(call["web_search"])
        self.assertIn("page_checked_2026-09-13", call["system"])
        self.assertEqual(json.loads(call["user"])["name"], "existing")


if __name__ == "__main__":
    unittest.main()
