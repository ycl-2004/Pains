"""Contract layer: scoring vocabulary, shared collector mechanics, the baseline seed."""

import unittest
from datetime import datetime, timedelta, timezone

from radar import config
from radar.ledger import load
from radar.models import Evidence, RawItem
from radar.scoring import DIMENSIONS, Scores, clamp_scores, render_rubric
from radar.sources.base import SourceAdapter, dedupe, strip_html

NOW = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)


def item(external_id: str, *, title: str = "plain title", hours_ago: int = 1, comments: int = 0) -> RawItem:
    return RawItem(source="dummy", external_id=external_id, url=f"https://example.com/{external_id}", title=title,
                   created_at=NOW - timedelta(hours=hours_ago), comments=comments)


class DummyAdapter(SourceAdapter):
    name = "dummy"
    label = "Dummy"
    high_engagement_comments = 50
    thread_limit = 2
    thread_chars = 5

    def __init__(self, items: list[RawItem], replies: list[str] | None = None) -> None:
        super().__init__()
        self._items = items
        self._replies = replies or []

    def fetch(self, since):
        return self._items

    def fetch_thread(self, item):
        return self._replies


class ScoringTest(unittest.TestCase):
    def test_clamp_keeps_rubric_bounds_and_half_steps(self):
        scores = clamp_scores(Scores(frequency=12, severity=0, urgency=5, existing_solution_gap=5,
                                     willingness_to_pay=5, momentum=5, ease_of_validation=5, overall=6.3))
        self.assertEqual((scores.frequency, scores.severity, scores.overall), (10, 1, 6.5))

    def test_rubric_mentions_every_dimension(self):
        rubric = render_rubric()
        for name in DIMENSIONS:
            self.assertIn(name, rubric)

    def test_vendor_evidence_never_counts_as_demand(self):
        base = dict(url="u", platform="p", date=None, date_basis="post_date", paraphrase="x", engagement="")
        self.assertTrue(Evidence(kind="workaround", **base).counts_as_demand)
        self.assertFalse(Evidence(kind="vendor_launch", **base).counts_as_demand)
        self.assertFalse(Evidence(kind="official_doc", **base).counts_as_demand)


class SourceAdapterMechanicsTest(unittest.TestCase):
    def test_collect_applies_window_and_dedupes(self):
        adapter = DummyAdapter([item("a"), item("a"), item("old", hours_ago=100)])
        collected = adapter.collect(NOW, timedelta(hours=72))
        self.assertEqual([i.external_id for i in collected], ["a"])

    def test_prefilter_keeps_pain_language_or_heated_threads(self):
        adapter = DummyAdapter([])
        kept = adapter.prefilter([
            item("pain", title="Is there a tool to reconcile invoices"),
            item("chinese", title="每次都要手动导出报表"),
            item("heated", title="My admin lost it", comments=60),
            item("noise", title="Weekly photo thread"),
        ])
        self.assertEqual([i.external_id for i in kept], ["pain", "chinese", "heated"])

    def test_attach_thread_truncates_count_and_length(self):
        adapter = DummyAdapter([], replies=["first reply", "second", "third"])
        self.assertEqual(adapter.attach_thread(item("a")).thread, ["first", "secon"])

    def test_strip_html_and_dedupe(self):
        self.assertEqual(strip_html("<p>a &amp; <i>b</i></p>"), "a & b")
        self.assertEqual(len(dedupe([item("x"), item("x")])), 1)


class SeedTest(unittest.TestCase):
    def test_seed_is_valid_and_every_merge_has_a_target(self):
        ledger = load(config.SEED_PATH)
        targets = {c.id for c in ledger.clusters} | {s.id for s in ledger.signals} | {"-"}
        self.assertTrue(all(record.new_id in targets for record in ledger.merge_log))
        self.assertEqual({r.origin for r in ledger.merge_log}, {"claude-pp", "codex-pp", "agy-pp"})
        self.assertEqual(len({c.id for c in ledger.clusters}), len(ledger.clusters))


if __name__ == "__main__":
    unittest.main()
