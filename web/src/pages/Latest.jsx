import { ArrowUpRight, CheckCircle2, CircleAlert, Clock3, Database, Filter } from 'lucide-react'
import { SectionTitle, Tag } from '../components/Chrome'
import { formatDateTime, hasBuyingEvidence, topOpportunities } from '../lib/data'
import { displayTitle, evidenceSummary } from '../lib/research'

function Metric({ label, value, note, icon: Icon, tone = 'plain' }) {
  return <div className="metric-cell">
    <div className="flex items-center justify-between gap-3"><span className="metric-label">{label}</span>{Icon && <Icon className={`size-4 ${tone === 'accent' ? 'text-accent' : 'text-muted'}`} aria-hidden="true" />}</div>
    <div className={`metric-value ${tone === 'accent' ? 'text-accent' : ''}`}>{value}</div>
    <div className="metric-note">{note}</div>
  </div>
}

function RunStatus({ run, data }) {
  if (!run) return <p className="py-4 text-sm text-muted">还没有自动运行记录。当前展示的是基线数据；运行 <code className="rounded bg-surface-alt px-1.5 py-0.5 font-mono text-xs">uv run python -m radar run</code> 可更新研究。</p>
  const statusText = { success: '运行完成', partial: '部分完成，存在未验证环节', failed: '运行失败' }
  return <div className="space-y-3 py-3 text-xs text-muted">
    <div className="flex flex-wrap gap-x-5 gap-y-1"><span className="font-mono">{run.run_id}</span><span>{statusText[run.status ?? 'success']}</span><span className="num">{formatDateTime(run.finished_at)}</span><span>初筛 {run.triaged} · 保留 {run.kept} · 更新 {run.changes.length} 个簇</span>{run.cost_usd != null && <span>LLM 花费约 ${run.cost_usd.toFixed(2)}</span>}</div>
    {run.summary && <p className="max-w-3xl text-sm leading-relaxed text-ink">{run.summary}</p>}
    {run.sources.some(source => source.warnings?.length) && <p>采样说明：{run.sources.flatMap(source => (source.warnings ?? []).map(warning => `${source.source} ${warning}`)).join('；')}</p>}
    {run.notes?.length > 0 && <ul className="list-disc space-y-1 pl-5">{run.notes.map(note => <li key={note}>{note}</li>)}</ul>}
    {run.changes.length === 0 && <p>本期没有新增或更新的痛点簇；历史候选不代表本期重新证实需求。</p>}
  </div>
}

function OpportunityRow({ cluster }) {
  const summary = evidenceSummary(cluster)
  return <div className="opportunity-row">
    <div className="min-w-0"><div className="mb-1 flex flex-wrap items-center gap-2"><a href={`#/cluster/${cluster.id}`} className="opportunity-title hover:text-accent">{displayTitle(cluster)}</a>{hasBuyingEvidence(cluster) ? <Tag tone="evidence">购买来源待核实</Tag> : <Tag>预算未证实</Tag>}</div><p className="opportunity-problem">{cluster.problem}</p></div>
    <div className="opportunity-meta"><strong>目标人群</strong><span className="line-clamp-2">{cluster.who || '待确认'}</span></div>
    <div className="opportunity-meta"><strong>证据强度</strong><span className="text-evidence">{summary.threads} 条讨论 · {summary.communities} 个社区</span></div>
    <a href={`#/cluster/${cluster.id}`} className="opportunity-action">查看 <ArrowUpRight className="inline size-3" aria-hidden="true" /></a>
  </div>
}

function SourceHealth({ run }) {
  const sources = run?.sources ?? []
  return <section className="panel"><div className="panel-header"><h3>来源状态</h3><p>{sources.length ? `${sources.filter(source => !source.error && !source.degraded).length} / ${sources.length} 正常` : '暂无运行'}</p></div><div className="source-health-list">
    {sources.length ? sources.map(source => <div className="source-health-row" key={source.source}><span className="flex items-center gap-2"><span className={`status-dot ${source.error || source.degraded ? 'is-warn' : ''}`} />{source.source}</span><span>{source.error ? '失败' : `${source.fetched} 条`}</span></div>) : <p className="py-3 text-xs text-muted">运行一次后显示抓取数量和健康状态。</p>}
  </div></section>
}

export function Latest({ data }) {
  const run = data.runs[0]
  const opportunities = topOpportunities(data)
  const tracked = data.clusters.filter(cluster => cluster.status !== 'demoted').length
  const buying = data.clusters.filter(hasBuyingEvidence).length
  const newSignals = data.signals.filter(signal => run?.new_signals?.includes(signal.id))
  return <div className="page-stack">
    <div className="page-intro"><div><p className="header-context">{run?.finished_at ? <time className="num">{formatDateTime(run.finished_at).split(' ')[0]}</time> : '基线数据'}</p><h2>今天的研究</h2><p className="mt-1">从公开讨论里筛出值得联系买方、验证预算和成本的产品机会。</p></div><p className="max-w-sm">优先读“需要你判断”的条目。综合分只是内部判断，不代表市场规模或成交概率。</p></div>
    <div className="metrics-strip" aria-label="研究摘要"><Metric label="新信号" value={run?.new_signals?.length ?? 0} note="最近一期" icon={WavesIcon} /><Metric label="需要你判断" value={opportunities.length} note="证据与核查达标" icon={CircleAlert} tone="accent" /><Metric label="购买来源" value={buying} note="需打开原文核实" icon={CheckCircle2} /><Metric label="持续追踪" value={tracked} note="活跃 + 观察" icon={Clock3} /></div>
    <section className="panel"><div className="panel-header"><div><h3>需要你判断</h3><p className="mt-1">先验证付款方和预算，再决定是否开发</p></div><a href="#/ledger" className="header-link">打开机会库 <ArrowUpRight className="size-3" aria-hidden="true" /></a></div><div className="opportunity-table">{opportunities.length ? opportunities.slice(0, 5).map(cluster => <OpportunityRow key={cluster.id} cluster={cluster} />) : <div className="p-6 text-sm text-muted">暂无达到门槛的候选。证据不足时，空白比虚假的推荐更有用。</div>}</div></section>
    <div className="dashboard-grid"><div className="grid gap-6"><section className="panel"><div className="panel-header"><div><h3>新兴信号</h3><p className="mt-1">单条证据弱，但值得继续盯</p></div><a href="#/signals" className="header-link">查看全部 <ArrowUpRight className="size-3" aria-hidden="true" /></a></div>{newSignals.length ? <ul className="side-list">{newSignals.slice(0, 4).map(signal => <li key={signal.id}><a href="#/signals" className="hover:text-accent">{signal.title}</a><p>{signal.why_watch}</p></li>)}</ul> : <p className="px-4 py-5 text-sm text-muted">本期没有新信号。历史观察项不会冒充今天的新发现。</p>}</section></div><div className="grid content-start gap-6"><SourceHealth run={run} /><section className="panel"><div className="panel-header"><h3>研究入口</h3><Filter className="size-4 text-muted" aria-hidden="true" /></div><div className="flex flex-wrap gap-2 p-4"><a className="filter-link" href="#/ledger?lens=buying">有购买来源</a><a className="filter-link" href="#/ledger?lens=changed">本期有变化</a><a className="filter-link" href="#/ledger?lens=saved">我的验证清单</a></div></section></div></div>
    <details className="run-details"><summary>数据健康与运行记录</summary><RunStatus run={run} data={data} /></details>
  </div>
}

function WavesIcon(props) { return <Database {...props} /> }
