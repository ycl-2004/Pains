"""Bounded storage maintenance for the local and CI data directories."""

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from radar import config
from radar.models import Ledger


_RUN_STAMP = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{4,6})(?:-(\d{1,6}))?$")


def _parse_stamp(value: str) -> datetime | None:
    match = _RUN_STAMP.fullmatch(value)
    if not match:
        return None
    day, clock, fraction = match.groups()
    try:
        parsed = datetime.strptime(f"{day}-{clock}", "%Y-%m-%d-%H%M%S" if len(clock) == 6 else "%Y-%m-%d-%H%M")
    except ValueError:
        return None
    if fraction:
        parsed = parsed.replace(microsecond=int(fraction.ljust(6, "0")))
    return parsed.replace(tzinfo=timezone.utc)


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return None


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _activity_date(value: str | None) -> date | None:
    return _parse_date(value) if value else None


def _cluster_activity(cluster) -> date | None:
    values = [
        _activity_date(cluster.last_detected),
        _activity_date(cluster.solution_checked_at),
        *(_activity_date(event.date) for event in cluster.score_history),
    ]
    return max((value for value in values if value), default=None)


def prune_ledger(ledger: Ledger, now: datetime | None = None) -> dict[str, int]:
    """Drop stale terminal records and cap per-cluster score history in place."""

    now = now or datetime.now(timezone.utc)
    archive_cutoff = now.date() - timedelta(days=config.ARCHIVE_RETENTION_DAYS)
    signal_cutoff = now.date() - timedelta(days=config.SIGNAL_RETENTION_DAYS)
    before_clusters = len(ledger.clusters)
    ledger.clusters[:] = [
        cluster for cluster in ledger.clusters
        if cluster.status != "demoted" or (_cluster_activity(cluster) or now.date()) >= archive_cutoff
    ]
    before_signals = len(ledger.signals)
    ledger.signals[:] = [
        signal for signal in ledger.signals
        if (_activity_date(signal.last_detected) or now.date()) >= signal_cutoff
    ]
    trimmed_histories = 0
    for cluster in ledger.clusters:
        if len(cluster.score_history) > config.MAX_SCORE_HISTORY:
            cluster.score_history[:] = cluster.score_history[-config.MAX_SCORE_HISTORY:]
            trimmed_histories += 1
    return {
        "clusters": before_clusters - len(ledger.clusters),
        "signals": before_signals - len(ledger.signals),
        "score_histories": trimmed_histories,
    }


def _prune_timestamped_files(directory: Path, cutoff: datetime) -> int:
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.glob("*.json"):
        stamp = _parse_stamp(path.stem)
        if stamp and stamp < cutoff:
            path.unlink()
            removed += 1
    return removed


def _prune_date_directories(directory: Path, cutoff: date) -> int:
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.iterdir():
        if not path.is_dir():
            continue
        stamped = _parse_date(path.name)
        if stamped and stamped < cutoff:
            for child in path.rglob("*"):
                if child.is_file() or child.is_symlink():
                    child.unlink()
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            path.rmdir()
            removed += 1
    return removed


def _prune_mtime_files(directory: Path, cutoff: datetime) -> int:
    if not directory.exists():
        return 0
    removed = 0
    for path in directory.rglob("*.json"):
        if path.is_file() and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
            path.unlink()
            removed += 1
    return removed


def prune_runtime_data(now: datetime | None = None) -> dict[str, int]:
    """Prune bounded artifacts after a run; unknown filenames are kept safe by default."""

    now = now or datetime.now(timezone.utc)
    return {
        "raw_directories": _prune_date_directories(config.RAW_DIR, now.date() - timedelta(days=config.RAW_RETENTION_DAYS)),
        "runs": _prune_timestamped_files(config.RUNS_DIR, now - timedelta(days=config.RUN_RETENTION_DAYS)),
        "history": _prune_timestamped_files(config.LEDGER_HISTORY_DIR, now - timedelta(days=config.HISTORY_RETENTION_DAYS)),
        "audit": _prune_mtime_files(config.AUDIT_DIR, now - timedelta(days=config.AUDIT_RETENTION_DAYS)),
    }


def prune_reviewed(path: Path, now: datetime | None = None) -> bool:
    """Remove old revisit bookkeeping while preserving malformed/undated entries."""

    if not path.exists():
        return False
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=config.REVIEWED_RETENTION_DAYS)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    kept = {}
    for key, value in payload.items():
        if isinstance(value, str):
            parsed = _parse_datetime(value)
            if parsed is None or parsed >= cutoff:
                kept[key] = value
            continue
        if not isinstance(value, dict):
            kept[key] = value
            continue
        stamps = []
        for field in ("last_attempt", "last_success", "next_retry"):
            if (parsed := _parse_datetime(value.get(field))):
                stamps.append(parsed)
        if not stamps or max(stamps) >= cutoff:
            kept[key] = value
    if kept == payload:
        return False
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return True
