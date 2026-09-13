import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from radar import config
from radar.models import ScoreEvent, Signal
from radar.retention import prune_ledger, prune_reviewed, prune_runtime_data
from test_ledger import ledger


NOW = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)


class RuntimeRetentionTest(unittest.TestCase):
    def test_old_runtime_artifacts_are_pruned_but_recent_and_unknown_names_stay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs, history, raw, audit = (root / name for name in ("runs", "history", "raw", "audit"))
            for directory in (runs, history, raw, audit):
                directory.mkdir()
            (runs / "2026-01-01-000000-000000.json").write_text("{}")
            (runs / "2026-09-12-000000-000000.json").write_text("{}")
            (runs / "keep-me.json").write_text("{}")
            (history / "2025-01-01-000000-000000.json").write_text("{}")
            (history / "2026-09-12-000000-000000.json").write_text("{}")
            (raw / "2025-01-01").mkdir()
            (raw / "2025-01-01" / "old.json").write_text("{}")
            (raw / "2026-09-12").mkdir()
            (raw / "2026-09-12" / "recent.json").write_text("{}")
            old_cache = audit / "old.json"
            old_cache.write_text("{}")
            old_cache.touch()
            with patch.object(config, "RUNS_DIR", runs), patch.object(config, "LEDGER_HISTORY_DIR", history), \
                 patch.object(config, "RAW_DIR", raw), patch.object(config, "AUDIT_DIR", audit), \
                 patch.object(config, "RUN_RETENTION_DAYS", 30), patch.object(config, "HISTORY_RETENTION_DAYS", 30), \
                 patch.object(config, "RAW_RETENTION_DAYS", 30), patch.object(config, "AUDIT_RETENTION_DAYS", 30):
                stats = prune_runtime_data(NOW)
            self.assertEqual(stats["runs"], 1)
            self.assertEqual(stats["history"], 1)
            self.assertEqual(stats["raw_directories"], 1)
            self.assertTrue((runs / "2026-09-12-000000-000000.json").exists())
            self.assertTrue((runs / "keep-me.json").exists())
            self.assertTrue((raw / "2026-09-12").exists())

    def test_reviewed_bookkeeping_drops_only_old_timestamped_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviewed.json"
            path.write_text(json.dumps({
                "old": {"last_attempt": "2025-01-01T00:00:00+00:00"},
                "recent": {"last_attempt": "2026-09-12T00:00:00+00:00"},
                "legacy_old": "2025-01-01T00:00:00",
                "unknown": "legacy",
            }))
            with patch.object(config, "REVIEWED_RETENTION_DAYS", 30):
                self.assertTrue(prune_reviewed(path, NOW))
            self.assertEqual(set(json.loads(path.read_text())), {"recent", "unknown"})


class LedgerRetentionTest(unittest.TestCase):
    def test_stale_archives_and_signals_are_removed_and_history_is_capped(self):
        state = ledger()
        state.clusters[1].last_detected = "2025-01-01"
        state.clusters[0].score_history = [
            ScoreEvent(run_id=str(index), date="2026-01-01", overall=5, reason="x")
            for index in range(5)
        ]
        state.signals = [
            Signal(id="SIG-OLD", title="old", why_watch="old", first_detected="2025-01-01", last_detected="2025-01-01"),
            Signal(id="SIG-NEW", title="new", why_watch="new", first_detected="2026-09-01", last_detected="2026-09-12"),
        ]
        with patch.object(config, "ARCHIVE_RETENTION_DAYS", 30), patch.object(config, "SIGNAL_RETENTION_DAYS", 30), \
             patch.object(config, "MAX_SCORE_HISTORY", 2):
            stats = prune_ledger(state, NOW)
        self.assertEqual(stats, {"clusters": 1, "signals": 1, "score_histories": 1})
        self.assertEqual([cluster.id for cluster in state.clusters], ["OP-001"])
        self.assertEqual([signal.id for signal in state.signals], ["SIG-NEW"])
        self.assertEqual(len(state.clusters[0].score_history), 2)


if __name__ == "__main__":
    unittest.main()
