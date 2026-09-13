"""Bounded weekly revisit of supported, previously cited demand threads."""

import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, parse_qs

from radar import config
from radar.models import RawItem
from radar.registry import get_source


def item_for(evidence):
    parts = urlsplit(evidence.url)
    host, path = parts.hostname, parts.path
    source, external_id = None, None
    if host == "news.ycombinator.com":
        source, external_id = "hackernews", parse_qs(parts.query).get("id", [None])[0]
    elif host == "github.com" and (match := re.fullmatch(r"/([^/]+/[^/]+)/issues/(\d+)/?", path)):
        source, external_id = "github", f"{match[1]}#{match[2]}"
    elif host in {"community.make.com", "community.n8n.io"} and "/t/" in path:
        source = "make" if host == "community.make.com" else "n8n"
        external_id = evidence.url.rstrip("/")
    elif host == "wordpress.org" and path.startswith("/support/topic/"):
        source, external_id = "wordpress", evidence.url.rstrip("/")
    if not source or not external_id or not evidence.date:
        return None
    try:
        created = datetime.fromisoformat(evidence.date).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return RawItem(source=source, external_id=external_id, url=evidence.url, title="已收录讨论复查",
                   body=evidence.paraphrase, created_at=created)


def revisit(ledger, now, limit=5):
    path = config.DATA_DIR / "reviewed.json"
    reviewed = json.loads(path.read_text()) if path.exists() else {}
    reviewed = {key: ({"last_success": value, "last_attempt": value,
                       "next_retry": (datetime.fromisoformat(value) + timedelta(days=config.REVISIT_DAYS)).isoformat()}
                      if isinstance(value, str) else value) for key, value in reviewed.items()}
    candidates = {}
    for cluster in ledger.clusters:
        if cluster.status == "demoted":
            continue
        for evidence in cluster.evidence:
            if evidence.counts_as_demand and (item := item_for(evidence)):
                retry = reviewed.get(item.key, {}).get("next_retry")
                if not retry or now >= datetime.fromisoformat(retry):
                    candidates[item.key] = item
    items, notes = [], []
    for item in sorted(candidates.values(), key=lambda i: reviewed.get(i.key, {}).get("last_attempt", ""))[:limit]:
        state = reviewed.setdefault(item.key, {})
        state["last_attempt"] = now.isoformat()
        try:
            refreshed = get_source(item.source).attach_thread(item)
            items.append(refreshed)
            state.update(failures=0, outcome="fetched", next_retry=(now + timedelta(days=1)).isoformat())
        except Exception as error:
            failures = state.get("failures", 0) + 1
            state.update(failures=failures, outcome="fetch_failed",
                         next_retry=(now + timedelta(days=min(2 ** min(failures - 1, 3), 7))).isoformat())
            notes.append(f"旧帖复查失败 {item.key}: {type(error).__name__}")
    return items, notes, reviewed
