import { useEffect, useState } from 'react'
import { readResearch, RESEARCH_KEY } from './research'

const CHANGE_EVENT = 'pain-radar-research-change'
const read = () => {
  try { return { records: readResearch(), error: '', unreadable: false } }
  catch { return { records: {}, error: '无法读取验证记录，请检查浏览器存储权限或已有备份。', unreadable: true } }
}

export function useResearch() {
  const [state, setState] = useState(read)
  // The storage event reaches other tabs; our event also updates this tab's views.
  // https://developer.mozilla.org/en-US/docs/Web/API/Window/storage_event
  useEffect(() => {
    const update = event => {
      if (event.type !== 'storage' || event.key === RESEARCH_KEY || event.key === null) setState(read())
    }
    window.addEventListener('storage', update)
    window.addEventListener(CHANGE_EVENT, update)
    return () => {
      window.removeEventListener('storage', update)
      window.removeEventListener(CHANGE_EVENT, update)
    }
  }, [])

  function persist(records) {
    try {
      localStorage.setItem(RESEARCH_KEY, JSON.stringify(records))
      setState({ records, error: '', unreadable: false })
      window.dispatchEvent(new Event(CHANGE_EVENT))
      return true
    } catch {
      setState({ records, error: '保存失败：存储不可用或已满。请导出当前记录备份。', unreadable: false })
      return false
    }
  }

  function save(id, change) {
    const record = state.records[id] || { stage: 'saved', note: '' }
    const nextRecord = { ...record, ...change, updated: new Date().toISOString() }
    try { return persist({ ...readResearch(), [id]: nextRecord }) }
    catch {
      setState(previous => ({ ...previous, records: { ...previous.records, [id]: nextRecord }, error: '无法读取原有记录，未覆盖存储。请导出当前记录备份。' }))
      return false
    }
  }

  function restore(incoming) {
    // Local records win on conflicts, including drafts after a failed write.
    return persist({ ...incoming, ...readResearch(), ...(state.error ? state.records : {}) })
  }

  function backup() {
    if (state.unreadable) throw new Error('无法读取原有记录，暂不能导出')
    return state.error ? state.records : readResearch()
  }

  return { ...state, save, restore, backup }
}
