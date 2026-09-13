import { useEffect, useState } from 'react'

const readHash = () => window.location.hash.replace(/^#\/?/, '') || 'latest'

/** Hash routing keeps the site a plain static bundle while still giving shareable links like #/cluster/OP-001. */
export function useHashRoute() {
  const [route, setRoute] = useState(readHash)
  useEffect(() => {
    const onChange = () => {
      setRoute(readHash())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route.split('/')
}
