import { ArrowRight } from 'lucide-react'
import { SectionTitle, Tag } from '../components/Chrome'
import { formatDateTime, shortLabel, topOpportunities } from '../lib/data'
import { LEVEL } from '../lib/labels'

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
        <span className="num">{formatDateTime(run.finished_at)}</span>
        <span className="num">初筛 {run.triaged} · 保留 {run.kept} · 更新 {run.changes.length} 个簇 · 新信号 {run.new_signals.length}</span>
        {cost && <span className="num">LLM 花费约 ${cost}</span>}
      </div>
      {run.summary && <p className="max-w-3xl text-sm leading-relaxed">{run.summary}</p>}
      <p className="text-xs text-muted">
        {run.sources.map((source) => `${source.source} ${source.error ? '失败' : `${source.prefiltered}/${source.fetched}`}`).join(' · ')}
      </p>
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

function TopItem({ rank, cluster, rubric }) {
  return (
    <li className="grid gap-x-6 gap-y-4 py-7 md:grid-cols-[2.5rem_1fr_8.5rem]">
      <span className="num font-mono text-2xl leading-none text-muted">{String(rank).padStart(2, '0')}</span>
      <div className="min-w-0 space-y-4">
        <div>
          <a href={`#/cluster/${cluster.id}`} className="text-lg leading-snug font-semibold hover:text-accent">
            {cluster.name}
          </a>
          <p className="mt-1 text-sm text-muted">{cluster.who}</p>
        </div>
        <p className="text-sm leading-relaxed">{cluster.problem}</p>
        <div className="grid gap-4 text-sm leading-relaxed sm:grid-cols-2">
          <div>
            <h3 className="text-xs font-medium text-muted">为什么是现在</h3>
            <p className="mt-1">{cluster.why_now}</p>
          </div>
          <div>
            <h3 className="text-xs font-medium text-muted">现有方案为什么不行</h3>
            <p className="mt-1">{cluster.why_insufficient}</p>
          </div>
        </div>
        {cluster.next_validation?.length > 0 && (
          <div>
            <h3 className="text-xs font-medium text-muted">下一步验证</h3>
            <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm marker:text-muted">
              {cluster.next_validation.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
        )}
        <a href={`#/cluster/${cluster.id}`} className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
          查看证据和反方论证
          <ArrowRight className="size-3.5" aria-hidden="true" />
        </a>
      </div>
      <div className="flex flex-row flex-wrap items-center gap-3 md:flex-col md:items-end md:text-right">
        <div>
          <div className="num font-mono text-3xl leading-none font-semibold text-accent">{cluster.scores?.overall?.toFixed(1)}</div>
          <div className="mt-1 text-xs text-muted">综合分</div>
        </div>
        <div className="flex flex-wrap gap-1.5 md:justify-end">
          {cluster.solution_class && <Tag title={rubric.classes[cluster.solution_class]}>{cluster.solution_class} · {shortLabel(rubric.classes[cluster.solution_class])}</Tag>}
          <Tag>痛点置信 {LEVEL[cluster.pain_confidence]}</Tag>
          <Tag>缺口置信 {LEVEL[cluster.gap_confidence]}</Tag>
        </div>
      </div>
    </li>
  )
}

export function Latest({ data }) {
  const run = data.runs[0]
  const top = topOpportunities(data)
  const byId = new Map(data.clusters.map((cluster) => [cluster.id, cluster]))
  const newSignals = data.signals.filter((signal) => run?.new_signals.includes(signal.id))

  return (
    <div className="space-y-12 pt-8">
      <section>
        <RunStatus run={run} data={data} />
      </section>

      <section>
        <SectionTitle note="按综合分、痛点置信度、检出次数排序">{run?.top_opportunities?.length ? '本期最值得行动' : '当前最值得行动'}</SectionTitle>
        <ol className="mt-3 divide-y divide-line border-y border-line">
          {top.map((cluster, index) => (
            <TopItem key={cluster.id} rank={index + 1} cluster={cluster} rubric={data.rubric} />
          ))}
        </ol>
      </section>

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
