import { useState } from 'react'
import { parseResearch, STAGES } from '../lib/research'
import { useResearch } from '../lib/useResearch'

export function ResearchBackup({ research }) {
  const [message, setMessage] = useState('')
  function download() {
    try {
      const url = URL.createObjectURL(new Blob([JSON.stringify(research.backup(), null, 2)], { type: 'application/json' }))
      const a = document.createElement('a')
      a.href = url; a.download = `pain-radar-research-${new Date().toISOString().slice(0, 10)}.json`; a.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMessage('备份已导出')
    } catch (error) { setMessage(`导出失败：${error.message}`) }
  }
  async function restore(event) {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      if (file.size > 2000000) throw new Error('备份文件过大')
      const incoming = parseResearch(await file.text())
      setMessage(research.restore(incoming) ? '已导入，已有记录保持不变' : '导入未保存，请导出备份后检查存储空间。')
    } catch (error) { setMessage(`导入失败：${error.message}`) }
    event.target.value = ''
  }
  return <div>
    <div className="flex flex-wrap items-center gap-3">
      <button className="filter-link" onClick={download} disabled={research.unreadable}>导出全部记录</button>
      <label className="filter-link cursor-pointer">导入备份<input className="sr-only" type="file" accept="application/json,.json" onChange={restore} /></label>
    </div>
    {message && <p role="status" className="mt-2 text-xs text-muted">{message}</p>}
  </div>
}

export function ValidationNotebook({ id, headingLevel = 2 }) {
  const Heading = `h${headingLevel}`
  const research = useResearch()
  const [message, setMessage] = useState('')
  const record = research.records[id] || { stage: 'saved', note: '' }
  function save(change) { setMessage(research.save(id, change) ? '已保存' : '') }
  return <section className="dossier-section">
    <Heading>我的验证记录</Heading>
    <p className="mb-4 text-xs text-muted">仅保存在当前浏览器；可导出备份，不会同步到其他设备。</p>
    <label className="block text-xs text-muted">验证阶段
      <select className="research-input mt-1 mb-3 block" value={record.stage} onChange={e => save({ stage: e.target.value })} disabled={research.unreadable}>
        {Object.entries(STAGES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </label>
    <label className="block text-xs text-muted">访谈发现与下一步
      <textarea className="research-input mt-1" rows={4} maxLength={20000} value={record.note} onChange={e => save({ note: e.target.value })} disabled={research.unreadable} placeholder="例如：联系 3 位店主，核实每周对账耗时；询问是否愿意参与付费试点。" />
    </label>
    <div className="mt-3 flex flex-wrap items-start gap-3">
      <button className="filter-link" onClick={() => save({})} disabled={research.unreadable}>保存验证记录</button>
      <ResearchBackup research={research} />
    </div>
    {(research.error || message) && <p role="status" className="mt-2 text-xs text-muted">{research.error || message}</p>}
  </section>
}
