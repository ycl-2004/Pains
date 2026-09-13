"""Adapter layer: each source only tests its own payload parsing (shared mechanics live in test_contracts)."""

import unittest

from radar.registry import SOURCES, get_source
from radar.sources.github import GitHubIssues
from radar.sources.hackernews import HackerNews
from radar.sources.stackexchange import StackExchange
from radar.sources.v2ex import V2EX


class HackerNewsParseTest(unittest.TestCase):
    def test_story_and_comment(self):
        adapter = HackerNews()
        story = adapter._parse({"objectID": "1", "title": "Ask HN: tools?", "story_text": "<p>We <b>hate</b> it</p>",
                                "created_at_i": 1789247332, "points": 12, "num_comments": 30, "_tags": ["story", "ask_hn"]})
        comment = adapter._parse({"objectID": "2", "story_title": "Parent story", "comment_text": "I wish there was X",
                                  "created_at_i": 1789247332, "_tags": ["comment", "author_x"]})
        self.assertEqual((story.body, story.comments, story.tags), ("We hate it", 30, ["story", "ask_hn"]))
        self.assertEqual((comment.title, comment.body, comment.tags), ("Parent story", "I wish there was X", ["comment"]))
        self.assertEqual(comment.url, "https://news.ycombinator.com/item?id=2")


class GitHubParseTest(unittest.TestCase):
    def test_issue(self):
        parsed = GitHubIssues()._parse("n8n-io/n8n", {
            "number": 7, "html_url": "https://github.com/n8n-io/n8n/issues/7", "title": "Retry duplicates rows",
            "body": "line one\n\nline two", "created_at": "2026-09-11T05:31:34Z", "comments": 8,
            "reactions": {"total_count": 3}, "labels": [{"name": "bug"}]})
        self.assertEqual((parsed.external_id, parsed.body, parsed.score, parsed.tags),
                         ("n8n-io/n8n#7", "line one line two", 3, ["n8n-io/n8n", "bug"]))


class V2EXParseTest(unittest.TestCase):
    def test_topic(self):
        parsed = V2EX()._parse({"id": 42, "url": "https://www.v2ex.com/t/42", "title": "有没有工具", "content": "每次\n都手动",
                                "created": 1789187170, "replies": 67, "node": {"name": "qna"}})
        self.assertEqual((parsed.external_id, parsed.body, parsed.comments, parsed.tags), ("42", "每次 都手动", 67, ["qna"]))


class StackExchangeParseTest(unittest.TestCase):
    def test_question(self):
        parsed = StackExchange()._parse("softwarerecs", {
            "question_id": 9, "link": "https://softwarerecs.stackexchange.com/q/9", "title": "Tool for &quot;X&quot;",
            "body": "<p>Need it</p>", "creation_date": 1789187170, "score": 2, "answer_count": 1, "tags": ["pdf"]})
        self.assertEqual((parsed.external_id, parsed.title, parsed.body, parsed.tags),
                         ("softwarerecs:9", 'Tool for "X"', "Need it", ["softwarerecs", "pdf"]))


class RegistryTest(unittest.TestCase):
    def test_names_unique_and_lookup(self):
        names = [source.name for source in SOURCES]
        self.assertEqual(len(names), len(set(names)))
        self.assertIs(get_source("v2ex"), SOURCES[names.index("v2ex")])
        with self.assertRaises(KeyError):
            get_source("reddit")


if __name__ == "__main__":
    unittest.main()
