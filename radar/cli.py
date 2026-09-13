"""Command line entry point: `python -m radar <command>`."""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

from radar import config
from radar import ledger as ledger_store
from radar.export import export_site, load_runs
from radar.llm.analyze import check_solutions, run_analysis
from radar.llm.client import LLM, Budget, BudgetExceeded, StageFailed, llm_problem
from radar.llm.triage import run_triage
from radar.models import Ledger, RawItem, RunReport, SourceStat, TriageVerdict
from radar.registry import SOURCES, get_source
from radar.scoring import is_significant_change
from radar.sources.base import SourceAdapter
from radar.sampling import select_items
from radar.evidence import eligible, opportunity_rank
from radar.privacy import redact
from radar.revisit import revisit

SEEN_LIMIT = 50_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="痛点雷达：抓取公开讨论 → 初筛 → 聚类打分 → 台账 → 网站数据")
    commands = parser.add_subparsers(dest="command", required=True)

    seed = commands.add_parser("seed", help="用第 0 期基线初始化 data/ledger.json")
    seed.add_argument("--force", action="store_true", help="覆盖已有台账")

    fetch = commands.add_parser("fetch", help="只抓取和规则预筛，不调用 LLM、不改台账")
    fetch.add_argument("--source", choices=[source.name for source in SOURCES])

    for name, help_text in (("run", "完整跑一期（需要模型配置和凭据）"),
                            ("refresh", "数据过期且模型可用时跑一期，否则只导出")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--limit", type=int, help="最多送多少条去初筛（业务来源加权轮询）")
        command.add_argument("--max-cost", type=float, default=config.DEFAULT_MAX_COST_USD, help="本期 LLM 软预算（美元，硬额度请在服务商设置）")
        command.add_argument("--skip-solution-check", action="store_true", help="不做联网的现有方案检查")
    refresh = commands.choices["refresh"]
    refresh.add_argument("--stale-after", default="20h", help="距上一期多久算过期，如 20h、90m、2d；0m 表示立即跑")
    refresh.add_argument("--strict", action="store_true", help="模型可用但运行失败时以非零退出（CI 用）")

    commands.add_parser("export", help="把台账导出成网站数据")
    commands.add_parser("status", help="查看台账和最近一期概况")

    args = parser.parse_args(argv)
    handlers = {"seed": cmd_seed, "fetch": cmd_fetch, "run": cmd_run, "refresh": cmd_refresh,
                "export": cmd_export, "status": cmd_status}
    return handlers[args.command](args)


def cmd_seed(args) -> int:
    created = ledger_store.init_from_seed(config.SEED_PATH, config.LEDGER_PATH, force=args.force)
    print("已用第 0 期基线初始化台账" if created else "台账已存在，未覆盖（需要覆盖请加 --force）")
    return cmd_export(args)


def cmd_fetch(args) -> int:
    now = datetime.now(timezone.utc)
    sources = [get_source(args.source)] if args.source else list(SOURCES)
    stats, candidates = collect(sources, now, now.strftime("%H%M"))
    for stat in stats:
        print(f"{stat.source}: 抓到 {stat.fetched} · 新的 {stat.new} · 通过预筛 {stat.prefiltered}" + (f" · 错误 {stat.error}" if stat.error else ""))
    for item in sorted(candidates, key=engagement, reverse=True)[:10]:
        print(f"  [{item.source}] {item.comments} 评论 · {item.title[:80]}")
    return 0


def cmd_run(args) -> int:
    if args.limit is not None and args.limit <= 0:
        print("--limit 必须为正整数", file=sys.stderr)
        return 2
    if problem := llm_problem():
        print(problem, file=sys.stderr)
        return 2
    ledger = ensure_ledger()
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    report = RunReport(run_id=now.strftime("%Y-%m-%d-%H%M%S-%f"), started_at=now, window_hours=config.WINDOW_HOURS)
    budget = Budget(args.max_cost)
    llm = LLM(budget, cache_dir=config.AUDIT_DIR / "calls")
    seen_now: list[str] = []

    report.sources, candidates = collect(SOURCES, now, now.strftime("%H%M"))
    candidates = select_items(candidates, args.limit)
    revisited, revisit_notes, reviewed = revisit(ledger, now, limit=min(5, args.limit or 5))
    report.notes += revisit_notes
    if revisited:
        report.notes.append(f"本期含 {len(revisited)} 条既有证据复查，不作为新的独立需求计数")
    selected_keys = {i.key for i in revisited}
    candidates = (revisited + [i for i in candidates if i.key not in selected_keys])[:args.limit]
    for stat in report.sources:
        stat.selected = sum(item.source == stat.source for item in candidates)
    if any(stat.error or stat.degraded for stat in report.sources) or revisit_notes:
        report.status = "partial"
    try:
        if report.sources and all(stat.error for stat in report.sources):
            raise StageFailed("所有来源抓取失败")
        kept, judged, notes = run_triage(llm, candidates)
        report.notes += notes
        report.triaged, report.kept = len(judged), len(kept)
        kept_keys = {item.key for item, _ in kept}
        seen_now += [item.revision_key for item in judged if item.key not in kept_keys]
        if notes or len(judged) < len(candidates):
            report.status = "partial" if judged else "failed"

        by_key = {item.key: (item, verdict) for item, verdict in kept}
        signals = deepen([by_key[item.key] for item in select_items([i for i, _ in kept], config.MAX_ANALYZE_SIGNALS)], report)
        context = [(i, v) for i, v in signals if v.needs_context and i.thread][:config.MAX_CONTEXT_THREADS]
        if context:
            accepted, rejudged, context_notes = run_triage(llm, [i for i, _ in context])
            report.notes += context_notes
            if context_notes:
                report.status = "partial"
            checked = {i.key for i in rejudged}
            replacements = {i.key: (i, v) for i, v in accepted}
            signals = [replacements.get(i.key, (i, v)) for i, v in signals if i.key not in checked or i.key in replacements]
            seen_now += [i.revision_key for i in rejudged if i.key not in replacements]
        for stat in report.sources:
            stat.analyzed = sum(i.source == stat.source for i, _ in signals)
        if signals:
            result = run_analysis(llm, ledger, signals)
            report.changes, report.new_signals, report.top_opportunities = ledger_store.apply_analysis(
                ledger, result, report.run_id, today)
            report.summary = result.summary
            seen_now += [item.revision_key for item, _ in signals]
            processed_keys = {item.key for item, _ in signals}
            seen_now += [item.revision_key for item in candidates if item.key in processed_keys]
        else:
            report.notes.append("本期没有条目通过初筛")
        if not args.skip_solution_check:
            run_solution_checks(llm, ledger, report, today)
        else:
            report.notes.append("本期主动跳过现有方案核查；候选不视为重新验证")
        report.top_opportunities = [c.id for c in sorted(ledger.clusters, key=opportunity_rank)
                                    if c.status == "active" and eligible(c) and c.solution_checked_at
                                    and 0 <= (now.date() - datetime.fromisoformat(c.solution_checked_at).date()).days <= config.SOLUTION_RECHECK_DAYS][:3]
    except (BudgetExceeded, StageFailed, ValueError) as error:
        if isinstance(error, ValueError):
            llm.discard_last_cache()
        report.status = "partial" if report.changes or seen_now else "failed"
        report.notes.append(f"提前停止：{error}")

    report.notes += llm.notes
    report.usage = budget.records
    report.finished_at = datetime.now(timezone.utc)
    if budget.spent > budget.max_cost_usd:
        report.status = "partial"
    ledger.last_run_id = report.run_id
    save_run(report, ledger, seen_now)
    # Only advance review timestamps after the discussion reached a completed analysis.
    consumed = set(seen_now)
    path = config.DATA_DIR / "reviewed.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    previous.update({i.key: reviewed[i.key] for i in revisited if i.revision_key in consumed})
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(previous, ensure_ascii=False))
    temporary.replace(path)
    print(f"{report.run_id}: 初筛 {report.triaged} 条，保留 {report.kept} 条，更新 {len(report.changes)} 个簇，"
          f"新信号 {len(report.new_signals)} 个，花费约 ${budget.spent:.2f}")
    for note in report.notes:
        print(f"  注意：{note}")
    return 0 if report.status == "success" else 1


