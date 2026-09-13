import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, Mock

from radar.evidence import qualification
from radar.revisit import revisit
from radar.sources.hackernews import HackerNews
from radar import config
from test_ledger import ledger, evidence
from test_llm import raw
from radar.evaluate import evaluate


class QualificationTest(unittest.TestCase):
    def test_evaluation_rejects_missing_ids_and_reports_wrong_dimensions(self):
        cases = json.loads((Path(__file__).resolve().parents[1] / 'evals/commercial-cases.json').read_text())['cases']
        predictions = [{"id": c['id'], **c['expected']} for c in cases]
        self.assertEqual(len(cases), 20)
        self.assertEqual(evaluate(cases, predictions)['failures'], [])
        with self.assertRaises(ValueError):
            evaluate(cases, predictions[:-1])
        predictions[0]['kind'] = 'vendor_reply'
        self.assertEqual(evaluate(cases, predictions)['failures'][0]['field'], 'kind')

    def test_qualification_boundaries_and_reasons(self):
        c = ledger().clusters[0]
        c.solution_class = 'B'
        c.evidence.append(evidence('https://b'))
        c.solution_checked_at = '2026-09-06'
        now = datetime(2026, 9, 13, 23, tzinfo=timezone.utc)
        self.assertTrue(qualification(c, now)['eligible'])
        self.assertFalse(qualification(c, now + timedelta(days=1))['eligible'])
        c.status = 'demoted'
        self.assertIn('不是活跃状态', qualification(c, now)['reasons'])
        c.solution_checked_at = 'bad'
        self.assertIn('方案核查日期无效', qualification(c, now)['reasons'])

    def test_duplicate_thread_does_not_qualify(self):
        c = ledger().clusters[0]
        c.solution_class = 'B'; c.solution_checked_at = '2026-09-13'
        c.evidence.append(evidence('https://a/?utm_source=copy'))
        self.assertFalse(qualification(c, datetime(2026, 9, 13, tzinfo=timezone.utc))['eligible'])


class RevisitTest(unittest.TestCase):
    def test_failure_is_recorded_and_other_threads_get_a_turn(self):
        state = ledger()
        state.clusters[0].evidence = [evidence(f'https://news.ycombinator.com/item?id={i}') for i in range(6)]
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        source = Mock(); source.attach_thread.side_effect = RuntimeError('network')
        with tempfile.TemporaryDirectory() as tmp, patch.object(config, 'DATA_DIR', Path(tmp)), patch('radar.revisit.get_source', return_value=source):
            items, notes, records = revisit(state, now)
            self.assertEqual((len(items), len(notes), len(records)), (0, 5, 5))
            (Path(tmp) / 'reviewed.json').write_text(json.dumps(records))
            _, notes2, records2 = revisit(state, now + timedelta(hours=1))
            self.assertEqual(len(notes2), 1)
            self.assertEqual(len(records2), 6)
            self.assertEqual(records2['hackernews:0']['outcome'], 'fetch_failed')

    def test_legacy_success_timestamp_is_respected(self):
        state = ledger(); state.clusters[0].evidence = [evidence('https://news.ycombinator.com/item?id=1')]
        now = datetime(2026, 9, 13, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, patch.object(config, 'DATA_DIR', Path(tmp)):
            (Path(tmp) / 'reviewed.json').write_text(json.dumps({'hackernews:1': now.isoformat()}))
            self.assertEqual(revisit(state, now)[0], [])

    def test_hn_refreshes_original_not_old_paraphrase(self):
        source = HackerNews()
        with patch.object(source, 'get_json', return_value={'title': 'Updated', 'text': '<p>Now fixed</p>', 'children': []}):
            refreshed = source.attach_thread(raw('1'))
        self.assertEqual(refreshed.body, 'Now fixed')
        self.assertEqual(refreshed.refresh_scope, 'original_and_replies')
