"""Stack Exchange API 2.3.

Software Recommendations is close to a pure "is there a tool for X" feed; the other sites
are filtered by workaround language to keep plain how-to questions out.
"""

from datetime import datetime, timezone

from radar.models import RawItem
from radar.sources.base import SourceAdapter, strip_html

API = "https://api.stackexchange.com/2.3"


class StackExchange(SourceAdapter):
    name = "stackexchange"
    label = "Stack Exchange"
    description = "Software Recommendations、Web Applications 的全部新问题，Super User 里提到 workaround / manually 的问题"
    high_engagement_comments = 8
    request_interval_seconds = 0.5

    # (site, free-text query or None for everything new on the site)
    queries = (
        ("softwarerecs", None),
        ("webapps", None),
        ("superuser", "workaround"),
        ("superuser", "manually"),
    )
    page_size = 50

    def fetch(self, since: datetime) -> list[RawItem]:
        items = []
        for site, query in self.queries:
            params = {"order": "desc", "sort": "creation", "site": site, "pagesize": self.page_size,
                      "filter": "withbody", "fromdate": int(since.timestamp())}
            if query:
                params["q"] = query
            items += [self._parse(site, question) for question in self.get_json(f"{API}/search/advanced", params)["items"]]
        return items

    def fetch_thread(self, item: RawItem) -> list[str]:
        site, question_id = item.external_id.split(":")
        answers = self.get_json(
            f"{API}/questions/{question_id}/answers",
            {"site": site, "order": "desc", "sort": "votes", "filter": "withbody"},
        )["items"]
        return [strip_html(answer.get("body")) for answer in answers]

    def _parse(self, site: str, question: dict) -> RawItem:
        return RawItem(
            source=self.name,
            external_id=f"{site}:{question['question_id']}",
            url=question["link"],
            title=strip_html(question["title"]),
            body=self.clip(strip_html(question.get("body"))),
            created_at=datetime.fromtimestamp(question["creation_date"], tz=timezone.utc),
            score=question.get("score") or 0,
            comments=question.get("answer_count") or 0,
            tags=[site, *question.get("tags", [])[:5]],
        )
