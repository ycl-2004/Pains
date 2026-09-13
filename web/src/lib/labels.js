// Display names for enum values coming from the pipeline. Rubric texts come from radar.json instead.

export const KIND = {
  buyer_request: '求购 / 找人修',
  budget_or_payment: '预算 / 金额',
  workaround: '变通做法',
  complaint: '一手抱怨',
  counterevidence: '反例',
  vendor_reply: '卖方回帖',
  vendor_launch: '产品发布',
  official_doc: '官方文档',
  news: '资讯',
}

export const STATUS = { active: '活跃', watch: '观察', demoted: '已降级' }

export const LEVEL = { high: '高', medium: '中', low: '低' }

export const ORIGIN = { pipeline: '自动管线' }

export const MERGE_ACTION = {
  merged: '合并',
  kept: '保留',
  watch: '转观察',
  demoted: '降级',
  signal: '转为信号',
  excluded: '排除',
}
