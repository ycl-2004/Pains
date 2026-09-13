import { Monitor, Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formatDateTime } from '../lib/data'

const THEMES = ['system', 'light', 'dark']
const THEME_ICON = { system: Monitor, light: Sun, dark: Moon }
const THEME_LABEL = { system: '跟随系统', light: '浅色', dark: '深色' }

function readTheme() {
  try {
    return localStorage.getItem('pain-radar-theme') || 'system'
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
    try {
      localStorage.setItem('pain-radar-theme', theme)
    } catch {
      // Storage can be unavailable (private mode); the theme still applies for this visit.
    }
  }, [theme])
  const Icon = THEME_ICON[theme]
  return (
    <button
      type="button"
      onClick={() => setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length])}
      className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs text-muted transition-colors hover:text-ink"
      aria-label={`主题：${THEME_LABEL[theme]}，点击切换`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {THEME_LABEL[theme]}
    </button>
  )
}

export function Header({ data }) {
  const updated = data.runs[0]?.finished_at ?? data.generated_at
  return (
    <header>
      <div className="mx-auto flex max-w-5xl flex-wrap items-end justify-between gap-x-6 gap-y-3 px-4 pt-8 pb-5 sm:px-6">
        <div>
          <div className="flex items-baseline gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">痛点雷达</h1>
            <span className="font-mono text-xs text-muted">pain-radar</span>
          </div>
          <p className="mt-1 max-w-xl text-sm text-muted">从公开讨论里找反复出现、现有方案没解决好、能用代码解决的问题。</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted">
          <span>
            数据更新于 <time className="num">{formatDateTime(updated)}</time>
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

export function Tabs({ current, counts }) {
  const tabs = [
    ['latest', '最新一期'],
    ['ledger', '痛点台账', counts.ledger],
    ['signals', '新兴信号', counts.signals],
    ['demoted', '已降级', counts.demoted],
    ['method', '方法与局限'],
  ]
  const active = current === 'cluster' ? 'ledger' : current
  return (
    <nav className="sticky top-0 z-20 border-y border-line bg-bg" aria-label="主导航">
      <div className="no-scrollbar mx-auto flex max-w-5xl gap-6 overflow-x-auto px-4 sm:px-6">
        {tabs.map(([id, label, count]) => (
          <a
            key={id}
            href={`#/${id}`}
            aria-current={active === id ? 'page' : undefined}
            className={`relative shrink-0 py-3 text-sm transition-colors after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:transition-colors ${
              active === id ? 'text-ink after:bg-accent' : 'text-muted hover:text-ink after:bg-transparent'
            }`}
          >
            {label}
            {count != null && <span className="num ml-1.5 text-xs text-muted">{count}</span>}
          </a>
        ))}
      </div>
    </nav>
  )
}

export function Footer() {
  return (
    <footer className="border-t border-line">
      <p className="mx-auto max-w-5xl px-4 py-8 text-xs leading-relaxed text-muted sm:px-6">
        页面只收录公开讨论的转述和原文链接，内容版权归原作者和平台所有。分数是基于有限样本的判断，不是市场测算；做决定前请点开证据原文核对。
      </p>
    </footer>
  )
}

export function SectionTitle({ children, note }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="text-base font-semibold">{children}</h2>
      {note && <p className="text-xs text-muted">{note}</p>}
    </div>
  )
}

export function Tag({ children, tone = 'plain', title }) {
  const tones = {
    plain: 'border-line text-muted',
    accent: 'border-transparent bg-accent-soft text-accent',
  }
  return (
    <span title={title} className={`inline-flex items-center rounded border px-1.5 py-px text-[11px] leading-5 whitespace-nowrap ${tones[tone]}`}>
      {children}
    </span>
  )
}
