"""Contract for public-source collectors.

Shared mechanics live here: polite HTTP with retry, the time window, the pain-language
prefilter and in-run dedupe. Each adapter declares its queries as class attributes and
implements only fetching and parsing its own payloads.
"""

import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from html.parser import HTMLParser

from radar.models import RawItem

USER_AGENT = "pain-radar/0.1 (personal research; read-only)"

# Adapted from claude-pp's first run: deliberately broad, because the goal of this step is
# not to miss anything. Judging happens later in triage.
PAIN_PATTERN = re.compile(
    r"how do (you|i|we)|anyone|is there (a|any) (tool|way|app)|tool|software|manual|tired|frustrat"
    r"|alternative|wish|hate|spreadsheet|automat|struggl|problem|nightmare|best way|recommend"
    r"|annoy|broke|expensive|pricing|lost|keeps|scam|fraud|workaround|deprecat|migrat|silent"
    r"|pay for|waste|\?|？|有没有|怎么|求推荐|太贵|手动|手工|麻烦|替代|吐槽|踩坑|痛点|崩溃|每次都|求助",
    re.IGNORECASE,
)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(markup: str | None) -> str:
    extractor = _TextExtractor()
    extractor.feed(markup or "")
    extractor.close()
    return re.sub(r"\s+", " ", " ".join(extractor.parts)).strip()


class SourceAdapter(ABC):
    name: str
    label: str
    description: str  # shown on the site's method page
    # Items with at least this many comments/replies skip the keyword prefilter:
    # heated threads often have no pain words in the title.
    high_engagement_comments: int
    request_interval_seconds: float = 0.0
    thread_limit: int = 8
    body_chars: int = 1500
    thread_chars: int = 400

    def __init__(self) -> None:
        self._last_request = 0.0

    def collect(self, now: datetime, window: timedelta) -> list[RawItem]:
        since = now - window
        items = [item for item in self.fetch(since) if item.created_at >= since]
        return dedupe(items)

    def prefilter(self, items: list[RawItem]) -> list[RawItem]:
        return [
            item
            for item in items
            if item.comments >= self.high_engagement_comments
            or PAIN_PATTERN.search(f"{item.title} {item.body[:500]}")
        ]

    def attach_thread(self, item: RawItem) -> RawItem:
        replies = self.fetch_thread(item)
        return item.model_copy(update={"thread": [r[: self.thread_chars] for r in replies[: self.thread_limit] if r]})

    @abstractmethod
    def fetch(self, since: datetime) -> list[RawItem]:
        """Return candidate items created at or after `since` (extra older items are filtered out by collect)."""

    @abstractmethod
    def fetch_thread(self, item: RawItem) -> list[str]:
        """Return the most-engaged replies as plain text, best first."""

    def get_json(self, url: str, params: dict[str, str | int] | None = None, headers: dict[str, str] | None = None):
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", **(headers or {})}
        )
        for attempt in range(3):
            self._throttle()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    payload = response.read()
                    if response.headers.get("Content-Encoding") == "gzip":
                        payload = gzip.decompress(payload)
                    return json.loads(payload)
            except urllib.error.HTTPError as error:
                if error.code not in RETRYABLE_STATUS or attempt == 2:
                    raise
                time.sleep(float(error.headers.get("Retry-After") or 2 ** (attempt + 1)))
            except urllib.error.URLError:
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError("unreachable")

    def _throttle(self) -> None:
        wait = self.request_interval_seconds - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def clip(self, text: str) -> str:
        return text[: self.body_chars]


def dedupe(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    unique = []
    for item in items:
        if item.key not in seen:
            seen.add(item.key)
            unique.append(item)
    return unique
