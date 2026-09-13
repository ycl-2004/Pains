import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseResearch, ledgerHash, displayTitle, evidenceSummary } from '../src/lib/research.js'

test('validation backups retain only supported fields and reject unsafe shapes', () => {
  const note = { stage: 'pilot', note: '买方确认试点', updated: '2026-09-13' }
  assert.deepEqual(parseResearch(JSON.stringify({ 'OP-001': note })), { 'OP-001': note })
  for (const raw of ['null', '[]', '{"__proto__":{}}', '{"OP-001":{"stage":"invalid","note":"x"}}']) assert.throws(() => parseResearch(raw))
})
test('filters round trip in shareable hash links including Chinese and punctuation', () => {
  const hash = ledgerHash({ q: '财务 & 发票', selected: 'OP-001', industry: 'all' })
  const params = new URLSearchParams(hash.split('?')[1])
  assert.equal(params.get('q'), '财务 & 发票')
  assert.equal(params.get('selected'), 'OP-001')
  assert.equal(params.has('industry'), false)
})
test('titles are excerpts, counts are discussions rather than buyers', () => {
  assert.equal(displayTitle({ name: '账单导出：每周人工复制' }), '账单导出')
  const summary = evidenceSummary({ evidence: [
    { url: 'https://a', platform: 'HN', date: '2026-09-01', counts_as_demand: true },
    { url: 'https://a', platform: 'HN', date: '2026-09-01', counts_as_demand: true },
    { url: 'https://b', platform: 'Vendor', counts_as_demand: false },
  ] })
  assert.equal(summary.threads, 1)
  assert.equal(summary.communities, 1)
})
