"""Paths and tunables. Models, limits and windows can be overridden with environment variables."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
RUNS_DIR = DATA_DIR / "runs"
LEDGER_PATH = DATA_DIR / "ledger.json"
LEDGER_HISTORY_DIR = DATA_DIR / "ledger-history"
SEED_PATH = DATA_DIR / "seed" / "baseline-2026-09-12.json"
SEEN_PATH = DATA_DIR / "seen.json"
WEB_DATA_DIR = ROOT / "web" / "public" / "data"


def _env(name: str, default: str) -> str:
    # Unset GitHub Actions variables arrive as empty strings, so empty means "use the default".
    return os.environ.get(name) or default


def _models(name: str) -> tuple[str, ...]:
    """Comma-separated model routes in priority order, e.g. `vendor/model-a,vendor/model-b,deepseek:deepseek-flash`."""
    return tuple(part.strip() for part in (os.environ.get(name) or "").split(",") if part.strip())


WINDOW_HOURS = int(_env("RADAR_WINDOW_HOURS", "72"))

TRIAGE_MODELS = _models("RADAR_TRIAGE_MODELS")
ANALYZE_MODELS = _models("RADAR_ANALYZE_MODELS")
# Solution checks need web search, which only OpenRouter routes provide.
SOLUTION_MODELS = _models("RADAR_SOLUTION_MODELS") or ANALYZE_MODELS
# Appended to every stage's chain, e.g. `deepseek:deepseek-flash`.
FALLBACK_MODELS = _models("RADAR_FALLBACK_MODELS")

TRIAGE_CHUNK_SIZE = 20
# Deep-reading threads costs requests and tokens; only the most engaged survivors get it.
MAX_THREADS = int(_env("RADAR_MAX_THREADS", "40"))
MAX_ANALYZE_SIGNALS = 60
MAX_SOLUTION_CHECKS = 3
SOLUTION_CHECK_SEARCHES = 5
DEFAULT_MAX_COST_USD = float(_env("RADAR_MAX_COST_USD", "3"))
SOLUTION_RECHECK_DAYS = 7
RAW_RETENTION_DAYS = int(_env("RADAR_RAW_RETENTION_DAYS", "14"))
RUN_RETENTION_DAYS = int(_env("RADAR_RUN_RETENTION_DAYS", "90"))
HISTORY_RETENTION_DAYS = int(_env("RADAR_HISTORY_RETENTION_DAYS", "180"))
AUDIT_RETENTION_DAYS = int(_env("RADAR_AUDIT_RETENTION_DAYS", "14"))
REVIEWED_RETENTION_DAYS = int(_env("RADAR_REVIEWED_RETENTION_DAYS", "180"))
ARCHIVE_RETENTION_DAYS = int(_env("RADAR_ARCHIVE_RETENTION_DAYS", "365"))
SIGNAL_RETENTION_DAYS = int(_env("RADAR_SIGNAL_RETENTION_DAYS", "90"))
MAX_SCORE_HISTORY = int(_env("RADAR_MAX_SCORE_HISTORY", "52"))
AUDIT_DIR = DATA_DIR / "audit"
REVISIT_DAYS = 7
MAX_CONTEXT_THREADS = 8
