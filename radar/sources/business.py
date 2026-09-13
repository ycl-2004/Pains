"""Public business-community RSS feeds; bounded samples, never authenticated scraping.

Discourse feed contract: https://meta.discourse.org/t/finding-discourse-rss-feeds/264134
WordPress plugin support feeds: https://meta.trac.wordpress.org/ticket/2204
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from radar.models import RawItem
from radar.sources.base import SourceAdapter, strip_html
from radar.privacy import redact

CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"


class BusinessFeed(SourceAdapter):
    business_source = True
    high_engagement_comments = 5
    request_interval_seconds = 1.5

    def __init__(self, name: str, label: str, base_url: str, feeds: tuple[str, ...], *, discourse: bool = False):
        super().__init__()
        self.name, self.label, self.base_url, self.feeds = name, label, base_url, feeds
        self.discourse = discourse
        self.description = f"{label}：业务流程、订单、集成与手工成本；公开 RSS 有限条数采样。"

    def fetch(self, since: datetime) -> list[RawItem]:
        items, failures = [], []
        for feed in self.feeds:
            try:
                root = ET.fromstring(self.get_bytes(f"{self.base_url}{feed}"))
                for node in root.findall("./channel/item"):
                    item = self._parse(node)
                    if item:
                        items.append(item)
            except Exception as error:
                failures.append(f"{feed}: {type(error).__name__}")
        self.warnings.extend(failures)
        self.degraded = bool(failures)
        if len(failures) == len(self.feeds):
            raise RuntimeError("; ".join(failures))
        return items

    def _parse(self, node) -> RawItem | None:
        url, date = node.findtext("link", "").strip(), node.findtext("pubDate", "")
        if not date or urlsplit(url).hostname != urlsplit(self.base_url).hostname:
            return None
        created = parsedate_to_datetime(date).astimezone(timezone.utc)
        return RawItem(source=self.name, external_id=url.rstrip("/"), url=url,
                       title=strip_html(node.findtext("title")),
                       body=self.clip(strip_html(node.findtext(CONTENT) or node.findtext("description"))),
                       created_at=created, tags=["business", *[n.text for n in node.findall("category") if n.text]])

    def prefilter(self, items):
        # Support forums already have topical focus; don't discard short operational questions.
        return items

    def attach_thread(self, item):
        if not self.discourse:
            return super().attach_thread(item)
        # Topic JSON gives creation/last activity and solved state, unlike a topic-list RSS.
        topic = self.get_json(f"{item.url.rstrip('/')}.json")
        posts = topic.get("post_stream", {}).get("posts", [])
        first = next((p for p in posts if p.get("post_number") == 1), None)
        replies = [strip_html(p.get("cooked")) for p in posts if p.get("post_number") != 1]
        return item.model_copy(update={
            "body": self.clip(strip_html(first.get("cooked"))) if first else item.body,
            "thread": [redact(r)[:self.thread_chars] for r in replies[-self.thread_limit:]],
            "created_at": datetime.fromisoformat(topic["created_at"]),
            "updated_at": datetime.fromisoformat(topic.get("last_posted_at") or topic["created_at"]),
            "resolved": bool(topic.get("accepted_answer") or topic.get("has_accepted_answer"))
                        if "accepted_answer" in topic or "has_accepted_answer" in topic else None,
            "comments": max(0, topic.get("posts_count", 1) - 1),
        })

    def fetch_thread(self, item):
        root = ET.fromstring(self.get_bytes(f"{item.url.rstrip('/')}/feed/"))
        return [strip_html(n.findtext(CONTENT) or n.findtext("description"))
                for n in root.findall("./channel/item")][-self.thread_limit:]
