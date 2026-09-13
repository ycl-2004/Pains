import { ArrowLeft, CheckSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ClusterDetail, EvidenceList, OpportunitySummary, OriginList } from '../components/ClusterDetail'
import { SectionTitle, Tag } from '../components/Chrome'
import { shortLabel } from '../lib/data'
import { LEVEL, MERGE_ACTION, STATUS } from '../lib/labels'
import { displayTitle, readResearch, STAGES } from '../lib/research'

export function ClusterPage({ data, id }) {
  const cluster = data.clusters.find((item) => item.id === id)
  const back = new URLSearchParams(window.location.hash.split('?')[1]).get('return')
  return (
    <div className="mx-auto max-w-3xl pt-6">
      <a href={back?.startsWith('#/ledger') ? back : '#/ledger'} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        痛点台账
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
      <SectionTitle note="单条证据弱但值得盯的变化；复查后可晋升为观察簇或放弃">新兴信号</SectionTitle>
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
      <SectionTitle note="降级不删除：保留反证，避免下次把同一个伪机会重新当成新发现">已降级</SectionTitle>
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
    <div className="page-intro"><div><p className="header-context">研究工作区</p><h2>验证清单</h2><p className="mt-1">把公开证据变成自己的访谈、预算和试点记录。这里的判断不会改变公共台账。</p></div></div>
    <section className="panel"><div className="panel-header"><div><h3>我的验证记录</h3><p className="mt-1">仅保存在当前浏览器，可在机会详情中编辑</p></div><a className="header-link" href="#/ledger">添加机会 <span aria-hidden="true">↗</span></a></div>{rows.length ? <ul className="side-list">{rows.map(({ cluster, id, record }) => <li key={id}><div className="flex flex-wrap items-center justify-between gap-3"><a href={`#/cluster/${id}`} className="text-sm hover:text-accent">{displayTitle(cluster)}</a><Tag tone={record.stage === 'pilot' ? 'success' : record.stage === 'rejected' ? 'plain' : 'accent'}>{STAGES[record.stage]}</Tag></div><p>{record.note || '还没有文字记录。'}</p><p className="mt-2 num text-[10px]">{record.updated ? `更新于 ${record.updated.slice(0, 10)}` : '尚未更新'}</p></li>)}</ul> : <div className="p-8 text-center"><CheckSquare className="mx-auto size-7 text-muted" aria-hidden="true" /><h3 className="mt-3 text-sm font-semibold">还没有验证记录</h3><p className="mt-1 text-xs text-muted">打开一个机会，在详情页记录买方、成本和试点结果。</p><a href="#/ledger" className="action mt-4">浏览机会库</a></div>}</section>
    <p className="text-xs text-muted">记录存储在浏览器的 pain-radar-research-v1 中；清除浏览器数据前请导出备份。</p>
  </div>
}

const PIPELINE = [
  ['抓取', '公开接口有限采样；业务社区优先。每次最多复查 5 条旧证据，每条成功复查至少间隔 7 天，失败退避重试。GitHub / HN 可刷新原文与回复，WordPress 仅刷新回复。'],
  ['规则预筛', '用痛点关键词（中英文）和互动量粗筛，目的是不漏，不负责判断。'],
  ['初筛', '业务来源加权轮询，优先具体成本与买方信号；已解决内容保留为反证，信息不足时补评论。'],
  ['补评论', '给互动最高的条目拉高赞回复，变通做法和付费信号大多在回复里。'],
  ['聚类与打分', '强模型按根因并入已有簇或新建簇，先写反方论证再打分，写明分数变化的理由。'],
  ['现有方案核查', '核查新簇、分数变化和每周到期项；已解决则降级。新簇先观察，证据与核查达标才进入候选。'],
  ['台账', '每期保存运行报告和台账快照，同一簇一期最多计一次检出。'],
]

const RULES = [
  '行为优先于观点：自建脚本、手工表格、已经在付费，比“我希望有个工具”更有分量。',
  '卖方回帖、产品发布和官方文档不计入需求；同一事故、同一帖子的转载不算多个用户；重复抓到同一 URL 不算再次检出。',
  '观察和推断分开：证据只写原文里出现的内容（转述），根因和机会假设标为推断。',
  '先写反方论证再打分；综合分是判断，不是加权平均。',
  '降级保留理由，方便以后被新证据推翻。',
]

const LIMITS = [
  'Reddit 没有覆盖：新 API 需要人工审批，免登录 JSON 接口据报道已关闭，云端定时任务抓不到。X、Discord、Product Hunt、应用商店评论也没有覆盖。',
  '新增 Make、n8n 和 WooCommerce 支持社区，仍偏软件使用者和英语。RSS 每条订阅只返回有限帖子，不能代表整个行业。',
  '分数来自有限样本和模型判断，没有用户访谈、成交或市场规模数据。',
  'LLM 的聚类和转述可能出错，重要结论请点开原文核对。',
  '第 0 期基线里标注“agy-pp 记录，未复核”的证据，原文没有被重新打开确认过。',
]

export function Method({ data }) {
  const logByOrigin = Object.groupBy(data.merge_log, (record) => record.origin)
  return (
    <div className="max-w-3xl space-y-12 pt-8">
      <section>
        <SectionTitle>数据来源</SectionTitle>
        <dl className="mt-3 divide-y divide-line border-y border-line">
          {data.sources.map((source) => (
            <div key={source.name} className="grid gap-1 py-3 sm:grid-cols-[9rem_1fr]">
              <dt className="text-sm font-medium">{source.label}</dt>
              <dd className="text-sm text-muted">{source.description}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <SectionTitle>每期怎么跑</SectionTitle>
        <ol className="mt-3 space-y-3">
          {PIPELINE.map(([title, text], index) => (
            <li key={title} className="grid grid-cols-[2rem_1fr] gap-2 text-sm">
              <span className="num font-mono text-muted">{index + 1}</span>
              <p>
                <span className="font-medium">{title}</span>
                <span className="text-muted">：{text}</span>
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <SectionTitle>判断规则</SectionTitle>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed marker:text-muted">
          {RULES.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle>评分标准</SectionTitle>
        <dl className="mt-3 space-y-2 text-sm">
          {Object.entries(data.rubric.dimensions).map(([key, text]) => (
            <div key={key} className="grid gap-1 sm:grid-cols-[7rem_1fr]">
              <dt className="font-medium">{shortLabel(text)}</dt>
              <dd className="text-muted">{text.split('：').slice(1).join('：')}</dd>
            </div>
          ))}
        </dl>
        <h3 className="mt-6 text-sm font-medium">现有方案分类</h3>
        <dl className="mt-2 space-y-2 text-sm">
          {Object.entries(data.rubric.classes).map(([key, text]) => (
            <div key={key} className="grid gap-1 sm:grid-cols-[7rem_1fr]">
              <dt className="font-medium">{key} · {shortLabel(text)}</dt>
              <dd className="text-muted">{text.split('：').slice(1).join('：')}</dd>
            </div>
          ))}
        </dl>
        <h3 className="mt-6 text-sm font-medium">置信度</h3>
        <dl className="mt-2 space-y-2 text-sm">
          {Object.entries(data.rubric.levels).map(([key, text]) => (
            <div key={key} className="grid gap-1 sm:grid-cols-[7rem_1fr]">
              <dt className="font-medium">{LEVEL[key]}</dt>
              <dd className="text-muted">{text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <SectionTitle>已知局限</SectionTitle>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed marker:text-muted">
          {LIMITS.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </section>

      <section>
        <SectionTitle note="三份研究里的每个结论去了哪里">第 0 期基线怎么来的</SectionTitle>
        {Object.entries(logByOrigin).map(([origin, records]) => (
          <div key={origin} className="mt-5">
            <h3 className="font-mono text-sm">{origin}</h3>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[34rem] text-left text-sm">
                <thead className="text-xs text-muted">
                  <tr className="border-b border-line">
                    <th className="py-2 pr-3 font-normal">原结论</th>
                    <th className="py-2 pr-3 font-normal">处理</th>
                    <th className="py-2 pr-3 font-normal">去向</th>
                    <th className="py-2 font-normal">理由</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {records.map((record) => (
                    <tr key={record.old_id} className="align-top">
                      <td className="py-2 pr-3">{record.old_name}</td>
                      <td className="py-2 pr-3 whitespace-nowrap text-muted">{MERGE_ACTION[record.action]}</td>
                      <td className="py-2 pr-3 font-mono text-xs whitespace-nowrap">
                        {record.new_id.startsWith('OP-') ? <a href={`#/cluster/${record.new_id}`} className="underline decoration-line underline-offset-4 hover:decoration-accent">{record.new_id}</a> : record.new_id}
                      </td>
                      <td className="py-2 text-muted">{record.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
