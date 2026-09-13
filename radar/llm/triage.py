"""Stage 1: a cheap batch judgment per item — is this a concrete, codable pain point?"""

import json
from collections.abc import Sequence, Callable
from collections import Counter

from radar import config
from radar.llm.client import LLM, BudgetExceeded, StageFailed, load_prompt
from radar.privacy import redact
from radar.models import RawItem, TriageResult, TriageVerdict


def run_triage(
    llm: LLM,
    items: list[RawItem],
    *,
    routes: Sequence[str] = (),
    chunk_size: int = config.TRIAGE_CHUNK_SIZE,
    checkpoint: Callable | None = None,
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
        except BudgetExceeded as error:
            notes.append(f"triage 提前停止：{error}")
            break

        counts = Counter(v.key for v in result.verdicts)
        expected = {item.key for item in chunk}
        if set(counts) != expected or any(count != 1 for count in counts.values()):
            notes.append(f"triage 第 {start // chunk_size + 1} 批存在遗漏、重复或未知 key；异常条目保持未处理")
            if hasattr(llm, "discard_last_cache"):
                llm.discard_last_cache()
        verdicts = {verdict.key: verdict for verdict in result.verdicts}
        for item in chunk:
            verdict = verdicts.get(item.key)
            if verdict is None or counts[item.key] != 1:
                continue
            judged.append(item)
            if (verdict.is_pain_point and verdict.codable) or verdict.kind == "counterevidence" or verdict.needs_context:
                kept.append((item, verdict))
        if checkpoint:
            checkpoint(kept, judged, notes)
    return kept, judged, notes


def _payload(chunk: list[RawItem]) -> str:
    return json.dumps(
        [
            {
                "key": item.key,
                "source": item.source,
                "title": item.title,
                "body": redact(item.body),
                "top_replies": [redact(reply) for reply in item.thread[:5]],
                "resolved": item.resolved,
                "date": item.created_at.date().isoformat(),
                "engagement": f"{item.score} 分 / {item.comments} 评论",
                "tags": item.tags,
            }
            for item in chunk
        ],
        ensure_ascii=False,
    )
