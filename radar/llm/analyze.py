"""Stage 2: fold the day's pain signals into the ledger, then check existing solutions with web search."""

import json
from collections.abc import Sequence

from radar import config
from radar.llm.client import LLM, StageFailed, load_prompt
from radar.evidence import canonical_url
from radar.privacy import redact
from radar.models import AnalysisResult, Cluster, Ledger, RawItem, SolutionCheck, TriageVerdict
from radar.scoring import render_rubric


def run_analysis(llm: LLM, ledger: Ledger, signals: list[tuple[RawItem, TriageVerdict]], *,
                 routes: Sequence[str] = ()) -> AnalysisResult:
    result = llm.complete(
        "analyze",
        system=load_prompt("analyze", rubric=render_rubric()),
        user=f"<ledger>\n{ledger_digest(ledger)}\n</ledger>\n\n<signals>\n{signals_payload(signals)}\n</signals>",
        schema=AnalysisResult,
        routes=tuple(routes) or config.ANALYZE_MODELS + config.FALLBACK_MODELS,
        max_tokens=32000,
    )
    supplied = {canonical_url(item.url): item for item, _ in signals}
    try:
        known = {c.id for c in ledger.clusters}
        if any(u.cluster_id != "NEW" and u.cluster_id not in known for u in result.updates):
            raise ValueError("Unknown cluster ID")
        evidence_groups = [u.new_evidence for u in result.updates] + [s.evidence for s in result.new_signals]
        evidence_groups += [s.evidence for s in result.signal_updates]
        for group in evidence_groups:
            for evidence in group:
                item = supplied.get(canonical_url(evidence.url))
                if item is None:
                    raise ValueError(f"Evidence URL was not supplied: {evidence.url}")
                evidence.url, evidence.source_key = item.url, item.key
                evidence.date, evidence.date_basis = item.created_at.date().isoformat(), "post_date"
                evidence.platform = item.source
                evidence.engagement = f"{item.score} 分 / {item.comments} 评论"
                evidence.paraphrase = redact(evidence.paraphrase)
        for update in result.updates:
            if any(canonical_url(url) not in supplied for url in update.buying_evidence_urls):
                raise ValueError("Buying evidence must cite supplied URLs")
            if update.payment_evidence and not update.buying_evidence_urls:
                raise ValueError("Payment claims need source URLs")
    except ValueError as error:
        if hasattr(llm, "discard_last_cache"):
            llm.discard_last_cache()
        raise StageFailed(f"证据校验失败：{error}") from error
    return result


def check_solutions(llm: LLM, cluster: Cluster, *, today: str, routes: Sequence[str] = ()) -> SolutionCheck:
    """Search competitors and native features. Only routes that support web search are tried."""
    result = llm.complete(
        "solution_check",
        system=load_prompt("solution_check", rubric=render_rubric(), today=today),
        user=cluster_brief(cluster),
        schema=SolutionCheck,
        routes=tuple(routes) or config.SOLUTION_MODELS + config.FALLBACK_MODELS,
        max_tokens=8000,
        web_search=True,
    )
    if not result.sources:
        raise StageFailed("方案核查没有可引用来源，不能标记为已核查")
    try:
        for source in result.sources:
            canonical_url(source.url)
            # Search findings are supply/counterevidence, never a second demand ingestion path.
            if source.kind not in {"official_doc", "news", "counterevidence"}:
                raise ValueError("Search sources must not increase demand counts")
    except ValueError as error:
        if hasattr(llm, "discard_last_cache"):
            llm.discard_last_cache()
        raise StageFailed(str(error)) from error
    return result


def ledger_digest(ledger: Ledger) -> str:
    clusters = []
    for cluster in ledger.clusters:
        view = {"id": cluster.id, "name": cluster.name, "status": cluster.status}
        view |= {"status_reason": cluster.status_reason, "buyer": cluster.buyer,
                 "payment_evidence": cluster.payment_evidence, "current_cost": cluster.current_cost,
                 "evidence": [{"url": e.url, "kind": e.kind, "date": e.date, "paraphrase": e.paraphrase}
                              for e in cluster.evidence[-12:]],
                 "solution_checked_at": cluster.solution_checked_at}
        if cluster.status == "demoted":
            view["status_reason"] = cluster.status_reason
        else:
            view |= {
                "who": cluster.who,
                "problem": cluster.problem,
                "solution_class": cluster.solution_class,
                "overall": cluster.scores.overall if cluster.scores else None,
                "pain_confidence": cluster.pain_confidence,
                "gap_confidence": cluster.gap_confidence,
                "evidence_urls": [evidence.url for evidence in cluster.evidence],
                "contrarian": cluster.contrarian,
            }
        clusters.append(view)
    signals = [{"id": s.id, "title": s.title, "why_watch": s.why_watch} for s in ledger.signals if s.status == "watching"]
    return json.dumps({"clusters": clusters, "signals": signals}, ensure_ascii=False)


def signals_payload(signals: list[tuple[RawItem, TriageVerdict]]) -> str:
    return json.dumps(
        [
            {
                "url": item.url,
                "source": item.source,
                "date": item.created_at.date().isoformat(),
                "title": item.title,
                "body": item.body[:800],
                "engagement": f"{item.score} 分 / {item.comments} 评论",
                "top_replies": item.thread[:5],
                "resolved": item.resolved,
                "refresh_scope": item.refresh_scope,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                "triage": verdict.model_dump(include={"who", "pain", "loss", "workaround", "kind"}),
            }
            for item, verdict in signals
        ],
        ensure_ascii=False,
    )


def cluster_brief(cluster: Cluster) -> str:
    return json.dumps(
        {
            "name": cluster.name,
            "who": cluster.who,
            "problem": cluster.problem,
            "workaround": cluster.workaround,
            "known_solutions": cluster.existing_solutions,
            "evidence": [evidence.paraphrase for evidence in cluster.evidence[:6]],
        },
        ensure_ascii=False,
    )
