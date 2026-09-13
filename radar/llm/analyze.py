"""Stage 2: fold the day's pain signals into the ledger, then check existing solutions with web search."""

import json
from collections.abc import Sequence

from radar import config
from radar.llm.client import LLM, load_prompt
from radar.models import AnalysisResult, Cluster, Ledger, RawItem, SolutionCheck, TriageVerdict
from radar.scoring import render_rubric


def run_analysis(llm: LLM, ledger: Ledger, signals: list[tuple[RawItem, TriageVerdict]], *,
                 routes: Sequence[str] = ()) -> AnalysisResult:
    return llm.complete(
        "analyze",
        system=load_prompt("analyze", rubric=render_rubric()),
        user=f"<ledger>\n{ledger_digest(ledger)}\n</ledger>\n\n<signals>\n{signals_payload(signals)}\n</signals>",
        schema=AnalysisResult,
        routes=tuple(routes) or config.ANALYZE_MODELS + config.FALLBACK_MODELS,
        max_tokens=32000,
    )


def check_solutions(llm: LLM, cluster: Cluster, *, today: str, routes: Sequence[str] = ()) -> SolutionCheck:
    """Search competitors and native features. Only routes that support web search are tried."""
    return llm.complete(
        "solution_check",
        system=load_prompt("solution_check", rubric=render_rubric(), today=today),
        user=cluster_brief(cluster),
        schema=SolutionCheck,
        routes=tuple(routes) or config.SOLUTION_MODELS + config.FALLBACK_MODELS,
        max_tokens=8000,
        web_search=True,
    )


def ledger_digest(ledger: Ledger) -> str:
    clusters = []
    for cluster in ledger.clusters:
        view = {"id": cluster.id, "name": cluster.name, "status": cluster.status}
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