def cmd_refresh(args) -> int:
    ensure_ledger()
    runs = load_runs(config.RUNS_DIR)
    successful = [run for run in runs if run.status == "success"]
    latest_ok = successful[-1] if successful else None
    # A failed attempt after a success remains retryable immediately.
    age = (datetime.now(timezone.utc) - latest_ok.started_at
           if latest_ok and runs[-1].run_id == latest_ok.run_id else None)
    status = 0
    if age is not None and age < parse_duration(args.stale_after):
        print(f"最近一期是 {int(age.total_seconds() // 3600)} 小时前跑的，未过期，直接导出")
    elif problem := llm_problem():
        print(f"跳过抓取，只导出现有数据：{problem}")
    elif cmd_run(args) != 0:
        print("本期运行失败，继续使用现有数据", file=sys.stderr)
        status = 1 if args.strict else 0
    cmd_export(args)
    return status


def cmd_export(args) -> int:
    target = export_site(ensure_ledger(), config.RUNS_DIR, config.WEB_DATA_DIR)
    print(f"网站数据已写入 {target.relative_to(config.ROOT)}")
    return 0


def cmd_status(args) -> int:
    ledger = ensure_ledger()
    counts = {status: sum(c.status == status for c in ledger.clusters) for status in ("active", "watch", "demoted")}
    print(f"台账：活跃 {counts['active']} · 观察 {counts['watch']} · 降级 {counts['demoted']} · 新兴信号 {len(ledger.signals)}")
    active = sorted((c for c in ledger.clusters if c.status == "active" and c.scores), key=lambda c: -c.scores.overall)
    for cluster in active[:5]:
        print(f"  {cluster.id} {cluster.scores.overall:>4} · 检出 {cluster.detected_runs} 次 · {cluster.name}")
    runs = load_runs(config.RUNS_DIR)
    if runs:
        last = runs[-1]
        print(f"最近一期 {last.run_id}：保留 {last.kept} 条，花费约 ${sum(u.cost_usd for u in last.usage):.2f}")
    print(f"模型：{llm_problem() or '已配置'}")
    return 0


