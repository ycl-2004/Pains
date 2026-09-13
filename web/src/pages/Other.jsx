import { ArrowLeft } from 'lucide-react'
import { ClusterDetail, EvidenceList, OriginList } from '../components/ClusterDetail'
import { SectionTitle, Tag } from '../components/Chrome'
import { shortLabel } from '../lib/data'
import { LEVEL, MERGE_ACTION, STATUS } from '../lib/labels'

export function ClusterPage({ data, id }) {
  const cluster = data.clusters.find((item) => item.id === id)
  return (
    <div className="pt-6">
      <a href="#/ledger" className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
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
          <h2 className="mt-2 mb-8 max-w-3xl text-2xl leading-snug font-semibold tracking-tight">{cluster.name}</h2>
          <ClusterDetail cluster={cluster} rubric={data.rubric} />
        </article>
      ) : (
        <p className="py-10 text-sm text-muted">找不到 {id}，它可能已被合并。</p>
      )}
    </div>
  )
}

export function Signals({ data }) {
  const signals = [...data.signals].sort((a, b) => b.last_detected.localeCompare(a.last_detected))
  return (
    <div className="pt-8">
      <SectionTitle note="单条证据弱但值得盯的变化；跨社区重复出现后会升级为簇">新兴信号</SectionTitle>
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

const PIPELINE = [
  ['抓取', '各数据源抓最近 72 小时的帖子、评论和 issue，原始数据按日期落盘，已看过的条目跳过。'],
  ['规则预筛', '用痛点关键词（中英文）和互动量粗筛，目的是不漏，不负责判断。'],
  ['初筛', '便宜模型逐条判断：有没有具体的人、具体的动作、具体的损失，能不能用代码解决。'],
  ['补评论', '给互动最高的条目拉高赞回复，变通做法和付费信号大多在回复里。'],
  ['聚类与打分', '强模型按根因并入已有簇或新建簇，先写反方论证再打分，写明分数变化的理由。'],
  ['现有方案核查', '对新簇和分数变化大的簇联网搜索竞品、原生功能和价格门槛。'],
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
  '来源偏开发者、偏英语；中文目前只有 V2EX。',
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
