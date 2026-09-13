import { useEffect, useState } from 'react'

export function useRadarData() {
  const [state, setState] = useState({ data: null, error: null })
  useEffect(() => {
    let cancelled = false
    fetch('./data/radar.json', { cache: 'no-cache' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((data) => !cancelled && setState({ data, error: null }))
      .catch((error) => !cancelled && setState({ data: null, error }))
    return () => {
      cancelled = true
    }
  }, [])
  return state
}

const LEVEL_RANK = { high: 3, medium: 2, low: 1 }

export const overallOf = (cluster) => cluster.scores?.overall ?? -1
export const hasBuyingEvidence = (cluster) => Boolean(cluster.payment_evidence && cluster.buying_evidence_urls?.length)

export const byOpportunity = (a, b) => Number(hasBuyingEvidence(b)) - Number(hasBuyingEvidence(a)) || byOverall(a, b)

export function byOverall(a, b) {
  return (
    overallOf(b) - overallOf(a) ||
    (LEVEL_RANK[b.pain_confidence] ?? 0) - (LEVEL_RANK[a.pain_confidence] ?? 0) ||
    b.detected_runs - a.detected_runs
  )
}

export function topOpportunities(data) {
  const byId = new Map(data.clusters.map((cluster) => [cluster.id, cluster]))
  // Backend owns qualification. Client only prevents stale static exports staying recommended.
  const eligible = (cluster) => cluster?.qualification?.eligible === true
    && Date.parse(cluster.qualification.expires_at) > Date.now()
  const picked = (data.runs[0]?.top_opportunities ?? []).map((id) => byId.get(id)).filter(eligible)
  if (picked.length) return picked.sort(byOpportunity)
  return data.clusters.filter(eligible).sort(byOpportunity).slice(0, 3)
}

// Rubric texts look like "频率：多少独立的人…"; the part before the colon is the short label.
export const shortLabel = (text) => (text ?? '').split('：')[0]

export function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
