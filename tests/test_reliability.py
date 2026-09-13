"""Regressions for silent failures, invented evidence and misleading commercial signals."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree as ET

from radar import cli, config
from radar.ledger import apply_analysis, apply_solution_check
from radar.llm.analyze import run_analysis
from radar.llm.client import LLM, Budget, StageFailed, BudgetExceeded
from radar.models import SourceStat, RunReport, SolutionCheck, Signal, SignalUpdate
from radar.sampling import select_items
from radar.sources.business import BusinessFeed
from radar.sources.github import GitHubIssues
from radar.privacy import redact
from test_ledger import ledger, analysis, update, evidence, TODAY
from test_llm import raw, verdict, FakeLLM, stub_client, response, complete, VALID


class EvidenceRegressionTest(unittest.TestCase):
    def test_duplicate_url_does_not_detect_even_with_tracking_parameters(self):
        state = ledger()
        apply_analysis(state, analysis(update("OP-001", new_evidence=[evidence("https://a/?utm_source=x#reply")])), "r", TODAY)
        self.assertEqual(state.clusters[0].detected_runs, 1)
        self.assertEqual(len(state.clusters[0].evidence), 1)

    def test_unknown_id_rejects_entire_batch_before_mutation(self):
        state = ledger(); before = state.model_dump()
        with self.assertRaises(ValueError):
            apply_analysis(state, analysis(update("OP-001", name="changed"), update("OP-TYPO")), "r", TODAY)
        self.assertEqual(state.model_dump(), before)

    def test_solved_check_demotes_and_records_score(self):
        cluster = ledger().clusters[0]
        check = SolutionCheck(existing_solutions=["native"], why_insufficient="已解决", solution_class="A",
                              sources=[evidence("https://official", "official_doc")])
        apply_solution_check(cluster, check, TODAY, "r")
        self.assertEqual(cluster.status, "demoted")
        self.assertLessEqual(cluster.scores.overall, 4)
        self.assertEqual(cluster.score_history[-1].run_id, "r:solution")

    def test_no_new_evidence_cannot_revive_demoted(self):
        state = ledger()
        apply_analysis(state, analysis(update("OP-002", overall=9)), "r", TODAY)
        self.assertEqual(state.clusters[1].status, "demoted")

    def test_hallucinated_source_rejected(self):
        result = analysis(update("OP-001", new_evidence=[evidence("https://invented")]))
        with self.assertRaises(StageFailed):
            run_analysis(FakeLLM(result), ledger(), [(raw("1"), verdict("hackernews:1"))])

    def test_payment_claim_requires_citation(self):
        result = analysis(update("OP-001"))
        result.updates[0].payment_evidence = "willing to pay $100"
        with self.assertRaises(StageFailed):
            run_analysis(FakeLLM(result), ledger(), [(raw("1"), verdict("hackernews:1"))])

    def test_old_thread_resolution_replaces_demand_without_increment(self):
        state = ledger()
        apply_analysis(state, analysis(update("OP-001", new_evidence=[evidence("https://a", "counterevidence")])), "r", TODAY)
        self.assertEqual(state.clusters[0].detected_runs, 1)
        self.assertFalse(state.clusters[0].evidence[0].counts_as_demand)

    def test_signal_promotion_links_existing_cluster(self):
        state = ledger()
        state.signals.append(Signal(id="SIG-001", title="x", why_watch="x", first_detected=TODAY,last_detected=TODAY))
        result = analysis()
        result.signal_updates = [SignalUpdate(signal_id="SIG-001",status="promoted",cluster_id="OP-001",why_watch="",watch_next="",evidence=[])]
        apply_analysis(state,result,"r",TODAY)
        self.assertEqual((state.signals[0].status,state.signals[0].promoted_to),("promoted","OP-001"))


class RunRegressionTest(unittest.TestCase):
    def test_full_run_saves_watch_then_activates_after_solution_check(self):
        from radar.ledger import load
        from radar.export import load_runs
        from contextlib import ExitStack
        items = [raw("10"), raw("11")]
        result = analysis(update("NEW", name="Invoice reconciliation", new_evidence=[
            evidence(items[0].url), evidence(items[1].url)]))
        check = SolutionCheck(existing_solutions=["partial tool"], why_insufficient="manual step remains", solution_class="B",
                              sources=[evidence("https://official.example/tool", "official_doc")])
        state = ledger()
        state.clusters = []
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            root = Path(tmp)
            for name, value in {"DATA_DIR":root,"LEDGER_PATH":root/'ledger.json',"RUNS_DIR":root/'runs',
                                "LEDGER_HISTORY_DIR":root/'history',"SEEN_PATH":root/'seen.json',
                                "WEB_DATA_DIR":root/'web',"AUDIT_DIR":root/'audit'}.items():
                stack.enter_context(patch.object(config,name,value))
            stack.enter_context(patch.object(cli,'llm_problem',return_value=None))
            stack.enter_context(patch.object(cli,'ensure_ledger',return_value=state))
            stack.enter_context(patch.object(cli,'collect',return_value=([SourceStat(source='hackernews',fetched=2)],items)))
            stack.enter_context(patch.object(cli,'revisit',return_value=([],[],{})))
            stack.enter_context(patch.object(cli,'run_triage',return_value=([(i,verdict(i.key)) for i in items],items,[])))
            stack.enter_context(patch.object(cli,'deepen',side_effect=lambda items,report:items))
            stack.enter_context(patch.object(cli,'run_analysis',return_value=result))
            stack.enter_context(patch.object(cli,'check_solutions',return_value=check))
            self.assertEqual(cli.cmd_run(SimpleNamespace(limit=30,max_cost=1,skip_solution_check=False)),0)
            saved = load(config.LEDGER_PATH)
            self.assertEqual(saved.clusters[0].status,'active')
            self.assertEqual(load_runs(config.RUNS_DIR)[0].top_opportunities,[saved.clusters[0].id])
            self.assertEqual(set(json.loads(config.SEEN_PATH.read_text())),{i.key for i in items})
            self.assertTrue((config.WEB_DATA_DIR/'radar.json').exists())

    def test_stage_failure_returns_nonzero_and_preserves_report(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(config,"DATA_DIR",Path(tmp)), patch.object(cli,"llm_problem",return_value=None), \
             patch.object(cli,"ensure_ledger",return_value=ledger()), patch.object(cli,"collect",return_value=([SourceStat(source="hackernews",fetched=1)], [raw("1")])), \
             patch.object(cli,"revisit",return_value=([],[],{})), patch.object(cli,"run_triage",side_effect=StageFailed("failure")), \
             patch.object(cli,"save_run") as saved:
            self.assertEqual(cli.cmd_run(SimpleNamespace(limit=30,max_cost=1,skip_solution_check=True)),1)
            self.assertEqual(saved.call_args.args[0].status,"failed")

    def test_failed_refresh_does_not_delay_retry(self):
        now = datetime.now(timezone.utc)
        runs = [RunReport(run_id="ok",started_at=now-timedelta(hours=1),window_hours=72),
                RunReport(run_id="bad",started_at=now,window_hours=72,status="failed")]
        with patch.object(cli,"ensure_ledger"),patch.object(cli,"load_runs",return_value=runs),patch.object(cli,"llm_problem",return_value=None), \
             patch.object(cli,"cmd_run",return_value=1) as run,patch.object(cli,"cmd_export"):
            self.assertEqual(cli.cmd_refresh(SimpleNamespace(stale_after="20h",strict=True)),1)
            run.assert_called_once()

    def test_due_solution_checks_run_without_new_clusters(self):
        state = ledger()
        check = SolutionCheck(existing_solutions=["x"],why_insufficient="solved",solution_class="A",sources=[evidence("https://official","official_doc")])
        report = RunReport(run_id="r",started_at=datetime.now(timezone.utc),window_hours=72)
        with patch.object(cli,"check_solutions",return_value=check) as checker:
            cli.run_solution_checks(object(),state,report,TODAY)
        checker.assert_called_once()
        self.assertEqual(state.clusters[0].status,"demoted")


class SourceRegressionTest(unittest.TestCase):
    def test_business_sampling_cannot_be_swamped_by_hn(self):
        items = [raw(str(i)).model_copy(update={"comments":9999}) for i in range(100)]
        for source in ("make","n8n","wordpress","v2ex"):
            items += [raw(f"{source}{i}").model_copy(update={"source":source}) for i in range(5)]
        selected = select_items(items,10)
        self.assertEqual(len(selected),10)
        self.assertTrue({"make","n8n","wordpress","v2ex","hackernews"} <= {i.source for i in selected})
        self.assertGreater(sum(i.source in {"make","n8n","wordpress"} for i in selected),5)

    def test_rss_parses_body_and_ignores_offsite_links(self):
        adapter = BusinessFeed("wordpress","WP","https://wordpress.org",("/feed/",))
        xml = '<item><title>Invoice export</title><link>https://wordpress.org/support/topic/invoice/</link><pubDate>Sun, 13 Sep 2026 02:22:04 +0000</pubDate><description>&lt;p&gt;manual work&lt;/p&gt;</description></item>'
        node = ET.fromstring(xml)
        self.assertEqual(adapter._parse(node).body,"manual work")
        node.find("link").text = "https://attacker.example/feed"
        self.assertIsNone(adapter._parse(node))

    def test_old_updated_github_issue_survives_window(self):
        adapter = GitHubIssues()
        now = datetime.now(timezone.utc)
        item = raw("1").model_copy(update={"created_at":now-timedelta(days=100),"updated_at":now})
        with patch.object(adapter,"fetch",return_value=[item]):
            self.assertEqual(adapter.collect(now,timedelta(hours=72)),[item])
        self.assertNotEqual(item.key,item.revision_key)

    def test_github_closed_not_planned_is_not_a_fix(self):
        item=GitHubIssues()._parse('org/repo',{'number':1,'html_url':'https://github.com/org/repo/issues/1',
              'title':'needs feature','created_at':'2026-09-01T00:00:00Z','state':'closed','state_reason':'not_planned'})
        self.assertFalse(item.resolved)
        self.assertIn('state_reason:not_planned',item.tags)

    def test_privacy_filter(self):
        self.assertEqual(redact('email a@company.com sk-abcdefghijklmnop'), 'email [email removed] [token removed]')


class BudgetAndCacheTest(unittest.TestCase):
    def test_annotated_search_source_accepted(self):
        check=SolutionCheck(existing_solutions=[],why_insufficient="x",solution_class="B",sources=[evidence("https://official.example","official_doc")])
        served=response(check.model_dump_json(),cost=0)
        served.choices[0].message.annotations=[{"type":"url_citation","url_citation":{"url":"https://official.example"}}]
        client,_=stub_client(served)
        self.assertEqual(complete(LLM(Budget(1),clients={"openrouter":client}),["vendor/a"],schema=SolutionCheck,web_search=True),check)

    def test_estimate_blocks_unaffordable_call(self):
        client,calls=stub_client()
        with self.assertRaises(StageFailed):
            complete(LLM(Budget(.000001),clients={"openrouter":client}),["vendor/a"])
        self.assertEqual(calls.calls,[])

    def test_completed_call_reused_without_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            client,calls=stub_client(response(VALID,cost=.001))
            complete(LLM(Budget(1),clients={"openrouter":client},cache_dir=Path(tmp)),["vendor/a"])
            budget=Budget(0)
            complete(LLM(budget,clients={"openrouter":client},cache_dir=Path(tmp)),["vendor/a"])
            self.assertEqual(len(calls.calls),1)
            self.assertEqual(budget.spent,0)

    def test_unannotated_search_sources_rejected(self):
        check=SolutionCheck(existing_solutions=[],why_insufficient="x",solution_class="B",sources=[evidence("https://invented","official_doc")])
        client,_=stub_client(response(check.model_dump_json(),cost=0))
        with self.assertRaises(StageFailed):
            complete(LLM(Budget(1),clients={"openrouter":client}),["vendor/a"],schema=SolutionCheck,web_search=True)


if __name__ == "__main__":
    unittest.main()
