import { ChevronDown, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ClusterDetail } from '../components/ClusterDetail'
import { Tag } from '../components/Chrome'
import { byOverall, shortLabel } from '../lib/data'
import { LEVEL, STATUS } from '../lib/labels'

const STATUS_FILTERS = [
  ['open', '活跃 + 观察'],
  ['active', '活跃'],
  ['watch', '观察'],
]

const SORTS = {
  overall: ['综合分', byOverall],
  momentum: ['动能', (a, b) => (b.scores?.momentum ?? -1) - (a.scores?.momentum ?? -1) || byOverall(a, b)],
  detected: ['检出次数', (a, b) => b.detected_runs - a.detected_runs || byOverall(a, b)],
  recent: ['最近检出', (a, b) => b.last_detected.localeCompare(a.last_detected) || byOverall(a, b)],
}

const selectClass = 'h-8 rounded-md border border-line bg-bg px-2 text-sm text-ink'

export function Ledger({ data }) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('open')
  const [solutionClass, setSolutionClass] = useState('all')
  const [industry, setIndustry] = useState('all')
  const [sort, setSort] = useState('overall')
  const [openId, setOpenId] = useState(null)

  const open = useMemo(() => data.clusters.filter((cluster) => cluster.status !== 'demoted'), [data])
  const industries = useMemo(() => [...new Set(open.map((cluster) => cluster.industry).filter(Boolean))].sort(), [open])

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return open
      .filter((cluster) => status === 'open' || cluster.status === status)
      .filter((cluster) => solutionClass === 'all' || cluster.solution_class === solutionClass)
      .filter((cluster) => industry === 'all' || cluster.industry === industry)
      .filter((cluster) => !needle || [cluster.id, cluster.name, cluster.who, cluster.problem, cluster.industry].join(' ').toLowerCase().includes(needle))
      .sort(SORTS[sort][1])
  }, [open, query, status, solutionClass, industry, sort])

  return (
    <div className="pt-8">
      <div className="flex flex-wrap items-center gap-2">
        <label className="relative w-full sm:w-64">
          <span className="sr-only">搜索</span>
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索人群、问题、行业"
            className="h-8 w-full rounded-md border border-line bg-bg pr-2 pl-8 text-sm placeholder:text-muted focus:border-accent focus:outline-none"
          />
        </label>
        <div className="flex rounded-md border border-line p-0.5" role="group" aria-label="状态">
          {STATUS_FILTERS.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setStatus(value)}
              aria-pressed={status === value}
              className={`rounded px-2.5 py-1 text-xs transition-colors ${status === value ? 'bg-surface text-ink' : 'text-muted hover:text-ink'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <select value={solutionClass} onChange={(event) => setSolutionClass(event.target.value)} className={selectClass} aria-label="现有方案分类">
          <option value="all">全部分类</option>
          {Object.entries(data.rubric.classes).map(([key, text]) => (
            <option key={key} value={key}>{key} · {shortLabel(text)}</option>
          ))}
        </select>
        <select value={industry} onChange={(event) => setIndustry(event.target.value)} className={selectClass} aria-label="行业">
          <option value="all">全部行业</option>
          {industries.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)} className={`${selectClass} sm:ml-auto`} aria-label="排序">
          {Object.entries(SORTS).map(([key, [label]]) => (
            <option key={key} value={key}>按{label}</option>
          ))}
        </select>
      </div>

      <p className="mt-4 text-xs text-muted">共 {rows.length} 个簇，点击一行展开证据、反方论证和分数变化。</p>

      <div className="mt-2 hidden grid-cols-[4.5rem_1fr_7rem_3.5rem_3.5rem_1.5rem] gap-3 border-b border-line pb-2 text-xs text-muted md:grid">
        <span>ID</span>
        <span>痛点</span>
        <span>置信度 痛点/缺口</span>
        <span className="text-right">检出</span>
        <span className="text-right">综合</span>
        <span />
      </div>
      <ul className="divide-y divide-line border-b border-line">
        {rows.map((cluster) => {
          const isOpen = openId === cluster.id
          return (
            <li key={cluster.id}>
              <button
                type="button"
                onClick={() => setOpenId(isOpen ? null : cluster.id)}
                aria-expanded={isOpen}
                aria-controls={`detail-${cluster.id}`}
                className="grid w-full grid-cols-[1fr_auto] items-start gap-3 py-3.5 text-left transition-colors hover:bg-surface md:grid-cols-[4.5rem_1fr_7rem_3.5rem_3.5rem_1.5rem] md:px-1"
              >
                <span className="hidden font-mono text-xs leading-6 text-muted md:block">{cluster.id}</span>
                <span className="min-w-0">
                  <span className="block text-sm leading-6 font-medium">{cluster.name}</span>
                  <span className="mt-1 flex flex-wrap gap-1.5">
                    {cluster.status !== 'active' && <Tag tone="accent">{STATUS[cluster.status]}</Tag>}
                    {cluster.industry && <Tag>{cluster.industry}</Tag>}
                    {cluster.solution_class && <Tag title={data.rubric.classes[cluster.solution_class]}>{cluster.solution_class} · {shortLabel(data.rubric.classes[cluster.solution_class])}</Tag>}
                    <span className="font-mono text-[11px] leading-5 text-muted md:hidden">{cluster.id} · 检出 {cluster.detected_runs}</span>
                  </span>
                </span>
                <span className="hidden text-sm leading-6 text-muted md:block">
                  {LEVEL[cluster.pain_confidence] ?? '—'} / {LEVEL[cluster.gap_confidence] ?? '—'}
                </span>
                <span className="num hidden text-right font-mono text-sm leading-6 md:block">{cluster.detected_runs}</span>
                <span className="num text-right font-mono text-base leading-6 font-semibold text-accent">{cluster.scores?.overall?.toFixed(1) ?? '—'}</span>
                <ChevronDown className={`mt-1 hidden size-4 text-muted transition-transform md:block ${isOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
              </button>
              <div id={`detail-${cluster.id}`} className="reveal" data-open={isOpen}>
                <div>
                  {isOpen && (
                    <div className="pt-2 pb-10 md:px-1">
                      <ClusterDetail cluster={cluster} rubric={data.rubric} />
                    </div>
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ul>
      {rows.length === 0 && <p className="py-10 text-center text-sm text-muted">没有符合条件的簇</p>}
    </div>
  )
}
