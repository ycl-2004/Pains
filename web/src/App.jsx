import { Footer, Header, Tabs } from './components/Chrome'
import { useRadarData } from './lib/data'
import { useHashRoute } from './lib/useHashRoute'
import { Latest } from './pages/Latest'
import { Ledger } from './pages/Ledger'
import { ClusterPage, Demoted, Method, Signals } from './pages/Other'

const PAGES = { latest: Latest, ledger: Ledger, signals: Signals, demoted: Demoted, method: Method }

export default function App() {
  const { data, error } = useRadarData()
  const [section, param] = useHashRoute()

  if (error || !data) {
    return (
      <p className="mx-auto max-w-5xl px-4 py-16 text-sm text-muted sm:px-6">
        {error ? `数据加载失败（${error.message}）。本地请先运行 uv run python -m radar export。` : '正在加载…'}
      </p>
    )
  }

  const counts = {
    ledger: data.clusters.filter((cluster) => cluster.status !== 'demoted').length,
    signals: data.signals.filter((signal) => signal.status === 'watching').length,
    demoted: data.clusters.filter((cluster) => cluster.status === 'demoted').length,
  }
  const Page = PAGES[section] ?? Latest

  return (
    <div className="flex min-h-screen flex-col">
      <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>跳到内容</a>
      <Header data={data} />
      <Tabs current={section} counts={counts} />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-[1240px] flex-1 px-4 pb-24 sm:px-8">
        {section === 'cluster' ? <ClusterPage data={data} id={param} /> : <Page data={data} />}
      </main>
      <Footer />
    </div>
  )
}
