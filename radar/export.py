"""Write the single JSON file the static site reads. Only paraphrases, links and scores leave the pipeline."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from radar.models import Ledger, RunReport
from radar.registry import SOURCES
from radar.scoring import DIMENSIONS, LEVELS, SOLUTION_CLASSES
from radar.evidence import qualification

MAX_RUNS_EXPORTED = 30
_INTERNAL_AGENT = re.compile(r"(?<![A-Za-z0-9])(?:claude|codex|agy)[-_]pp(?![A-Za-z0-9])", re.IGNORECASE)
_UNVERIFIED_MARKER = re.compile(r"(?:claude|codex|agy)[-_]pp[_-]recorded[_-]unverified|未复核原文", re.IGNORECASE)


def _public_text(value: str) -> str:
    """Remove internal run provenance before text reaches the public static site."""

    value = re.sub(r"[（(][^（）()]*?(?:claude|codex|agy)[-_]pp[^（）()]*?[）)]", "", value, flags=re.IGNORECASE)
    value = _INTERNAL_AGENT.sub("历史资料", value)
    value = re.sub(r"两个\s+agent", "多方判断", value, flags=re.IGNORECASE)
    value = re.sub(r"跨\s+agent", "跨团队", value, flags=re.IGNORECASE)
    return re.sub(r"[ \t]{2,}", " ", value).strip()


def _publicize(value):
    if isinstance(value, dict):
        return {key: _publicize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_publicize(item) for item in value]
    if isinstance(value, str):
        return _public_text(value)
    return value


def load_runs(runs_dir: Path) -> list[RunReport]:
    return [RunReport.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(runs_dir.glob("*.json"))]


def _public_cluster(cluster):
    payload = cluster.model_dump(mode="json")
    payload["origin"] = []
    if _INTERNAL_AGENT.search(payload.get("status_reason", "")):
        payload["status_reason"] = (
            "已归档：现有方案或证据暂不支持当前机会。"
            if payload.get("status") == "demoted" else "基于历史资料，等待进一步核查。"
        )
    for evidence in payload.get("evidence", []):
        if _UNVERIFIED_MARKER.search(f'{evidence.get("date_basis", "")} {evidence.get("paraphrase", "")}'):
            evidence["date_basis"] = "recorded_unverified"
            evidence["paraphrase"] = "历史记录，原文尚未完成复核。"
    for event in payload.get("score_history", []):
        if _INTERNAL_AGENT.search(event.get("reason", "")):
            event["reason"] = "历史评分记录"
    return {**payload, "qualification": qualification(cluster)}


def _public_signal(signal):
    payload = signal.model_dump(mode="json")
    payload["origin"] = []
    if _INTERNAL_AGENT.search(payload.get("why_watch", "")):
        payload["why_watch"] = "基于历史资料的观察，仍待验证。"
    if _INTERNAL_AGENT.search(payload.get("watch_next", "")):
        payload["watch_next"] = "继续观察是否出现新的独立来源。"
    for evidence in payload.get("evidence", []):
        if _UNVERIFIED_MARKER.search(f'{evidence.get("date_basis", "")} {evidence.get("paraphrase", "")}'):
            evidence["date_basis"] = "recorded_unverified"
            evidence["paraphrase"] = "历史记录，原文尚未完成复核。"
    return payload


def export_site(ledger: Ledger, runs_dir: Path, out_dir: Path) -> Path:
    runs = load_runs(runs_dir)[-MAX_RUNS_EXPORTED:]
    site = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_run_id": ledger.last_run_id,
        "rubric": {"dimensions": DIMENSIONS, "classes": SOLUTION_CLASSES, "levels": LEVELS},
        "sources": [{"name": s.name, "label": s.label, "description": s.description,
                     "business_source": s.business_source, "coverage": s.coverage_note} for s in SOURCES],
        "clusters": [_public_cluster(cluster) for cluster in ledger.clusters],
        "signals": [_public_signal(signal) for signal in ledger.signals],
        "merge_log": [],
        "runs": [
            {
                **run.model_dump(mode="json", exclude={"usage"}),
                "cost_usd": round(sum(record.cost_usd for record in run.usage), 4),
            }
            for run in reversed(runs)
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "radar.json"
    target.write_text(json.dumps(_publicize(site), ensure_ascii=False, indent=1), encoding="utf-8")
    return target
