import { Archive, BookOpen, CheckSquare, CircleDot, LayoutDashboard, Monitor, Moon, Sun, Waves } from 'lucide-react'
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
const PAGE_TITLES = { latest: '今天的研究', ledger: '机会库', signals: '新兴信号', validation: '验证清单', demoted: '已归档', cluster: '机会详情' }

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

export function Sidebar({ current, counts }) {
  return <aside className="app-sidebar">
    <a href="#/latest" className="brand-lockup" aria-label="返回今日研究">
      <span className="brand-mark"><CircleDot className="size-5" aria-hidden="true" /></span>
      <span><strong>痛点雷达<span className="text-accent">.</span></strong><small>发现值得验证的需求</small></span>
    </a>
    <nav className="sidebar-nav" aria-label="工作区">
      {NAV_ITEMS.map(([id, label, Icon]) => <NavLink key={id} id={id} label={label} Icon={Icon} current={current} count={id === 'demoted' ? counts.demoted : id === 'ledger' ? counts.ledger : id === 'signals' ? counts.signals : undefined} />)}
    </nav>
    <div className="sidebar-spacer" />
    <div className="sidebar-identity"><span className="identity-avatar">YC</span><span><strong>YC 研究</strong><small>机会与证据</small></span></div>
  </aside>
}

export function Header({ data, section = 'latest' }) {
  const updated = data.runs.find((run) => !run.status || run.status === 'success')?.finished_at
  return <header className="workspace-header">
    <div><p className="header-context">痛点雷达</p><p className="workspace-title">{PAGE_TITLES[section] ?? PAGE_TITLES.latest}</p></div>
    <div className="header-actions"><span className="last-updated">{updated ? <>最后更新 · <time className="num">{formatDateTime(updated)}</time></> : '暂无更新记录'}</span><ThemeToggle /></div>
  </header>
}

export function Tabs({ current, counts }) {
  return <nav className="mobile-tabs lg:hidden" aria-label="主导航">
    {NAV_ITEMS.map(([id, label, Icon]) => <a key={id} href={`#/${id}`} aria-current={(current === id || (id === 'ledger' && current === 'cluster')) ? 'page' : undefined} className="mobile-tab"><Icon className="size-4" aria-hidden="true" /><span>{label}</span>{counts[id] != null && <small>{counts[id]}</small>}</a>)}
  </nav>
}

export function Footer() {
  return <footer className="workspace-footer"><p>内容来自公开来源；请核对原文。</p></footer>
}

export function SectionTitle({ children, note }) {
  return <div className="section-heading"><h1>{children}</h1>{note && <p>{note}</p>}</div>
}

export function Tag({ children, tone = 'plain', title }) {
  const tones = { plain: 'tag-plain', accent: 'tag-accent', evidence: 'tag-evidence', success: 'tag-success' }
  return <span title={title} className={`tag ${tones[tone] ?? tones.plain}`}>{children}</span>
}
