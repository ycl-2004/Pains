"""Evidence identities and conservative eligibility; a thread is not a unique buyer."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
