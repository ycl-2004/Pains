import { ArrowLeft, CheckSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ClusterDetail, EvidenceList, OpportunitySummary, OriginList } from '../components/ClusterDetail'
import { SectionTitle, Tag } from '../components/Chrome'
import { shortLabel } from '../lib/data'
import { STATUS } from '../lib/labels'
import { displayTitle, readResearch, STAGES } from '../lib/research'

export function ClusterPage({ data, id }) {
  const cluster = data.clusters.find((item) => item.id === id)
  const back = new URLSearchParams(window.location.hash.split('?')[1]).get('return')
  return (
    <div className="mx-auto max-w-3xl pt-6">
      <a href={back?.startsWith('#/ledger') ? back : '#/ledger'} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        机会库
      </a>
      {cluster ? (
        <article className="mt-5">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="font-mono">{cluster.id}</span>
            <Tag tone={cluster.status === 'active' ? 'plain' : 'accent'}>{STATUS[cluster.status]}</Tag>
            {cluster.industry && <Tag>{cluster.industry}</Tag>}
          </div>
          <h2 className="editorial-title mt-2 mb-8 max-w-3xl text-3xl leading-snug">{displayTitle(cluster)}</h2>
          <OpportunitySummary cluster={cluster} />
          <ClusterDetail cluster={cluster} rubric={data.rubric} />
        </article>
      ) : (
        <p className="py-10 text-sm text-muted">找不到 {id}，它可能已被合并。</p>
      )}
    </div>
  )
}

export function Signals({ data }) {
  const signals = data.signals.filter((s) => s.status === 'watching').sort((a, b) => b.last_detected.localeCompare(a.last_detected))
  return (
    <div className="pt-8">
      <SectionTitle>新兴信号</SectionTitle>
      <ul className="mt-3 divide-y divide-line border-y border-line">
        {signals.map((signal) => (
          <li key={signal.id} className="grid gap-x-6 gap-y-3 py-6 md:grid-cols-[4.5rem_1fr]">
            <span className="font-mono text-xs leading-6 text-muted">{signal.id}</span>
            <div className="min-w-0 space-y-3">
              <h3 className="text-base leading-snug font-semibold">{signal.title}</h3>
              <p className="text-sm leading-relaxed">{signal.why_watch}</p>
              {signal.watch_next && (
                <p className="text-sm">
                  <span className="text-muted">下次看：</span>
                  {signal.watch_next}
                </p>
              )}
              {signal.evidence.length > 0 && <EvidenceList evidence={signal.evidence} />}
              <p className="num text-xs text-muted">
                首次 {signal.first_detected} · 检出 {signal.detected_runs} 次 · 来源 <OriginList origin={signal.origin} />
              </p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Demoted({ data }) {
  const demoted = data.clusters.filter((cluster) => cluster.status === 'demoted')
  return (
    <div className="pt-8">
      <SectionTitle>已归档</SectionTitle>
      <ul className="mt-3 divide-y divide-line border-y border-line">
        {demoted.map((cluster) => (
          <li key={cluster.id} className="grid gap-x-6 gap-y-2 py-5 md:grid-cols-[4.5rem_1fr_3.5rem]">
            <span className="font-mono text-xs leading-6 text-muted">{cluster.id}</span>
            <div className="min-w-0 space-y-2">
              <h3 className="text-sm leading-6 font-medium">{cluster.name}</h3>
              <p className="text-sm leading-relaxed text-muted">{cluster.status_reason}</p>
              <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                {cluster.industry && <Tag>{cluster.industry}</Tag>}
                {cluster.solution_class && <Tag>{cluster.solution_class} · {shortLabel(data.rubric.classes[cluster.solution_class])}</Tag>}
                <span>来源 <OriginList origin={cluster.origin} /></span>
              </div>
              {cluster.evidence.length > 0 && <EvidenceList evidence={cluster.evidence} compact />}
            </div>
            <span className="num font-mono text-sm leading-6 text-muted md:text-right">{cluster.scores?.overall?.toFixed(1) ?? '—'}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Validation({ data }) {
  const [records, setRecords] = useState({})
  useEffect(() => {
    try { setRecords(readResearch()) } catch { setRecords({}) }
  }, [])
  const rows = Object.entries(records).map(([id, record]) => ({ cluster: data.clusters.find(cluster => cluster.id === id), id, record })).filter(row => row.cluster)
  return <div className="page-stack">
    <div className="page-intro"><div><p className="header-context">验证</p><h2>验证清单</h2><p className="mt-1">记录访谈、预算与试点进展。</p></div></div>
    <section className="panel"><div className="panel-header"><h3>我的验证记录</h3><a className="header-link" href="#/ledger">添加机会 <span aria-hidden="true">↗</span></a></div>{rows.length ? <ul className="side-list">{rows.map(({ cluster, id, record }) => <li key={id}><div className="flex flex-wrap items-center justify-between gap-3"><a href={`#/cluster/${id}`} className="text-sm hover:text-accent">{displayTitle(cluster)}</a><Tag tone={record.stage === 'pilot' ? 'success' : record.stage === 'rejected' ? 'plain' : 'accent'}>{STAGES[record.stage]}</Tag></div><p>{record.note || '还没有文字记录。'}</p><p className="mt-2 num text-[10px]">{record.updated ? `更新于 ${record.updated.slice(0, 10)}` : '尚未更新'}</p></li>)}</ul> : <div className="p-8 text-center"><CheckSquare className="mx-auto size-7 text-muted" aria-hidden="true" /><h3 className="mt-3 text-sm font-semibold">还没有验证记录</h3><p className="mt-1 text-xs text-muted">打开一个机会开始记录。</p><a href="#/ledger" className="action mt-4">浏览机会库</a></div>}</section>
  </div>
}
