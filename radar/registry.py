"""Source registry: adding a collector means writing its adapter and adding one line here."""

from radar.sources.base import SourceAdapter
from radar.sources.github import GitHubIssues
from radar.sources.hackernews import HackerNews
from radar.sources.stackexchange import StackExchange
from radar.sources.v2ex import V2EX

SOURCES: tuple[SourceAdapter, ...] = (
    HackerNews(),
    GitHubIssues(),
    V2EX(),
    StackExchange(),
)


def get_source(name: str) -> SourceAdapter:
    for source in SOURCES:
        if source.name == name:
            return source
    raise KeyError(f"unknown source {name!r}; registered: {', '.join(s.name for s in SOURCES)}")
