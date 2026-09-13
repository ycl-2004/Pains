import { ExternalLink } from 'lucide-react'
import { shortLabel } from '../lib/data'
import { KIND, LEVEL, ORIGIN, STATUS } from '../lib/labels'
import { Tag } from './Chrome'
import { evidenceSummary } from '../lib/research'
import { ValidationNotebook } from './ValidationNotebook'

function Field({ label, children }) {
  if (children == null || children === '' || (Array.isArray(children) && children.length === 0)) return null
  return (
    <div>
      <h4 className="text-xs font-medium text-muted">
        {label}
      </h4>
      <div className="mt-1 text-sm leading-relaxed">{children}</div>
    </div>
  )
}

function BulletList({ items, ordered = false }) {
  if (!items?.length) return null
  const List = ordered ? 'ol' : 'ul'
  return (
    <List className={`space-y-1 pl-5 ${ordered ? 'list-decimal' : 'list-disc'} marker:text-muted`}>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </List>
  )
}

export function OriginList({ origin }) {
  return (origin ?? []).map((name) => ORIGIN[name] ?? name).join('、')
}

export function ScoreGrid({ scores, rubric }) {
  if (!scores) return <p className="text-sm text-muted">暂不打分</p>
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
      {Object.entries(rubric.dimensions).map(([key, text]) => (
        <div key={key} className={`flex items-baseline justify-between gap-2 border-b border-line pb-1 ${key === 'overall' ? 'col-span-2' : ''}`}>
          <dt className="text-xs text-muted">{shortLabel(text)}</dt>
          <dd className={`num font-mono ${key === 'overall' ? 'text-lg font-semibold text-accent' : 'text-sm'}`}>{scores[key]}</dd>
        </div>
      ))}
    </dl>
  )
}

export function EvidenceList({ evidence, compact = false }) {
  if (!evidence?.length) return <p className="text-sm text-muted">暂无可链接的证据</p>
  return (
    <ul className="divide-y divide-line border-y border-line">
      {evidence.map((item) => (
        <li key={item.url} className="py-2.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <Tag tone={item.counts_as_demand ? 'evidence' : 'plain'} title={item.counts_as_demand ? '需求线索' : '参考来源'}>
              {item.kind === 'budget_or_payment' ? '金额线索' : KIND[item.kind] ?? item.kind}
            </Tag>
            <span>{item.platform}</span>
            {item.date && <span className="num">{item.date}</span>}
            {item.engagement && <span className="num">{item.engagement}</span>}
            <a href={item.url} target="_blank" rel="noopener noreferrer" className="ml-auto inline-flex items-center gap-1 text-ink underline decoration-line underline-offset-4 hover:decoration-accent">
              原文
              <ExternalLink className="size-3" aria-hidden="true" />
            </a>
          </div>
          {!compact && <p className="mt-1 text-sm leading-relaxed">{item.paraphrase}</p>}
        </li>
      ))}
    </ul>
  )
}

export function OpportunitySummary({ cluster }) {
  const summary = evidenceSummary(cluster)
  const buyerSignal = cluster.payment_evidence && cluster.buying_evidence_urls?.length ? '有引用 · 待核实' : '尚未确认'
  return <div className="opportunity-summary" aria-label="机会摘要">
    <div><span>目标人群</span><strong>{cluster.who || '待确认'}</strong></div>
    <div><span>证据强度</span><strong className="text-evidence">{summary.threads} 条讨论 · {summary.communities} 个社区</strong></div>
    <div><span>买方信号</span><strong>{buyerSignal}</strong></div>
    <div><span>最近变化</span><strong className="num">{cluster.last_detected || '—'}</strong></div>
  </div>
}

