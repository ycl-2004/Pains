import { useEffect, useState } from 'react'

const readHash = () => window.location.hash.replace(/^#\/?/, '') || 'latest'

/** Hash routing keeps the site a plain static bundle while still giving shareable links like #/cluster/OP-001. */
export function useHashRoute() {
  const [route, setRoute] = useState(readHash)
  useEffect(() => {
    const onChange = () => {
      if (window.location.hash === '#main-content') return
      const next = readHash()
      setRoute(next)
      if (next.split('?')[0] !== route.split('?')[0]) {
        requestAnimationFrame(() => {
          document.getElementById('main-content')?.focus({ preventScroll: true })
          let saved = 0
          try { saved = sessionStorage.getItem(`pain-radar-scroll:${next}`) } catch { /* optional */ }
          window.scrollTo({ top: Number(saved) || 0 })
        })
      }
    }
    window.addEventListener('hashchange', onChange)
    const remember = () => { try { sessionStorage.setItem(`pain-radar-scroll:${route}`, String(window.scrollY)) } catch { /* optional */ } }
    window.addEventListener('scroll', remember, { passive: true })
    return () => { window.removeEventListener('hashchange', onChange); window.removeEventListener('scroll', remember) }
  }, [route])
  return route.split('?')[0].split('/')
}
