import { ExternalLink } from 'lucide-react'
import { shortLabel } from '../lib/data'
import { KIND, LEVEL, ORIGIN, STATUS } from '../lib/labels'
import { Tag } from './Chrome'

function Field({ label, children, hint }) {
  if (children == null || children === '' || (Array.isArray(children) && children.length === 0)) return null
  return (
    <div>
      <h4 className="text-xs font-medium text-muted">
        {label}
        {hint && <span className="ml-1.5 font-normal">（{hint}）</span>}
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
        <div key={key} title={text} className={`flex items-baseline justify-between gap-2 border-b border-line pb-1 ${key === 'overall' ? 'col-span-2' : ''}`}>
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
            <Tag tone={item.counts_as_demand ? 'accent' : 'plain'} title={item.counts_as_demand ? '计入需求证据' : '不计入需求证据'}>
              {KIND[item.kind] ?? item.kind}
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

export function ClusterDetail({ cluster, rubric }) {
  const classText = cluster.solution_class ? rubric.classes[cluster.solution_class] : null
  return (
    <div className="space-y-8">
      {cluster.status_reason && (
        <p className="border-l-2 border-accent pl-3 text-sm leading-relaxed">
          <span className="text-muted">{STATUS[cluster.status]}说明：</span>
          {cluster.status_reason}
        </p>
      )}

      <div className="grid gap-8 md:grid-cols-[1fr_16rem]">
        <div className="space-y-5">
          <Field label="谁在痛">{cluster.who}</Field>
          <Field label="问题">{cluster.problem}</Field>
          <Field label="他们现在怎么凑合">{cluster.workaround}</Field>
          <Field label="现有方案">
            <BulletList items={cluster.existing_solutions} />
          </Field>
          <Field label="为什么还不够">{cluster.why_insufficient}</Field>
          <Field label="根因" hint="推断">{cluster.root_cause}</Field>
          <Field label="为什么是现在">{cluster.why_now}</Field>
          <Field label="机会假设" hint="推断">{cluster.opportunity_hypothesis}</Field>
        </div>

        <aside className="space-y-5">
          <ScoreGrid scores={cluster.scores} rubric={rubric} />
          <dl className="space-y-1.5 text-xs">
            {[
              ['现有方案分类', classText && `${cluster.solution_class} · ${shortLabel(classText)}`],
              ['痛点置信度', LEVEL[cluster.pain_confidence]],
              ['缺口置信度', LEVEL[cluster.gap_confidence]],
              ['检出次数', cluster.detected_runs],
              ['首次 / 最近', `${cluster.first_detected} / ${cluster.last_detected}`],
              ['方案核查', cluster.solution_checked_at],
              ['来源', <OriginList key="origin" origin={cluster.origin} />],
            ]
              .filter(([, value]) => value != null && value !== '')
              .map(([label, value]) => (
                <div key={label} className="flex justify-between gap-3">
                  <dt className="text-muted">{label}</dt>
                  <dd className="num text-right">{value}</dd>
                </div>
              ))}
          </dl>
          <Field label="下次看什么">{cluster.watch_next}</Field>
        </aside>
      </div>

      <div className="grid gap-8 md:grid-cols-2">
        <Field label="反方论证：为什么可能不是机会">
          <BulletList items={cluster.contrarian} />
        </Field>
        <Field label="下一步验证">
          <BulletList items={cluster.next_validation} ordered />
        </Field>
      </div>

      {cluster.score_history?.length > 0 && (
        <Field label="分数变化">
          <ol className="space-y-1.5">
            {cluster.score_history.map((event) => (
              <li key={event.run_id} className="flex gap-3 text-sm">
                <span className="num w-24 shrink-0 font-mono text-xs leading-6 text-muted">{event.date}</span>
                <span className="num w-8 shrink-0 font-mono leading-6">{event.overall}</span>
                <span className="text-muted">{event.reason}</span>
              </li>
            ))}
          </ol>
        </Field>
      )}

      <div>
        <h4 className="mb-2 text-xs font-medium text-muted">证据（{cluster.evidence?.length ?? 0} 条，高亮的计入需求）</h4>
        <EvidenceList evidence={cluster.evidence} />
      </div>
    </div>
  )
}
