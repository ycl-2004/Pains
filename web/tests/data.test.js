import { test } from 'node:test'
import assert from 'node:assert/strict'
import { topOpportunities, byOpportunity } from '../src/lib/data.js'

const cluster = (overrides = {}) => ({
  id: 'OP-001', status: 'active', solution_class: 'B', scores: { overall: 7 },
  solution_checked_at: new Date().toISOString().slice(0, 10),
  evidence: [{ counts_as_demand: true, kind: 'workaround' }, { counts_as_demand: true, kind: 'complaint' }],
  ...overrides,
})

test('stale, demoted and unchecked recommendations cannot bypass eligibility with an explicit ID', () => {
  for (const change of [{ status: 'demoted' }, { solution_class: 'A' }, { solution_checked_at: null }, { solution_checked_at: '2020-01-01' }]) {
    assert.deepEqual(topOpportunities({ clusters: [cluster(change)], runs: [{ top_opportunities: ['OP-001'] }] }), [])
  }
})

test('a checked candidate with behavior evidence is available, single complaints are not', () => {
  assert.equal(topOpportunities({ clusters: [cluster()], runs: [] }).length, 1)
  assert.equal(topOpportunities({ clusters: [cluster({ evidence: [{ counts_as_demand: true, kind: 'complaint' }] })], runs: [] }).length, 0)
})

test('cited buying evidence outranks a higher speculative score', () => {
  const paid = cluster({ id: 'paid', scores: { overall: 6 }, payment_evidence: 'explicit budget', buying_evidence_urls: ['https://example.com/buyer'] })
  const speculative = cluster({ id: 'speculative', scores: { overall: 9 } })
  assert.equal([speculative, paid].sort(byOpportunity)[0].id, 'paid')
})
