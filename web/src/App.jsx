import { Footer, Header, Sidebar, Tabs } from './components/Chrome'
import { useRadarData } from './lib/data'
import { useHashRoute } from './lib/useHashRoute'
import { Latest } from './pages/Latest'
import { Ledger } from './pages/Ledger'
import { ClusterPage, Demoted, Signals, Validation } from './pages/Other'

const PAGES = { latest: Latest, ledger: Ledger, signals: Signals, validation: Validation, demoted: Demoted }

export default function App() {
  const { data, error, retry } = useRadarData()
  const [section, param] = useHashRoute()

  if (error || !data) {
    return (
      <main className="load-state" aria-busy={!error}>
        <p className="eyebrow">痛点雷达</p>
        <h1>{error ? '暂时无法加载研究数据' : '正在加载研究数据…'}</h1>
        <p className="text-sm text-muted" role={error ? 'alert' : 'status'}>{error ? '请检查网络连接后重试。' : '正在读取机会、证据与研究记录。'}</p>
        {error && <button className="action" onClick={retry}>重新加载</button>}
      </main>
    )
  }

  const counts = {
    ledger: data.clusters.filter((cluster) => cluster.status !== 'demoted').length,
    signals: data.signals.filter((signal) => signal.status === 'watching').length,
    demoted: data.clusters.filter((cluster) => cluster.status === 'demoted').length,
  }
  const Page = PAGES[section] ?? Latest

  return (
    <div className="app-shell min-h-screen">
      <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>跳到内容</a>
      <Sidebar current={section} counts={counts} />
      <div className="app-content">
        <Header data={data} section={section} />
        <Tabs current={section} counts={counts} />
        <main id="main-content" tabIndex={-1} className="workspace-main">
          {section === 'cluster' ? <ClusterPage data={data} id={param} /> : <Page data={data} />}
        </main>
        <Footer />
      </div>
    </div>
  )
}
