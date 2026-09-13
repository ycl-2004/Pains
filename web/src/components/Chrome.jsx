import { Archive, BookOpen, CheckSquare, CircleDot, FileText, LayoutDashboard, Monitor, Moon, Settings2, Sun, Waves } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formatDateTime } from '../lib/data'

const THEMES = ['system', 'light', 'dark']
const THEME_ICON = { system: Monitor, light: Sun, dark: Moon }
const THEME_LABEL = { system: '跟随系统', light: '浅色', dark: '深色' }
const NAV_ITEMS = [
  ['latest', '今日研究', LayoutDashboard],
  ['ledger', '机会库', BookOpen],
  ['signals', '新兴信号', Waves],
  ['validation', '验证清单', CheckSquare],
  ['demoted', '已归档', Archive],
]
const PAGE_TITLES = { latest: '今天的研究', ledger: '机会库', signals: '新兴信号', validation: '验证清单', demoted: '已归档', method: '方法与局限' }

function readTheme() {
  try {
    const value = localStorage.getItem('pain-radar-theme')
    return THEMES.includes(value) ? value : 'system'
  } catch {
    return 'system'
  }
}

function ThemeToggle() {
  const [theme, setTheme] = useState(readTheme)
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') delete root.dataset.theme
    else root.dataset.theme = theme
    try { localStorage.setItem('pain-radar-theme', theme) } catch { /* optional */ }
  }, [theme])
  const Icon = THEME_ICON[theme]
  return <button type="button" onClick={() => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length])} className="theme-toggle" aria-label={`主题：${THEME_LABEL[theme]}，点击切换`}>
    <Icon className="size-3.5" aria-hidden="true" /> <span>{THEME_LABEL[theme]}</span>
  </button>
}

function NavLink({ id, label, Icon, current, count }) {
  const active = current === id || (id === 'ledger' && current === 'cluster')
  return <a href={`#/${id}`} aria-current={active ? 'page' : undefined} className={`sidebar-link ${active ? 'is-active' : ''}`}>
    <Icon className="size-4" aria-hidden="true" /><span>{label}</span>{count != null && <span className="sidebar-count">{count}</span>}
  </a>
}

export function Sidebar({ data, current, counts }) {
  const latest = data.runs[0]
  const sourceStats = latest?.sources ?? []
  const healthy = sourceStats.filter(source => !source.error && !source.degraded).length
  return <aside className="app-sidebar">
    <a href="#/latest" className="brand-lockup" aria-label="返回今日研究">
      <span className="brand-mark"><CircleDot className="size-5" aria-hidden="true" /></span>
      <span><strong>痛点雷达<span className="text-accent">.</span></strong><small>发现值得验证的需求</small></span>
    </a>
    <nav className="sidebar-nav" aria-label="工作区">
      {NAV_ITEMS.map(([id, label, Icon]) => <NavLink key={id} id={id} label={label} Icon={Icon} current={current} count={id === 'demoted' ? counts.demoted : id === 'ledger' ? counts.ledger : id === 'signals' ? counts.signals : undefined} />)}
    </nav>
    <div className="sidebar-spacer" />
    <div className="sidebar-health">
      <div className="sidebar-health-title"><span>来源状态</span><span className={healthy === sourceStats.length ? 'status-good' : 'status-warn'}>{sourceStats.length ? `${healthy} / ${sourceStats.length} 正常` : '未运行'}</span></div>
      {sourceStats.slice(0, 5).map(source => <div className="sidebar-source" key={source.source}><span className={`status-dot ${source.error || source.degraded ? 'is-warn' : ''}`} />{source.source}</div>)}
      {!sourceStats.length && <p className="sidebar-empty">运行后显示来源健康度</p>}
    </div>
    <nav className="sidebar-secondary" aria-label="其他"><NavLink id="method" label="方法与设置" Icon={Settings2} current={current} /></nav>
    <div className="sidebar-identity"><span className="identity-avatar">YC</span><span><strong>研究工作区</strong><small>本地证据台账</small></span></div>
  </aside>
}

export function Header({ data, section = 'latest' }) {
  const updated = data.runs.find((run) => !run.status || run.status === 'success')?.finished_at
  return <header className="workspace-header">
    <div><p className="header-context">痛点雷达 · 研究工作区</p><h1>{PAGE_TITLES[section] ?? PAGE_TITLES.latest}</h1></div>
    <div className="header-actions"><span className="last-updated">{updated ? <>最后更新 · <time className="num">{formatDateTime(updated)}</time></> : '尚无成功运行记录'}</span><a href="#/method" className="header-link"><FileText className="size-3.5" aria-hidden="true" />运行说明</a><ThemeToggle /></div>
  </header>
}

export function Tabs({ current, counts }) {
  return <nav className="mobile-tabs lg:hidden" aria-label="主导航">
    {NAV_ITEMS.map(([id, label, Icon]) => <a key={id} href={`#/${id}`} aria-current={(current === id || (id === 'ledger' && current === 'cluster')) ? 'page' : undefined} className="mobile-tab"><Icon className="size-4" aria-hidden="true" /><span>{label}</span>{counts[id] != null && <small>{counts[id]}</small>}</a>)}
  </nav>
}

export function Footer() {
  return <footer className="workspace-footer"><p>公开讨论的转述和原文链接归原作者及平台所有。分数不是市场规模；做决定前请核对证据原文。</p></footer>
}

export function SectionTitle({ children, note }) {
  return <div className="section-heading"><h2>{children}</h2>{note && <p>{note}</p>}</div>
}

export function Tag({ children, tone = 'plain', title }) {
  const tones = { plain: 'tag-plain', accent: 'tag-accent', evidence: 'tag-evidence', success: 'tag-success' }
  return <span title={title} className={`tag ${tones[tone] ?? tones.plain}`}>{children}</span>
}
