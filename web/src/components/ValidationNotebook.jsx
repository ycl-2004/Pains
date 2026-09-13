import { useState } from 'react'
import { parseResearch, readResearch, RESEARCH_KEY, STAGES } from '../lib/research'

export function ValidationNotebook({ id }) {
  const [initial] = useState(() => {
    try { return { records: readResearch(), error: '' } }
    catch { return { records: {}, error: '无法读取验证记录' } }
  })
  const [records, setRecords] = useState(initial.records)
  const [message, setMessage] = useState(initial.error)
  const record = records[id] || { stage: 'saved', note: '' }
  function save(change) {
    if (initial.error) return
    const next = { ...records, [id]: { ...record, ...change, updated: new Date().toISOString() } }
    setRecords(next)
    try {
      const merged = { ...readResearch(), [id]: next[id] }
      localStorage.setItem(RESEARCH_KEY, JSON.stringify(merged))
      setRecords(merged)
      setMessage('已保存')
    } catch { setMessage('保存失败：存储不可用或已满。请导出当前记录备份。') }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url; a.download = `pain-radar-research-${new Date().toISOString().slice(0, 10)}.json`; a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  async function restore(event) {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      if (file.size > 2000000) throw new Error('备份文件过大')
      const incoming = parseResearch(await file.text())
      // Preserve current notes on conflict; importing is non-destructive.
      const next = { ...incoming, ...readResearch() }
      localStorage.setItem(RESEARCH_KEY, JSON.stringify(next)); setRecords(next)
      setMessage('已导入')
    } catch (error) { setMessage(`导入失败：${error.message}`) }
    event.target.value = ''
  }
  return <section className="dossier-section">
    <h3>我的验证记录</h3>
    <label className="block text-xs text-muted">验证阶段
      <select className="research-input mt-1 mb-3 block" value={record.stage} onChange={e => save({ stage: e.target.value })} disabled={Boolean(initial.error)}>
        {Object.entries(STAGES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
    <label className="block text-xs text-muted">访谈发现与下一步
      <textarea className="research-input mt-1" rows={4} maxLength={20000} value={record.note} onChange={e => save({ note: e.target.value })} disabled={Boolean(initial.error)} placeholder="例如：联系 3 位店主，核实每周对账耗时；询问是否愿意参与付费试点。" />
    </label>
    <div className="mt-3 flex flex-wrap items-center gap-3">
      <button className="filter-link" onClick={() => save({})} disabled={Boolean(initial.error)}>保存验证记录</button>
      <button className="filter-link" onClick={download}>导出全部记录</button>
      <label className="filter-link cursor-pointer">导入备份<input className="sr-only" type="file" accept="application/json,.json" onChange={restore} /></label>
    </div>
    {message && <p role="status" className="mt-2 text-xs text-muted">{message}</p>}
  </section>
}
