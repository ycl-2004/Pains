"""Ledger rules: how one run's analysis is folded into the long-lived ledger."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from radar.ledger import apply_analysis, load, next_id, save, snapshot
from radar.models import AnalysisResult, Cluster, ClusterUpdate, Evidence, Ledger, SignalDraft
from radar.scoring import Scores

TODAY = "2026-09-13"


def scores(overall: float) -> Scores:
    return Scores(frequency=5, severity=5, urgency=5, existing_solution_gap=5, willingness_to_pay=5, momentum=5,
                  ease_of_validation=5, overall=overall)


def evidence(url: str, kind: str = "workaround") -> Evidence:
    return Evidence(url=url, platform="HN", date=TODAY, date_basis="post_date", kind=kind, paraphrase="p", engagement="")


def update(cluster_id: str, *, overall: float = 6, new_evidence=(), name: str = "", contrarian=()) -> ClusterUpdate:
    return ClusterUpdate(cluster_id=cluster_id, name=name, who="", problem="", industry="", workaround="",
                         existing_solutions=[], why_insufficient="", root_cause="", why_now="", opportunity_hypothesis="",
                         contrarian=list(contrarian), next_validation=[], new_evidence=list(new_evidence),
                         solution_class="B", scores=scores(overall), score_reason="because", pain_confidence="medium",
                         gap_confidence="low")


def ledger() -> Ledger:
    return Ledger(updated_at=datetime(2026, 9, 12, tzinfo=timezone.utc), clusters=[
        Cluster(id="OP-001", name="existing", status="active", who="who", scores=scores(5),
                evidence=[evidence("https://a")], first_detected="2026-09-12", last_detected="2026-09-12"),
        Cluster(id="OP-002", name="demoted", status="demoted", status_reason="solved", first_detected="2026-09-12",
                last_detected="2026-09-12"),
    ], signals=[])


def analysis(*updates: ClusterUpdate, top=(), signals=()) -> AnalysisResult:
    return AnalysisResult(updates=list(updates), new_signals=list(signals), top_opportunity_ids=list(top), summary="s")


class ApplyAnalysisTest(unittest.TestCase):
    def test_update_merges_without_erasing_and_counts_one_detection_per_run(self):
        state = ledger()
        apply_analysis(state, analysis(
            update("OP-001", new_evidence=[evidence("https://a"), evidence("https://b")], contrarian=["c1"]),
            update("OP-001", overall=6.5, new_evidence=[evidence("https://c")], contrarian=["c1"]),
        ), "run-1", TODAY)
        cluster = state.clusters[0]
        self.assertEqual(cluster.who, "who")
        self.assertEqual([e.url for e in cluster.evidence], ["https://a", "https://b", "https://c"])
        self.assertEqual(cluster.contrarian, ["c1"])
        self.assertEqual((cluster.detected_runs, cluster.last_detected), (2, TODAY))
        self.assertEqual([(e.run_id, e.overall) for e in cluster.score_history], [("run-1", 6.5)])

    def test_vendor_only_evidence_is_not_a_detection(self):
        state = ledger()
        apply_analysis(state, analysis(update("OP-001", new_evidence=[evidence("https://v", "vendor_launch")])), "run-1", TODAY)
        self.assertEqual(state.clusters[0].detected_runs, 1)

    def test_new_cluster_gets_next_id_and_top_reference_resolves(self):
        state = ledger()
        changes, _, top = apply_analysis(state, analysis(update("NEW", name="fresh pain", overall=7),
                                                         top=["NEW:fresh pain", "OP-001", "OP-404"]), "run-1", TODAY)
        self.assertEqual(changes[0].cluster_id, "OP-003")
        self.assertEqual(state.clusters[-1].origin, ["pipeline"])
        self.assertEqual(top, ["OP-003", "OP-001"])

    def test_demoted_cluster_revives_to_watch_only_with_enough_score(self):
        state = ledger()
        apply_analysis(state, analysis(update("OP-002", overall=4)), "run-1", TODAY)
        self.assertEqual(state.clusters[1].status, "demoted")
        apply_analysis(state, analysis(update("OP-002", overall=5.5)), "run-2", TODAY)
        self.assertEqual(state.clusters[1].status, "watch")

    def test_signals_get_ids(self):
        state = ledger()
        _, ids, _ = apply_analysis(state, analysis(signals=[SignalDraft(title="t", why_watch="w", watch_next="n", evidence=[])]),
                                   "run-1", TODAY)
        self.assertEqual(ids, ["SIG-001"])


class PersistenceTest(unittest.TestCase):
    def test_save_load_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            save(ledger(), path)
            self.assertEqual(load(path).clusters[0].id, "OP-001")
            self.assertTrue(snapshot(load(path), "run-1", Path(tmp) / "history").exists())

    def test_next_id(self):
        self.assertEqual(next_id(["OP-009", "OP-010", "SIG-002"], "OP"), "OP-011")
        self.assertEqual(next_id([], "SIG"), "SIG-001")


if __name__ == "__main__":
    unittest.main()
