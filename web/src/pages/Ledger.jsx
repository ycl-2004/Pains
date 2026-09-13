import { useEffect, useState } from 'react'
import { ClusterDetail, OpportunitySummary } from '../components/ClusterDetail'
import { Tag } from '../components/Chrome'
import { Filter } from 'lucide-react'
import { byOpportunity, byOverall, hasBuyingEvidence } from '../lib/data'
import { displayTitle, evidenceSummary, ledgerHash, readResearch } from '../lib/research'

const read = () => Object.fromEntries(new URLSearchParams(window.location.hash.split('?')[1]))
export function Ledger({ data }) {
  const [params, setParams] = useState(read)
  useEffect(() => {
    const update = () => setParams(read())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  function change(key, value, replace = false) {
    const next = { ...params, [key]: value }
    if (key !== 'selected') delete next.selected
    setParams(next)
    if (replace) { window.history.replaceState(null, '', ledgerHash(next)); window.dispatchEvent(new HashChangeEvent('hashchange')) }
    else window.location.hash = ledgerHash(next)
    if (key === 'selected') requestAnimationFrame(() => {
      const panel = document.querySelector('.desk-detail')
      if (panel && panel.getBoundingClientRect().top < 70) panel.scrollIntoView({ block: 'start' })
    })
  }
  const open = data.clusters.filter(c => c.status !== 'demoted')
  const industries = [...new Set(open.map(c => c.industry).filter(Boolean))].sort()
  let saved = {}
  try { saved = readResearch() } catch { /* Notebook explains unavailable storage. */ }
  const rows = open.filter(c => !params.status || c.status === params.status)
    .filter(c => !params.industry || c.industry === params.industry)
    .filter(c => !params.class || c.solution_class === params.class)
    .filter(c => params.lens !== 'buying' || hasBuyingEvidence(c))
    .filter(c => params.lens !== 'saved' || Boolean(saved[c.id]))
    .filter(c => params.lens !== 'changed' || data.runs[0]?.changes.some(change => change.cluster_id === c.id))
    .filter(c => !params.q || [c.name, c.who, c.problem, c.industry].join(' ').toLowerCase().includes(params.q.toLowerCase()))
    .sort(params.sort === 'recent' ? (a, b) => b.last_detected.localeCompare(a.last_detected) : params.sort === 'score' ? byOverall : byOpportunity)
  const selected = rows.find(c => c.id === params.selected) || rows[0]
  const fullLink = c => `#/cluster/${c.id}?return=${encodeURIComponent(ledgerHash(params))}`
  return <div className="pt-8">
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div><p className="header-context">研究工作区</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">机会库</h2></div>
      <p className="max-w-xs text-xs text-muted">先读证据，再决定是否值得联系买方。讨论数量不等于独立买家数。</p>
    </div>
    <div className="mb-4 flex flex-wrap gap-2">
      <label className="min-w-0 basis-full sm:flex-1 sm:basis-auto"><span className="sr-only">搜索人群、问题、行业</span><input className="research-input w-full" type="search" value={params.q || ''} onChange={e => change('q', e.target.value, true)} placeholder="搜索人群、问题、行业…" /></label>
      <details className="filter-popover"><summary><Filter className="size-3.5" aria-hidden="true" />筛选</summary><div className="filter-popover-body">
        <select className="research-input" aria-label="证据视角" value={params.lens || ''} onChange={e => change('lens', e.target.value)}><option value="">全部机会</option><option value="buying">有购买来源</option><option value="changed">本期有变化</option><option value="saved">我的验证清单</option></select>
        <select className="research-input" aria-label="行业适配" value={params.industry || ''} onChange={e => change('industry', e.target.value)}><option value="">行业：不限</option>{industries.map(i => <option key={i}>{i}</option>)}</select>
        <select className="research-input" aria-label="排序" value={params.sort || ''} onChange={e => change('sort', e.target.value)}><option value="">购买来源优先</option><option value="recent">最近检出</option><option value="score">综合分</option></select>
        <select className="research-input" aria-label="状态" value={params.status || ''} onChange={e => change('status', e.target.value)}><option value="">活跃 + 观察</option><option value="active">活跃</option><option value="watch">观察</option></select>
        <select className="research-input max-w-full" aria-label="现有方案分类" value={params.class || ''} onChange={e => change('class', e.target.value)}><option value="">方案分类：全部</option>{Object.entries(data.rubric.classes).map(([key, label]) => <option key={key} value={key}>{key} · {label}</option>)}</select>
      </div></details>
    </div>
    <p className="mb-3 text-xs text-muted" role="status">{rows.length} 个研究对象 · 来源讨论数不等于独立买家数</p>
    {rows.length ? <div className="desk">
      <div className="desk-list"><ul>{rows.map(c => {
        const summary = evidenceSummary(c)
        return <li key={c.id}><a className="desk-row" aria-current={selected?.id === c.id ? 'true' : undefined} href={fullLink(c)} onClick={e => {
          if (window.matchMedia('(min-width: 768px)').matches && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) { e.preventDefault(); change('selected', c.id) }
        }}>
          <div className="mb-2 flex items-center justify-between gap-2"><span className="eyebrow">{c.id}</span><Tag>{c.industry || '跨行业'}</Tag></div>
          <h3 className="text-base leading-relaxed font-semibold" title={c.name}>{displayTitle(c)}</h3>
          <p className="mt-2 line-clamp-2 text-sm text-muted">{c.problem}</p>
          <p className="mt-4 text-xs" style={{ color: 'var(--evidence)' }}>{summary.threads} 条需求讨论 · {summary.communities} 个来源社区</p>
          <p className="mt-1 text-xs text-muted">{hasBuyingEvidence(c) ? '有引用的购买信号 · 待核实' : '预算尚未证实'} · 最近 {c.last_detected}</p>
        </a></li>
      })}</ul></div>
      <article className="desk-detail" key={selected.id} aria-label="选中机会详情">
        <div className="mb-5 flex items-center justify-between gap-2"><span className="eyebrow">机会详情 / {selected.id}</span><a className="text-xs text-accent underline" href={fullLink(selected)}>独立打开 ↗</a></div>
        <h2 className="mb-4 text-xl leading-snug font-semibold tracking-tight">{displayTitle(selected)}</h2>
        <OpportunitySummary cluster={selected} />
        <ClusterDetail cluster={selected} rubric={data.rubric} />
      </article>
    </div> : <div className="py-16 text-center"><h3>没有符合条件的机会</h3><p className="mt-2 text-sm text-muted">证据不足时，空白比虚假的推荐更有用。</p><a className="filter-link mt-5 inline-block" href="#/ledger">清除筛选</a></div>}
  </div>
}
