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
from radar.evidence import canonical_url, eligible, qualification

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
    # Validate the whole batch before mutating the durable state.
    for update in result.updates:
        if update.cluster_id != NEW_CLUSTER and update.cluster_id not in by_id:
            raise ValueError(f"Unknown cluster ID: {update.cluster_id}")
        if update.cluster_id == NEW_CLUSTER and (not update.name.strip() or not update.new_evidence):
            raise ValueError("New clusters need a name and source evidence")
    names = [u.name.strip().casefold() for u in result.updates if u.cluster_id == NEW_CLUSTER]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate new cluster names")
    for evidence in [e for u in result.updates for e in u.new_evidence] + [e for s in result.new_signals for e in s.evidence] + [e for s in result.signal_updates for e in s.evidence]:
        canonical_url(evidence.url)
    signal_by_id = {s.id: s for s in ledger.signals}
    new_refs = {f"NEW:{u.name}" for u in result.updates if u.cluster_id == NEW_CLUSTER}
    for update in result.signal_updates:
        if update.signal_id not in signal_by_id:
            raise ValueError(f"Unknown signal ID: {update.signal_id}")
        if update.status == "promoted" and update.cluster_id not in set(by_id) | new_refs:
            raise ValueError("Promoted signals need a valid cluster reference")
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
        detected = _merge_update(cluster, update, run_id, today, count_detection=cluster.id not in detected_this_run)
        if detected:
            detected_this_run.add(cluster.id)
        changes.append(ClusterChange(cluster_id=cluster.id, action="updated", overall_before=before,
                                     overall_after=cluster.scores.overall, reason=update.score_reason))

    signal_ids = []
    for draft in result.new_signals:
        duplicate = next((s for s in ledger.signals if s.title.strip().casefold() == draft.title.strip().casefold()), None)
        if duplicate:
            duplicate.evidence = _merge_evidence(duplicate.evidence, draft.evidence)
            continue
        signal = Signal(id=next_id([s.id for s in ledger.signals], "SIG"), title=draft.title, why_watch=draft.why_watch,
                        watch_next=draft.watch_next, evidence=draft.evidence, first_detected=today,
                        last_detected=today, origin=["pipeline"])
        ledger.signals.append(signal)
        signal_ids.append(signal.id)

    for update in result.signal_updates:
        signal = signal_by_id[update.signal_id]
        before = {canonical_url(e.url) for e in signal.evidence}
        signal.evidence = _merge_evidence(signal.evidence, update.evidence)
        if any(e.counts_as_demand and canonical_url(e.url) not in before for e in update.evidence):
            signal.detected_runs += 1
            signal.last_detected = today
        signal.why_watch = update.why_watch or signal.why_watch
        signal.watch_next = update.watch_next or signal.watch_next
        signal.status = update.status
        if update.status == "promoted":
            signal.promoted_to = new_names.get(update.cluster_id.removeprefix("NEW:"), update.cluster_id)

    top_ids = []
    for ref in result.top_opportunity_ids:
        resolved = new_names.get(ref.removeprefix(f"{NEW_CLUSTER}:"), ref)
        if resolved in by_id and qualification(by_id[resolved], datetime.fromisoformat(today).replace(tzinfo=timezone.utc))["eligible"] and resolved not in top_ids:
            top_ids.append(resolved)

    ledger.last_run_id = run_id
    ledger.updated_at = datetime.now(timezone.utc)
    consolidated = {}
    for change in changes:
        if change.cluster_id in consolidated:
            previous = consolidated[change.cluster_id]
            previous.overall_after, previous.reason = change.overall_after, change.reason
        else:
            consolidated[change.cluster_id] = change
    return list(consolidated.values()), signal_ids, top_ids[:3]


def apply_solution_check(cluster: Cluster, check: SolutionCheck, today: str, run_id: str = "solution-check") -> None:
    if not check.sources:
        raise ValueError("Solution checks need cited sources")
    for source in check.sources:
        canonical_url(source.url)
        if source.counts_as_demand:
            raise ValueError("Solution search must not create demand evidence")
    cluster.existing_solutions = check.existing_solutions or cluster.existing_solutions
    cluster.why_insufficient = check.why_insufficient or cluster.why_insufficient
    cluster.solution_class = check.solution_class
    cluster.evidence = _merge_evidence(cluster.evidence, check.sources)
    cluster.solution_checked_at = today
    if check.solution_class == "A":
        cluster.status = "demoted"
        cluster.status_reason = f"{today} 方案复查：{check.why_insufficient}"
        cluster.gap_confidence = "low"
        if cluster.scores:
            cluster.scores.overall = min(cluster.scores.overall, 4.0)
            cluster.scores.existing_solution_gap = min(cluster.scores.existing_solution_gap, 2)
            cluster.score_history.append(ScoreEvent(run_id=f"{run_id}:solution", date=today,
                                                    overall=cluster.scores.overall, reason=cluster.status_reason))
    elif eligible(cluster):
        cluster.status = "active"
        cluster.status_reason = f"{today} 已核查方案；属于待验证候选，不代表成交验证。"
    else:
        cluster.status = "watch"
        cluster.status_reason = "需求证据或方案缺口尚不足，继续观察。"


