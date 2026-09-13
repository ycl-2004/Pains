"""Write the single JSON file the static site reads. Only paraphrases, links and scores leave the pipeline."""

import json
from datetime import datetime, timezone
from pathlib import Path

from radar.models import Ledger, RunReport
from radar.registry import SOURCES
from radar.scoring import DIMENSIONS, LEVELS, SOLUTION_CLASSES
from radar.evidence import qualification

MAX_RUNS_EXPORTED = 30


def load_runs(runs_dir: Path) -> list[RunReport]:
    return [RunReport.model_validate_json(path.read_text(encoding="utf-8")) for path in sorted(runs_dir.glob("*.json"))]


def export_site(ledger: Ledger, runs_dir: Path, out_dir: Path) -> Path:
    runs = load_runs(runs_dir)[-MAX_RUNS_EXPORTED:]
    site = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "last_run_id": ledger.last_run_id,
        "rubric": {"dimensions": DIMENSIONS, "classes": SOLUTION_CLASSES, "levels": LEVELS},
        "sources": [{"name": s.name, "label": s.label, "description": s.description,
                     "business_source": s.business_source, "coverage": s.coverage_note} for s in SOURCES],
        "clusters": [{**cluster.model_dump(mode="json"), "qualification": qualification(cluster)} for cluster in ledger.clusters],
        "signals": [signal.model_dump(mode="json") for signal in ledger.signals],
        "merge_log": [record.model_dump(mode="json") for record in ledger.merge_log],
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
    target.write_text(json.dumps(site, ensure_ascii=False, indent=1), encoding="utf-8")
    return target
