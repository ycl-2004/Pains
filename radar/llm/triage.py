"""Stage 1: a cheap batch judgment per item — is this a concrete, codable pain point?"""

import json
from collections.abc import Sequence

from radar import config
from radar.llm.client import LLM, StageFailed, load_prompt
from radar.models import RawItem, TriageResult, TriageVerdict


def run_triage(
    llm: LLM,
    items: list[RawItem],
    *,
    routes: Sequence[str] = (),
    chunk_size: int = config.TRIAGE_CHUNK_SIZE,
) -> tuple[list[tuple[RawItem, TriageVerdict]], list[RawItem], list[str]]:
    """Return (kept items with verdicts, every item that received a verdict, notes)."""
    routes = tuple(routes) or config.TRIAGE_MODELS + config.FALLBACK_MODELS
    system = load_prompt("triage")
    kept: list[tuple[RawItem, TriageVerdict]] = []
    judged: list[RawItem] = []
    notes: list[str] = []

    for start in range(0, len(items), chunk_size):
        chunk = items[start : start + chunk_size]
        try:
            result = llm.complete("triage", system=system, user=f"<items>\n{_payload(chunk)}\n</items>",
                                  schema=TriageResult, routes=routes, max_tokens=16000)
        except StageFailed as error:
            # Skipped items stay unseen, so the next run judges them again.
            notes.append(f"triage 第 {start // chunk_size + 1} 批已跳过：{error}")
            continue

        verdicts = {verdict.key: verdict for verdict in result.verdicts}
        for item in chunk:
            verdict = verdicts.get(item.key)
            if verdict is None:
                continue
            judged.append(item)
            if verdict.is_pain_point and verdict.codable:
                kept.append((item, verdict))
    return kept, judged, notes


def _payload(chunk: list[RawItem]) -> str:
    return json.dumps(
        [
            {
                "key": item.key,
                "source": item.source,
                "title": item.title,
                "body": item.body,
                "date": item.created_at.date().isoformat(),
                "engagement": f"{item.score} 分 / {item.comments} 评论",
                "tags": item.tags,
            }
            for item in chunk
        ],
        ensure_ascii=False,
    )