def _create_cluster(ledger: Ledger, update: ClusterUpdate, run_id: str, today: str) -> Cluster:
    scores = clamp_scores(update.scores)
    if not update.payment_evidence or not update.buying_evidence_urls:
        scores.willingness_to_pay = min(scores.willingness_to_pay, 4)
    cluster = Cluster(
        id=next_id([c.id for c in ledger.clusters], "OP"),
        name=update.name,
        short_title=update.short_title,
        status="watch",
        status_reason="新候选：等待独立帖子证据和现有方案核查。",
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
        buyer=update.buyer, payment_evidence=update.payment_evidence, current_cost=update.current_cost,
        buying_evidence_urls=update.buying_evidence_urls,
    )
    ledger.clusters.append(cluster)
    return cluster


def _merge_update(cluster: Cluster, update: ClusterUpdate, run_id: str, today: str, *, count_detection: bool) -> bool:
    old_urls = {canonical_url(e.url) for e in cluster.evidence}
    detected = any(e.counts_as_demand and canonical_url(e.url) not in old_urls for e in update.new_evidence)
    for field in ("name", "short_title", "who", "problem", "industry", "workaround", "why_insufficient", "root_cause", "why_now",
                  "opportunity_hypothesis", "buyer", "payment_evidence", "current_cost"):
        value = getattr(update, field).strip()
        if value:
            setattr(cluster, field, value)
    cluster.existing_solutions = _merge_list(cluster.existing_solutions, update.existing_solutions)
    cluster.contrarian = _merge_list(cluster.contrarian, update.contrarian)
    cluster.buying_evidence_urls = _merge_list(cluster.buying_evidence_urls, update.buying_evidence_urls)
    if update.next_validation:
        cluster.next_validation = update.next_validation
    cluster.evidence = _merge_evidence(cluster.evidence, update.new_evidence)
    cluster.solution_class = update.solution_class
    cluster.pain_confidence = update.pain_confidence
    cluster.gap_confidence = update.gap_confidence
    cluster.scores = clamp_scores(update.scores)
    if not cluster.payment_evidence or not cluster.buying_evidence_urls:
        cluster.scores.willingness_to_pay = min(cluster.scores.willingness_to_pay, 4)

    # Re-reading an old URL or a vendor pitch is not a new detection (codex-pp independence rule).
    if count_detection and detected:
        cluster.detected_runs += 1
        cluster.last_detected = today
    if cluster.status == "demoted" and detected and cluster.scores.overall >= REVIVE_OVERALL:
        cluster.status = "watch"
        cluster.status_reason = f"{today} 新证据让分数回到 {cluster.scores.overall}，从降级转为观察，待复核。原降级理由：{cluster.status_reason}"
    if cluster.status != "demoted" and (cluster.solution_class == "A" or (cluster.status == "active" and not eligible(cluster))):
        cluster.status = "watch"
        cluster.status_reason = "当前证据或方案缺口不足，等待复核。"

    last = cluster.score_history[-1] if cluster.score_history else None
    event = ScoreEvent(run_id=run_id, date=today, overall=cluster.scores.overall, reason=update.score_reason)
    if last and last.run_id == run_id:
        cluster.score_history[-1] = event
    else:
        cluster.score_history.append(event)
    return detected


def _merge_list(old: list[str], new: list[str]) -> list[str]:
    return old + [value for value in new if value.strip() and value not in old]


def _merge_evidence(old: list[Evidence], new: list[Evidence]) -> list[Evidence]:
    urls = {canonical_url(evidence.url): index for index, evidence in enumerate(old)}
    merged = list(old)
    for evidence in new:
        identity = canonical_url(evidence.url)
        if identity not in urls:
            urls[identity] = len(merged)
            merged.append(evidence)
        elif evidence.kind == "counterevidence" or evidence.source_key:
            # A changed, resolved thread supersedes its earlier demand classification.
            merged[urls[identity]] = evidence
    return merged
