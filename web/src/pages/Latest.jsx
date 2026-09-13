import { ArrowUpRight, CheckCircle2, CircleAlert, Clock3, Database } from 'lucide-react'
import { Tag } from '../components/Chrome'
import { formatDateTime, hasBuyingEvidence, topOpportunities } from '../lib/data'
import { displayTitle, evidenceSummary } from '../lib/research'

function Metric({ label, value, note, icon: Icon, tone = 'plain' }) {
  return <div className="metric-cell">
    <div className="flex items-center justify-between gap-3"><span className="metric-label">{label}</span>{Icon && <Icon className={`size-4 ${tone === 'accent' ? 'text-accent' : 'text-muted'}`} aria-hidden="true" />}</div>
    <div className={`metric-value ${tone === 'accent' ? 'text-accent' : ''}`}>{value}</div>
    <div className="metric-note">{note}</div>
  </div>
}

function OpportunityRow({ cluster }) {
  const summary = evidenceSummary(cluster)
  return <div className="opportunity-row">
    <div className="min-w-0"><div className="mb-1 flex flex-wrap items-center gap-2"><a href={`#/cluster/${cluster.id}`} className="opportunity-title hover:text-accent">{displayTitle(cluster)}</a>{hasBuyingEvidence(cluster) ? <Tag tone="evidence">购买线索</Tag> : <Tag>待确认预算</Tag>}</div><p className="opportunity-problem">{cluster.problem}</p></div>
    <div className="opportunity-meta"><strong>目标客户</strong><span className="line-clamp-2">{cluster.who || '待确认'}</span></div>
    <div className="opportunity-meta"><strong>来源证据</strong><span className="text-evidence">{summary.threads} 条讨论 · {summary.communities} 个社区</span></div>
    <a href={`#/cluster/${cluster.id}`} className="opportunity-action">查看 <ArrowUpRight className="inline size-3" aria-hidden="true" /></a>
  </div>
}

function SourceHealth({ run, catalog }) {
  const sources = run?.sources ?? []
  const configured = catalog?.length ? catalog : sources.map(source => ({ name: source.source, label: source.source }))
  const rows = configured.map(source => ({ ...source, run: sources.find(item => item.source === source.name) }))
  const healthy = rows.filter(({ run: source }) => source && !source.error && !source.degraded).length
  return <section className="panel"><div className="panel-header"><h2>数据来源</h2><p>{rows.length ? `${healthy} / ${rows.length} 正常` : '暂无记录'}</p></div><div className="source-health-list">
    {rows.length ? rows.map(({ name, label, run: source }) => <div className="source-health-row" key={name}><span className="flex min-w-0 items-center gap-2"><span className={`status-dot ${!source ? 'is-pending' : source.error || source.degraded ? 'is-warn' : ''}`} /><span className="truncate">{label}</span></span><span>{!source ? '待更新' : source.error ? '失败' : source.degraded ? '部分' : `${source.fetched} 条`}</span></div>) : <p className="py-3 text-xs text-muted">暂无来源记录</p>}
  </div></section>
}

export function Latest({ data }) {
  const run = data.runs[0]
  const opportunities = topOpportunities(data)
  const tracked = data.clusters.filter(cluster => cluster.status !== 'demoted').length
  const buying = data.clusters.filter(cluster => cluster.status !== 'demoted' && hasBuyingEvidence(cluster)).length
  const watching = data.signals.filter(signal => signal.status === 'watching').sort((a, b) => b.last_detected.localeCompare(a.last_detected))
  const newSignals = watching.filter(signal => run?.new_signals?.includes(signal.id))
  const visibleSignals = newSignals.length ? newSignals : watching
  return <div className="page-stack">
    <div className="page-intro"><div><p className="header-context">{run?.finished_at ? <time className="num">{formatDateTime(run.finished_at).split(' ')[0]}</time> : '基线数据'}</p><h1>今天的研究</h1><p className="mt-1">今天值得继续验证的产品机会。</p></div></div>
    <div className="metrics-strip" aria-label="研究摘要"><Metric label="新增信号" value={run?.new_signals?.length ?? 0} note="本次运行" icon={WavesIcon} /><Metric label="重点机会" value={opportunities.length} note="本期精选" icon={CircleAlert} tone="accent" /><Metric label="购买线索" value={buying} note="已有引用" icon={CheckCircle2} /><Metric label="持续追踪" value={tracked} note="活跃记录" icon={Clock3} /></div>
    <section className="panel"><div className="panel-header"><h2>重点机会</h2><a href="#/ledger" className="header-link">打开机会库 <ArrowUpRight className="size-3" aria-hidden="true" /></a></div><div className="opportunity-table">{opportunities.length ? opportunities.slice(0, 5).map(cluster => <OpportunityRow key={cluster.id} cluster={cluster} />) : <div className="p-6 text-sm text-muted">暂无重点机会</div>}</div></section>
    <div className="dashboard-grid"><div className="grid gap-6"><section className="panel"><div className="panel-header"><h2>新兴信号</h2><a href="#/signals" className="header-link">查看全部 <ArrowUpRight className="size-3" aria-hidden="true" /></a></div>{!newSignals.length && watching.length > 0 && <p className="px-4 pt-3 text-xs text-muted">本期暂无新增，以下信号仍在观察。</p>}{visibleSignals.length ? <ul className="side-list">{visibleSignals.slice(0, 3).map(signal => <li key={signal.id}><a href="#/signals" className="hover:text-accent">{signal.title}</a><p>{signal.why_watch}</p></li>)}</ul> : <p className="px-4 py-5 text-sm text-muted">暂无观察中的信号</p>}</section></div><div className="grid content-start gap-6"><SourceHealth run={run} catalog={data.sources} /></div></div>
  </div>
}

function WavesIcon(props) { return <Database {...props} /> }
