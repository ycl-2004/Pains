import { ArrowRight } from 'lucide-react'
import { SectionTitle } from '../components/Chrome'
import { formatDateTime, topOpportunities } from '../lib/data'
import { displayTitle, evidenceSummary } from '../lib/research'

function RunStatus({ run, data }) {
  if (!run) {
    return (
      <div className="space-y-2 text-sm leading-relaxed">
        <p>
          还没有自动运行记录。当前展示的是<strong className="font-semibold">第 0 期基线</strong>：由 claude-pp、codex-pp、agy-pp 三份 2026-09-12 的独立研究去重合并而来，共{' '}
          <span className="num">{data.merge_log.length}</span> 条合并记录，见“方法与局限”。
        </p>
        <p className="text-muted">
          本地运行 <code className="rounded bg-surface px-1 py-0.5 font-mono text-xs">uv run python -m radar run</code> 即可抓取最新讨论并更新台账。
        </p>
      </div>
    )
  }
  const cost = run.cost_usd?.toFixed(2)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <span className="font-mono">{run.run_id}</span>
        <span>{({ success: '运行完成', partial: '部分完成，存在未验证环节', failed: '运行失败' })[run.status ?? 'success']}</span>
        <span className="num">{formatDateTime(run.finished_at)}</span>
        <span className="num">初筛 {run.triaged} · 保留 {run.kept} · 更新 {run.changes.length} 个簇 · 新信号 {run.new_signals.length}</span>
        {cost && <span className="num">LLM 花费约 ${cost}</span>}
      </div>
      {run.summary && <p className="max-w-3xl text-sm leading-relaxed">{run.summary}</p>}
      <p className="text-xs text-muted">
        {run.sources.map((source) => `${source.source} ${source.error ? '失败' : `${source.prefiltered}/${source.fetched}`}`).join(' · ')}
      </p>
      <p className="text-xs text-muted">
        {run.sources.map((source) => `${source.source}：初筛选入 ${source.selected ?? '—'} / 分析 ${source.analyzed ?? '—'}`).join(' · ')}
      </p>
      <div className="overflow-x-auto"><table className="w-full text-left text-xs"><caption className="pb-2 text-left text-muted">来源质量观察 · 模型初筛信号，不是已验证需求；— 表示旧运行未记录</caption><thead><tr className="border-b border-line"><th className="py-2">来源</th><th>进入分析</th><th>需求信号</th><th>求购/预算</th><th>反证</th></tr></thead><tbody>{run.sources.map(s => <tr key={s.source} className="border-b border-line"><td className="py-2">{s.source}</td><td>{s.analyzed ?? '—'}</td><td>{s.demand_signals ?? '—'}</td><td>{s.buying_signals ?? '—'}</td><td>{s.counter_signals ?? '—'}</td></tr>)}</tbody></table></div>
      {run.sources.some((source) => source.warnings?.length) && <p className="text-xs text-muted">采样说明：{run.sources.flatMap((source) => (source.warnings ?? []).map((warning) => `${source.source} ${warning}`)).join('；')}</p>}
      {run.changes.length === 0 && <p className="text-sm text-muted">本期没有新增或更新的痛点簇，以下为历史候选；不代表本期重新证实了需求。</p>}
      {run.notes.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted">
          {run.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function TopItem({ rank, cluster }) {
  const summary = evidenceSummary(cluster)
  return <li className="grid gap-4 py-7 sm:grid-cols-[3rem_1fr]">
    <span className="editorial-title text-3xl text-accent">{String(rank).padStart(2, '0')}</span>
    <div>
      <p className="eyebrow mb-2">{cluster.industry || 'Cross-industry'} / {cluster.id}</p>
      <h3><a href={`#/cluster/${cluster.id}`} className="editorial-title text-2xl leading-snug hover:text-accent">{displayTitle(cluster)}</a></h3>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">{cluster.problem}</p>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs">
        <span style={{ color: 'var(--evidence)' }}>{summary.threads} 条需求讨论 · {summary.communities} 个来源社区</span>
        <span className="text-muted">{cluster.payment_evidence ? '购买信号待核对' : '预算尚未证实'}</span>
        <span className="text-muted">核查 {cluster.solution_checked_at || '未完成'}</span>
      </div>
      <a href={`#/cluster/${cluster.id}`} className="mt-5 inline-flex items-center gap-2 text-sm text-accent">读证据，做判断 <ArrowRight className="size-4" aria-hidden="true" /></a>
    </div>
  </li>
}

export function Latest({ data }) {
  const run = data.runs[0]
  const top = topOpportunities(data)
  const byId = new Map(data.clusters.map((cluster) => [cluster.id, cluster]))
  const newSignals = data.signals.filter((signal) => run?.new_signals.includes(signal.id))

  return (
    <div className="space-y-12 pt-8">
      <section className="grid gap-6 border-b border-line pb-8 md:grid-cols-[1fr_18rem]">
        <div><p className="eyebrow">Field notes / 商业机会研究</p>
          <h2 className="editorial-title mt-3 text-4xl leading-tight sm:text-5xl">下一款产品，<br />从真实的<span className="text-accent">麻烦</span>开始。</h2>
          <p className="mt-5 max-w-xl text-sm text-muted">谁反复遇到问题？现在花了什么代价？为什么现有工具不够？先找到证据，再写第一行代码。</p>
        </div>
        <aside className="flex flex-col justify-end gap-3 border-l-2 border-line pl-5">
          <p className="eyebrow">本期阅读提示</p>
          <p className="text-sm">{run?.changes.length ? `${run.changes.length} 个研究对象发生变化。` : '本期没有新增或更新的痛点簇。'} 历史候选不代表本期重新证实了需求。</p>
          <a className="action self-start" href="#/ledger">打开机会工作台 ↗</a>
        </aside>
      </section>

      <div className="flex flex-wrap gap-2" aria-label="研究入口">
        <a className="filter-link" href="#/ledger?lens=buying">有购买证据</a>
        <a className="filter-link" href="#/ledger?lens=changed">本期有变化</a>
        <a className="filter-link" href="#/ledger?lens=saved">我的验证清单</a>
      </div>

      <section>
          <SectionTitle note="有引用的购买证据优先；仍需验证预算">优先验证候选</SectionTitle>
        <ol className="mt-3 divide-y divide-line border-y border-line">
          {top.map((cluster, index) => (
            <TopItem key={cluster.id} rank={index + 1} cluster={cluster} rubric={data.rubric} />
          ))}
        </ol>
        {top.length === 0 && <p className="py-6 text-sm text-muted">暂无证据和核查状态达标的候选。可到痛点台账查看观察项。</p>}
      </section>

      <details className="border-y border-line"><summary>数据健康与运行记录 · {run?.status === 'failed' ? '运行失败' : run?.status === 'partial' ? '部分完成' : run ? '最近运行完成' : '基线数据'}</summary><div className="pb-5"><RunStatus run={run} data={data} /></div></details>

      {run?.changes.length > 0 && (
        <section>
          <SectionTitle>本期变化</SectionTitle>
          <ul className="mt-3 divide-y divide-line border-y border-line">
            {run.changes.map((change) => (
              <li key={change.cluster_id} className="grid gap-1 py-3 text-sm sm:grid-cols-[4.5rem_1fr_6rem]">
                <span className="font-mono text-xs leading-6 text-muted">{change.cluster_id}</span>
                <div>
                  <a href={`#/cluster/${change.cluster_id}`} className="font-medium hover:text-accent">
                    {byId.get(change.cluster_id)?.name}
                  </a>
                  <p className="text-muted">{change.reason}</p>
                </div>
                <span className="num font-mono sm:text-right">
                  {change.action === 'created' ? `新建 ${change.overall_after}` : `${change.overall_before ?? '—'} → ${change.overall_after}`}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {newSignals.length > 0 && (
        <section>
          <SectionTitle>本期新信号</SectionTitle>
          <ul className="mt-3 space-y-2 text-sm">
            {newSignals.map((signal) => (
              <li key={signal.id}>
                <a href="#/signals" className="font-medium hover:text-accent">{signal.title}</a>
                <span className="text-muted"> — {signal.why_watch}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
