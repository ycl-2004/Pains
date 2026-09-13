import json
import unittest

from radar.export import _public_cluster, _public_signal
from radar.models import Evidence, ScoreEvent, Signal
from test_ledger import ledger


class PublicExportTest(unittest.TestCase):
    def test_internal_run_provenance_is_not_published(self):
        state = ledger()
        cluster = state.clusters[0]
        cluster.status = "demoted"
        cluster.status_reason = "codex-pp 给 7.8 分，但已有方案覆盖"
        cluster.score_history = [ScoreEvent(run_id="baseline", date="2026-09-01", overall=7.8, reason="claude-pp 的历史判断")]
        cluster.evidence = [Evidence(url="https://example.com", platform="HN", date="2026-09-01",
                                     date_basis="agy_pp_recorded_unverified", kind="complaint",
                                     paraphrase="agy-pp 记录，未复核原文", engagement="")]
        signal = Signal(id="SIG-001", title="signal", why_watch="codex-pp 观察到新趋势", first_detected="2026-09-01",
                        last_detected="2026-09-01")

        public = json.dumps({"cluster": _public_cluster(cluster), "signal": _public_signal(signal)}, ensure_ascii=False)
        self.assertNotRegex(public, r"(?i)(claude|codex|agy)[-_]pp")
        self.assertNotIn("未复核原文", public)
        self.assertEqual(_public_cluster(cluster)["status_reason"], "已归档：现有方案或证据暂不支持当前机会。")
        self.assertEqual(_public_cluster(cluster)["evidence"][0]["paraphrase"], "历史记录，原文尚未完成复核。")
        self.assertEqual(_public_signal(signal)["why_watch"], "基于历史资料的观察，仍待验证。")


if __name__ == "__main__":
    unittest.main()
