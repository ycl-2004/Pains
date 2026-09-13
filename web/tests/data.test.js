import { test } from 'node:test'
import assert from 'node:assert/strict'
import { topOpportunities, byOpportunity, validateRadarData } from '../src/lib/data.js'

const cluster = (overrides = {}) => ({
  id: 'OP-001', status: 'active', solution_class: 'B', scores: { overall: 7 },
  solution_checked_at: new Date().toISOString().slice(0, 10),
  qualification: { eligible: true, expires_at: new Date(Date.now() + 86400000).toISOString() },
  evidence: [{ counts_as_demand: true, kind: 'workaround' }, { counts_as_demand: true, kind: 'complaint' }],
  ...overrides,
})

test('stale, demoted and unchecked recommendations cannot bypass eligibility with an explicit ID', () => {
  for (const change of [{ qualification: { eligible: false } }, { qualification: null }, { qualification: { eligible: true, expires_at: '2020-01-01' } }]) {
    assert.deepEqual(topOpportunities({ clusters: [cluster(change)], runs: [{ top_opportunities: ['OP-001'] }] }), [])
  }
})

test('a checked candidate with behavior evidence is available, single complaints are not', () => {
  assert.equal(topOpportunities({ clusters: [cluster()], runs: [] }).length, 1)
  assert.equal(topOpportunities({ clusters: [cluster({ qualification: { eligible: false } })], runs: [] }).length, 0)
})

test('cited buying evidence outranks a higher speculative score', () => {
  const paid = cluster({ id: 'paid', scores: { overall: 6 }, payment_evidence: 'explicit budget', buying_evidence_urls: ['https://example.com/buyer'] })
  const speculative = cluster({ id: 'speculative', scores: { overall: 9 } })
  assert.equal([speculative, paid].sort(byOpportunity)[0].id, 'paid')
})

// Loading bad exports must reach the retry screen, not crash after fetch succeeds.
test('public data validation accepts the current export and rejects broken collections', async () => {
  const { readFile } = await import('node:fs/promises')
  const data = JSON.parse(await readFile(new URL('../public/data/radar.json', import.meta.url)))
  assert.equal(validateRadarData(data), data)
  assert.doesNotThrow(() => validateRadarData({ ...data, clusters: [], signals: [], runs: [] }))
  for (const invalid of [null, {}, { ...data, clusters: null }, { ...data, rubric: {} },
    { ...data, clusters: [null] }, { ...data, signals: [{}] }, { ...data, runs: [null] }]) {
    assert.throws(() => validateRadarData(invalid), /数据文件格式/)
  }
})
