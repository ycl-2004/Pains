export const RESEARCH_KEY = 'pain-radar-research-v1'
export const STAGES = { saved: '待验证', watching: '继续观察', rejected: '不成立', pilot: '有付费试点' }

export function parseResearch(raw) {
  const data = JSON.parse(raw || '{}')
  if (!data || Array.isArray(data) || typeof data !== 'object') throw new Error('备份格式不正确')
  const result = {}
  for (const [id, record] of Object.entries(data)) {
    if (!/^OP-\d+$/.test(id) || !record || !Object.hasOwn(STAGES, record.stage)
      || typeof record.note !== 'string' || record.note.length > 20000) throw new Error('备份包含无效记录')
    result[id] = { stage: record.stage, note: record.note, updated: String(record.updated || '') }
  }
  return result
}

export function readResearch() {
  return parseResearch(localStorage.getItem(RESEARCH_KEY))
}

export function evidenceSummary(cluster) {
  const demand = (cluster.evidence || []).filter(e => e.counts_as_demand)
  const dates = demand.map(e => e.date).filter(Boolean).sort()
  return {
    threads: new Set(demand.map(e => e.url)).size,
    communities: new Set(demand.map(e => e.platform)).size,
    span: dates.length ? `${dates[0]} — ${dates.at(-1)}` : '日期待核对',
  }
}

// A display excerpt, not a new AI-generated claim. The complete title remains in the dossier.
export function displayTitle(cluster) {
  if (cluster.short_title) return cluster.short_title
  const first = cluster.name.split(/[：；。]/)[0]
  return first.length <= 32 ? first : `${first.slice(0, 32)}…`
}

export function ledgerHash(params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v && v !== 'all' && v !== 'open' && v !== 'opportunity'))
  return `#/ledger${query.size ? `?${query}` : ''}`
}
