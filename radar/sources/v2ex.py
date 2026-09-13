"""V2EX public v1 API: the Chinese-language source all three original runs lacked."""

from datetime import datetime, timezone

from radar.models import RawItem
from radar.sources.base import SourceAdapter

API = "https://www.v2ex.com/api"


class V2EX(SourceAdapter):
    name = "v2ex"
    label = "V2EX"
    description = "公开 v1 接口：最新、最热，以及问与答、分享创造、奇思妙想、程序员节点"
    high_engagement_comments = 40
    # The v1 API is rate limited per IP (roughly 120 requests/hour).
    request_interval_seconds = 1.0

    nodes = ("qna", "create", "ideas", "programmer")

    def fetch(self, since: datetime) -> list[RawItem]:
        topics = self.get_json(f"{API}/topics/latest.json") + self.get_json(f"{API}/topics/hot.json")
        for node in self.nodes:
            topics += self.get_json(f"{API}/topics/show.json", {"node_name": node})
        return [self._parse(topic) for topic in topics]

    def fetch_thread(self, item: RawItem) -> list[str]:
        replies = self.get_json(f"{API}/replies/show.json", {"topic_id": item.external_id})
        ranked = sorted(replies, key=lambda reply: -(reply.get("thanks") or 0))
        return [" ".join((reply.get("content") or "").split()) for reply in ranked]

    def _parse(self, topic: dict) -> RawItem:
        node = (topic.get("node") or {}).get("name", "")
        return RawItem(
            source=self.name,
            external_id=str(topic["id"]),
            url=topic["url"],
            title=topic["title"],
            body=self.clip(" ".join((topic.get("content") or "").split())),
            created_at=datetime.fromtimestamp(topic["created"], tz=timezone.utc),
            comments=topic.get("replies") or 0,
            tags=[node] if node else [],
        )
