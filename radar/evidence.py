"""Evidence identities and conservative eligibility; a thread is not a unique buyer."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from datetime import datetime, timedelta, timezone
from radar import config


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Evidence requires a public HTTP(S) URL")
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_") and k not in {"ref", "source"}]
    return urlunsplit(("https", parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def demand_evidence(cluster):
    return {canonical_url(e.url): e for e in cluster.evidence if e.counts_as_demand}


def eligible(cluster) -> bool:
    evidence = list(demand_evidence(cluster).values())
    return (cluster.solution_class in {"B", "C"} and cluster.scores is not None
            and cluster.scores.overall >= 5 and len(evidence) >= 2
            and any(e.kind in {"workaround", "buyer_request", "budget_or_payment"} for e in evidence))


def opportunity_rank(cluster):
    return (-bool(cluster.payment_evidence and cluster.buying_evidence_urls),
            -(cluster.scores.overall if cluster.scores else 0), -cluster.detected_runs)


def qualification(cluster, now=None):
    """Single candidate policy for reports and UI; date checks expire after day 7 UTC."""
    now = now or datetime.now(timezone.utc)
    reasons = []
    if cluster.status != "active":
        reasons.append("不是活跃状态")
    if not eligible(cluster):
        reasons.append("需求讨论、行为证据、方案缺口或综合分未达门槛")
    expires = None
    if cluster.solution_checked_at:
        try:
            checked = datetime.fromisoformat(cluster.solution_checked_at).date()
            expires = datetime.combine(checked + timedelta(days=config.SOLUTION_RECHECK_DAYS + 1), datetime.min.time(), timezone.utc)
            if not 0 <= (now.date() - checked).days <= config.SOLUTION_RECHECK_DAYS:
                reasons.append("方案核查已过期或日期在未来")
        except ValueError:
            reasons.append("方案核查日期无效")
    else:
        reasons.append("尚未核查现有方案")
    return {"eligible": not reasons, "reasons": reasons, "expires_at": expires.isoformat() if expires else None}