def collect(sources: list[SourceAdapter], now: datetime, stamp: str) -> tuple[list[SourceStat], list[RawItem]]:
    """Fetch every source, persist raw items, drop already-seen ones, apply the keyword prefilter."""
    seen = set(load_seen())
    day_dir = config.RAW_DIR / now.date().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)
    stats, candidates = [], []
    for source in sources:
        stat = SourceStat(source=source.name)
        try:
            items = source.collect(now, timedelta(hours=config.WINDOW_HOURS))
        except Exception as error:  # one broken source must not sink the whole run
            stat.error = f"{type(error).__name__}: {error}"
            stats.append(stat)
            continue
        for item in items:
            item.title, item.body = redact(item.title), redact(item.body)
        raw_path = day_dir / f"{stamp}-{source.name}.json"
        raw_path.write_text(json.dumps([item.model_dump(mode="json") for item in items], ensure_ascii=False, indent=1),
                            encoding="utf-8")
        fresh = [item for item in items if item.revision_key not in seen]
        passed = source.prefilter(fresh)
        stat.fetched, stat.new, stat.prefiltered = len(items), len(fresh), len(passed)
        stat.warnings = list(source.warnings)
        stat.degraded = source.degraded
        stats.append(stat)
        candidates += passed
    return stats, candidates