export function ClusterDetail({ cluster, rubric }) {
  const summary = evidenceSummary(cluster)
  const demand = (cluster.evidence || []).filter(e => e.counts_as_demand)
  const strongest = [...demand].sort((a, b) => Number(cluster.buying_evidence_urls?.includes(b.url)) - Number(cluster.buying_evidence_urls?.includes(a.url))).slice(0, 3)
  const unknown = [!cluster.buyer && '付款决策人', !cluster.payment_evidence && '明确预算', !cluster.current_cost && '当前成本'].filter(Boolean)
  return <div className="space-y-6">
    <div>
      <p className="text-base leading-relaxed">{cluster.problem}</p>
      <p className="mt-3 text-sm text-muted">目标客户 · {cluster.who}</p>
      {cluster.status_reason && <p className="mt-3 text-xs text-muted">{STATUS[cluster.status]} · {cluster.status_reason}</p>}
    </div>
    <div className="evidence-strip">
      <p>{summary.threads} 条需求讨论 · {summary.communities} 个来源社区</p>
      <p className="mt-1">{summary.span}</p>
      <p className="mt-1">现有方案更新：{cluster.solution_checked_at || '暂无记录'}</p>
    </div>
    <section className="dossier-section">
      <h3>买方证据</h3>
      {unknown.length > 0 && <p className="mb-4 rounded-lg bg-surface p-3 text-sm text-muted">待确认：{unknown.join('、')}</p>}
      <div className="mb-4 space-y-3">
        <Field label="付款方">{cluster.buyer}</Field>
        <Field label="购买线索">{cluster.payment_evidence}</Field>
        <Field label="当前成本">{cluster.current_cost}</Field>
        {cluster.buying_evidence_urls?.length > 0 && <ul className="text-xs text-accent">{cluster.buying_evidence_urls.map((url, i) => <li key={url}><a href={url} target="_blank" rel="noopener noreferrer" className="underline">购买来源 {i + 1} ↗</a></li>)}</ul>}
      </div>
      <EvidenceList evidence={strongest} />
    </section>
    <section className="dossier-section">
      <h3>方案缺口</h3>
      <div className="space-y-4">
        <Field label="现有做法">{cluster.workaround}</Field>
        <Field label="已有替代方案"><BulletList items={cluster.existing_solutions} /></Field>
        <Field label="仍未解决">{cluster.why_insufficient}</Field>
        <Field label="机会假设">{cluster.opportunity_hypothesis}</Field>
      </div>
    </section>
    <section className="dossier-section">
      <h3>主要风险</h3>
      <div className="text-sm leading-relaxed"><BulletList items={cluster.contrarian} /></div>
      {!(cluster.contrarian?.length) && <p className="text-sm text-muted">暂无反方观点</p>}
    </section>
    <section className="dossier-section">
      <h3>下一步验证</h3>
      <div className="text-sm leading-relaxed"><BulletList items={cluster.next_validation} ordered /></div>
    </section>
    <ValidationNotebook key={cluster.id} id={cluster.id} />
    <details className="dossier-section"><summary>全部来源 · {cluster.evidence?.length || 0} 条</summary><EvidenceList evidence={cluster.evidence} /></details>
    <details className="dossier-section"><summary>评分与历史</summary>
      <div className="space-y-5 py-3">
        <Field label="原始完整标题">{cluster.name}</Field>
        <Field label="根因">{cluster.root_cause}</Field>
        <Field label="时机判断">{cluster.why_now}</Field>
        <Field label="下次观察">{cluster.watch_next}</Field>
        <p className="text-xs text-muted">痛点信心 {LEVEL[cluster.pain_confidence]} / 缺口信心 {LEVEL[cluster.gap_confidence]} · 出现 {cluster.detected_runs} 次 · 来源 <OriginList origin={cluster.origin} /></p>
        <ScoreGrid scores={cluster.scores} rubric={rubric} />
        <ul className="space-y-2 text-xs text-muted">{cluster.score_history?.map((e, i) => <li key={i}>{e.date} · {e.overall} / {e.reason}</li>)}</ul>
      </div>
    </details>
  </div>
}
