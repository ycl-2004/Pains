"""Source registry: adding a collector means writing its adapter and adding one line here."""

from radar.sources.base import SourceAdapter
from radar.sources.github import GitHubIssues
from radar.sources.hackernews import HackerNews
from radar.sources.stackexchange import StackExchange
from radar.sources.v2ex import V2EX
from radar.sources.business import BusinessFeed

SOURCES: tuple[SourceAdapter, ...] = (
    BusinessFeed("make", "Make Community", "https://community.make.com", ("/latest.rss?order=created",), discourse=True),
    BusinessFeed("n8n", "n8n Community", "https://community.n8n.io", ("/latest.rss?order=created",), discourse=True),
    BusinessFeed("wordpress", "WooCommerce 商家支持", "https://wordpress.org",
                 ("/support/plugin/woocommerce/feed/", "/support/plugin/woocommerce-pdf-invoices-packing-slips/feed/")),
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