def deepen(signals: list[tuple[RawItem, TriageVerdict]], report: RunReport) -> list[tuple[RawItem, TriageVerdict]]:
    """Attach top replies to the most engaged survivors; behavior evidence usually lives in the replies."""
    deepened, failures = [], 0
    for index, (item, verdict) in enumerate(signals):
        if index < config.MAX_THREADS and not item.thread:
            try:
                item = get_source(item.source).attach_thread(item)
            except Exception:  # a missing thread only costs context, not the signal
                failures += 1
        deepened.append((item, verdict))
    if failures:
        report.notes.append(f"{failures} 条讨论串拉取失败，按无回复处理")
        report.status = "partial"
    return deepened


def run_solution_checks(llm: LLM, ledger: Ledger, report: RunReport, today: str) -> None:
    by_id = {cluster.id: cluster for cluster in ledger.clusters}
    changed = [change.cluster_id for change in report.changes
               if change.action == "created" or is_significant_change(change.overall_before, change.overall_after)]
    due = sorted((c for c in ledger.clusters if c.status != "demoted" and
                  (not c.solution_checked_at or (datetime.fromisoformat(today).date() -
                   datetime.fromisoformat(c.solution_checked_at).date()).days >= config.SOLUTION_RECHECK_DAYS)),
                 key=lambda c: (c.solution_checked_at or "", -(c.scores.overall if c.scores else 0)))
    # Reserve the first slot for overdue work so a steady stream of new clusters cannot starve it.
    targets = list(dict.fromkeys(([due[0].id] if due else []) + changed + [c.id for c in due]))
    for cluster_id in targets[: config.MAX_SOLUTION_CHECKS]:
        cluster = by_id[cluster_id]
        before = cluster.scores.overall if cluster.scores else None
        before_status = (cluster.status, cluster.solution_class)
        try:
            check = check_solutions(llm, cluster, today=today)
            ledger_store.apply_solution_check(cluster, check, today, report.run_id)
        except (StageFailed, ValueError) as error:
            report.notes.append(f"{cluster.id} 现有方案检查失败：{error}")
            report.status = "partial"
            continue
        if cluster.scores and (before != cluster.scores.overall or before_status != (cluster.status, cluster.solution_class)):
            change = next((c for c in report.changes if c.cluster_id == cluster.id), None)
            if change:
                change.overall_after = cluster.scores.overall
                change.reason += f"；方案核查：{cluster.status_reason}"
            else:
                from radar.models import ClusterChange
                report.changes.append(ClusterChange(cluster_id=cluster.id, action="updated", overall_before=before,
                                                    overall_after=cluster.scores.overall, reason=cluster.status_reason))


def save_run(report: RunReport, ledger: Ledger, seen_now: list[str]) -> None:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RUNS_DIR / f"{report.run_id}.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    ledger_store.save(ledger, config.LEDGER_PATH)
    ledger_store.snapshot(ledger, report.run_id, config.LEDGER_HISTORY_DIR)
    save_seen(seen_now)
    export_site(ledger, config.RUNS_DIR, config.WEB_DATA_DIR)


def ensure_ledger() -> Ledger:
    ledger_store.init_from_seed(config.SEED_PATH, config.LEDGER_PATH)
    return ledger_store.load(config.LEDGER_PATH)


def load_seen() -> list[str]:
    return json.loads(config.SEEN_PATH.read_text(encoding="utf-8")) if config.SEEN_PATH.exists() else []


def save_seen(new_keys: list[str]) -> None:
    keys = list(dict.fromkeys(load_seen() + new_keys))[-SEEN_LIMIT:]
    config.SEEN_PATH.write_text(json.dumps(keys), encoding="utf-8")


def engagement(item: RawItem) -> tuple[int, int]:
    return item.comments, item.score


def parse_duration(text: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([mhd])", text.strip())
    if not match:
        raise ValueError(f"无法识别的时长 {text!r}，请用 90m、20h、2d 这样的格式")
    unit = {"m": "minutes", "h": "hours", "d": "days"}[match.group(2)]
    return timedelta(**{unit: int(match.group(1))})
