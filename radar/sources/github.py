"""GitHub issues, scoped to specific repos.

claude-pp found site-wide issue search drowned in game mods and firmware; only repo-scoped
queries against tools that paying users depend on are worth the rate limit.
"""

import os
from datetime import datetime

from radar.models import RawItem
from radar.sources.base import SourceAdapter

API = "https://api.github.com"


class GitHubIssues(SourceAdapter):
    name = "github"
    label = "GitHub Issues"
    description = "限定仓库的新 issue，按反应数排序：n8n、Claude Code、Codex、LiteLLM、MCP servers、certbot、win-acme、Langfuse"
    high_engagement_comments = 25
    thread_chars = 500

    repos = (
        "n8n-io/n8n",
        "anthropics/claude-code",
        "openai/codex",
        "BerriAI/litellm",
        "modelcontextprotocol/servers",
        "certbot/certbot",
        "win-acme/win-acme",
        "langfuse/langfuse",
    )
    per_repo = 30

    def __init__(self) -> None:
        super().__init__()
        self._token = os.environ.get("GITHUB_TOKEN")
        # Unauthenticated search allows 10 requests/minute; authenticated allows 30.
        self.request_interval_seconds = 2.2 if self._token else 6.5

    def fetch(self, since: datetime) -> list[RawItem]:
        items = []
        for repo in self.repos:
            result = self.get_json(
                f"{API}/search/issues",
                {"q": f"repo:{repo} is:issue created:>={since.date().isoformat()}", "sort": "reactions",
                 "order": "desc", "per_page": self.per_repo},
                headers=self._headers(),
            )
            items += [self._parse(repo, issue) for issue in result["items"]]
        return items

    def fetch_thread(self, item: RawItem) -> list[str]:
        repo, number = item.external_id.split("#")
        comments = self.get_json(f"{API}/repos/{repo}/issues/{number}/comments", {"per_page": 50}, headers=self._headers())
        ranked = sorted(comments, key=lambda comment: -(comment.get("reactions") or {}).get("total_count", 0))
        return [" ".join((comment.get("body") or "").split()) for comment in ranked]

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _parse(self, repo: str, issue: dict) -> RawItem:
        return RawItem(
            source=self.name,
            external_id=f"{repo}#{issue['number']}",
            url=issue["html_url"],
            title=issue["title"],
            body=self.clip(" ".join((issue.get("body") or "").split())),
            created_at=datetime.fromisoformat(issue["created_at"]),
            score=(issue.get("reactions") or {}).get("total_count", 0),
            comments=issue.get("comments") or 0,
            tags=[repo, *[label["name"] for label in issue.get("labels", [])][:5]],
        )
