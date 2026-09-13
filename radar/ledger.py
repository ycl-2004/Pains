"""Ledger persistence and the rules for folding one run's analysis into it."""

import re
from datetime import datetime, timezone
from pathlib import Path

from radar.models import (
    AnalysisResult,
    Cluster,
    ClusterChange,
    ClusterUpdate,
    Evidence,
    Ledger,
    ScoreEvent,
    Signal,
    SolutionCheck,
)
from radar.scoring import REVIVE_OVERALL, clamp_scores

NEW_CLUSTER = "NEW"


def load(path: Path) -> Ledger:
    return Ledger.model_validate_json(path.read_text(encoding="utf-8"))


def save(ledger: Ledger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)


def init_from_seed(seed_path: Path, ledger_path: Path, *, force: bool = False) -> bool:
    if ledger_path.exists() and not force:
        return False
    save(load(seed_path), ledger_path)
    return True


def snapshot(ledger: Ledger, run_id: str, directory: Path) -> Path:
    target = directory / f"{run_id}.json"
    save(ledger, target)
    return target


def next_id(existing: list[str], prefix: str) -> str:
    numbers = [int(match.group(1)) for value in existing if (match := re.fullmatch(rf"{prefix}-(\d+)", value))]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def apply_analysis(ledger: Ledger, result: AnalysisResult, run_id: str, today: str) -> tuple[list[ClusterChange], list[str], list[str]]:
    """Fold an analysis into the ledger in place. Returns (changes, new signal ids, top opportunity ids)."""
    by_id = {cluster.id: cluster for cluster in ledger.clusters}
    detected_this_run: set[str] = set()
    new_names: dict[str, str] = {}
    changes: list[ClusterChange] = []

    for update in result.updates:
        cluster = by_id.get(update.cluster_id)
        if cluster is None:
            cluster = _create_cluster(ledger, update, run_id, today)
            by_id[cluster.id] = cluster
            new_names[update.name] = cluster.id
            detected_this_run.add(cluster.id)
            changes.append(ClusterChange(cluster_id=cluster.id, action="created", overall_before=None,
                                         overall_after=cluster.scores.overall, reason=update.score_reason))
            continue
        before = cluster.scores.overall if cluster.scores else None
        _merge_update(cluster, update, run_id, today, count_detection=cluster.id not in detected_this_run)
        if any(evidence.counts_as_demand for evidence in update.new_evidence):
            detected_this_run.add(cluster.id)
        changes.append(ClusterChange(cluster_id=cluster.id, action="updated", overall_before=before,
                                     overall_after=cluster.scores.overall, reason=update.score_reason))

    signal_ids = []
    for draft in result.new_signals:
        signal = Signal(id=next_id([s.id for s in ledger.signals], "SIG"), title=draft.title, why_watch=draft.why_watch,
                        watch_next=draft.watch_next, evidence=draft.evidence, first_detected=today,
                        last_detected=today, origin=["pipeline"])
        ledger.signals.append(signal)
        signal_ids.append(signal.id)

    top_ids = []
    for ref in result.top_opportunity_ids:
        resolved = new_names.get(ref.removeprefix(f"{NEW_CLUSTER}:"), ref)
        if resolved in by_id and resolved not in top_ids:
            top_ids.append(resolved)

    ledger.last_run_id = run_id
    ledger.updated_at = datetime.now(timezone.utc)
    return changes, signal_ids, top_ids[:3]


def apply_solution_check(cluster: Cluster, check: SolutionCheck, today: str) -> None:
    cluster.existing_solutions = check.existing_solutions or cluster.existing_solutions
    cluster.why_insufficient = check.why_insufficient or cluster.why_insufficient
    cluster.solution_class = check.solution_class
    cluster.evidence = _merge_evidence(cluster.evidence, check.sources)
    cluster.solution_checked_at = today


def _create_cluster(ledger: Ledger, update: ClusterUpdate, run_id: str, today: str) -> Cluster:
    scores = clamp_scores(update.scores)
    cluster = Cluster(
        id=next_id([c.id for c in ledger.clusters], "OP"),
        name=update.name,
        status="active",
        industry=update.industry,
        who=update.who,
        problem=update.problem,
        solution_class=update.solution_class,
        pain_confidence=update.pain_confidence,
        gap_confidence=update.gap_confidence,
        scores=scores,
        evidence=_merge_evidence([], update.new_evidence),
        workaround=update.workaround,
        existing_solutions=update.existing_solutions,
        why_insufficient=update.why_insufficient,
        root_cause=update.root_cause,
        why_now=update.why_now,
        opportunity_hypothesis=update.opportunity_hypothesis,
        contrarian=update.contrarian,
        next_validation=update.next_validation,
        first_detected=today,
        last_detected=today,
        score_history=[ScoreEvent(run_id=run_id, date=today, overall=scores.overall, reason=update.score_reason)],
        origin=["pipeline"],
    )
    ledger.clusters.append(cluster)
    return cluster


def _merge_update(cluster: Cluster, update: ClusterUpdate, run_id: str, today: str, *, count_detection: bool) -> None:
    for field in ("name", "who", "problem", "industry", "workaround", "why_insufficient", "root_cause", "why_now",
                  "opportunity_hypothesis"):
        value = getattr(update, field).strip()
        if value:
            setattr(cluster, field, value)
    cluster.existing_solutions = _merge_list(cluster.existing_solutions, update.existing_solutions)
    cluster.contrarian = _merge_list(cluster.contrarian, update.contrarian)
    if update.next_validation:
        cluster.next_validation = update.next_validation
    cluster.evidence = _merge_evidence(cluster.evidence, update.new_evidence)
    cluster.solution_class = update.solution_class
    cluster.pain_confidence = update.pain_confidence
    cluster.gap_confidence = update.gap_confidence
    cluster.scores = clamp_scores(update.scores)

    # Re-reading an old URL or a vendor pitch is not a new detection (codex-pp independence rule).
    if count_detection and any(evidence.counts_as_demand for evidence in update.new_evidence):
        cluster.detected_runs += 1
        cluster.last_detected = today
    if cluster.status == "demoted" and cluster.scores.overall >= REVIVE_OVERALL:
        cluster.status = "watch"
        cluster.status_reason = f"{today} 新证据让分数回到 {cluster.scores.overall}，从降级转为观察，待复核。原降级理由：{cluster.status_reason}"

    last = cluster.score_history[-1] if cluster.score_history else None
    event = ScoreEvent(run_id=run_id, date=today, overall=cluster.scores.overall, reason=update.score_reason)
    if last and last.run_id == run_id:
        cluster.score_history[-1] = event
    else:
        cluster.score_history.append(event)


def _merge_list(old: list[str], new: list[str]) -> list[str]:
    return old + [value for value in new if value.strip() and value not in old]


def _merge_evidence(old: list[Evidence], new: list[Evidence]) -> list[Evidence]:
    urls = {evidence.url for evidence in old}
    merged = list(old)
    for evidence in new:
        if evidence.url not in urls:
            urls.add(evidence.url)
            merged.append(evidence)
    return merged
