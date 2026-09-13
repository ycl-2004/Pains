"""Hacker News via the official Algolia API (queries follow claude-pp's methodology)."""

from datetime import datetime, timezone

from radar.models import RawItem
from radar.sources.base import SourceAdapter, strip_html

API = "https://hn.algolia.com/api/v1"


class HackerNews(SourceAdapter):
    name = "hackernews"
    label = "Hacker News"
    description = "Algolia 官方 API：72 小时内的 Ask HN 和高分故事，以及含“I wish there was”等痛点短语的评论（关闭拼写容错）"
    high_engagement_comments = 80

    # Exact phrases, typo tolerance off: Algolia's fuzzy matching made claude-pp's counts unusable.
    pain_phrases = (
        "I wish there was",
        "is there a tool",
        "my workaround is",
        "I have to manually",
        "there has to be a better way",
        "we built an internal tool",
        "spreadsheet to track",
        "I would pay for",
        "we ended up building",
    )
    phrase_hits = 50
    story_min_points = 150

    def fetch(self, since: datetime) -> list[RawItem]:
        after = f"created_at_i>{int(since.timestamp())}"
        hits = self.get_json(f"{API}/search_by_date", {"tags": "ask_hn", "numericFilters": after, "hitsPerPage": 100})["hits"]
        hits += self.get_json(
            f"{API}/search",
            {"tags": "story", "numericFilters": f"{after},points>{self.story_min_points}", "hitsPerPage": 50},
        )["hits"]
        for phrase in self.pain_phrases:
            hits += self.get_json(
                f"{API}/search_by_date",
                {"query": f'"{phrase}"', "tags": "comment", "typoTolerance": "false", "numericFilters": after,
                 "hitsPerPage": self.phrase_hits},
            )["hits"]
        return [self._parse(hit) for hit in hits]

    def fetch_thread(self, item: RawItem) -> list[str]:
        root = self.get_json(f"{API}/items/{item.external_id}")
        # The items endpoint has no comment scores; reply count is the best proxy for "sparked discussion".
        children = sorted(root.get("children") or [], key=lambda child: -len(child.get("children") or []))
        return [strip_html(child.get("text")) for child in children]

    def _parse(self, hit: dict) -> RawItem:
        is_comment = "comment" in hit.get("_tags", [])
        return RawItem(
            source=self.name,
            external_id=hit["objectID"],
            url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
            title=(hit.get("story_title") if is_comment else hit.get("title")) or "",
            body=self.clip(strip_html(hit.get("comment_text") if is_comment else hit.get("story_text"))),
            created_at=datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
            score=hit.get("points") or 0,
            comments=hit.get("num_comments") or 0,
            tags=["comment"] if is_comment else [tag for tag in hit.get("_tags", []) if tag in ("ask_hn", "show_hn", "story")],
        )
