
import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, ArrowUpRight, AudioLines, CircleAlert, FileSearch, GitBranch,
  LayoutDashboard, PanelTop, Settings2, UploadCloud,
} from 'lucide-react'
import { Overview, Anomalies, Services } from './monitoring'
import { Incidents, Investigation } from './incidents'
import { LogExplorer, LogDetails } from './logs'
import { DataUpload, SettingsView } from './configuration'
import { useApi } from './api'
import './styles.css'

const routes = [
  { path: '/', title: 'Overview', icon: LayoutDashboard },
  { path: '/logs', title: 'Log Explorer', icon: FileSearch },
  { path: '/incidents', title: 'Incidents', icon: CircleAlert },
  { path: '/anomalies', title: 'Anomalies', icon: Activity },
  { path: '/services', title: 'Service Map', icon: GitBranch },
  { path: '/upload', title: 'Data Upload', icon: UploadCloud },
  { path: '/settings', title: 'Settings', icon: Settings2 },
]

function App() {
  const [path, setPath] = useState(() => window.location.hash.slice(1) || '/')
  const [revision, setRevision] = useState(0)
  const refresh = () => setRevision((value) => value + 1)
  const health = useApi<{ status: string }>('/health', revision)
  useEffect(() => {
    const navigate = () => {
      setPath(window.location.hash.slice(1) || '/')
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  const [, section, id] = path.split('?')[0].split('/')
  const current = routes.find((item) => item.path === '/' + section)
  const online = health.data?.status === 'ok'

  const pageProps = { revision, refresh }
  let page
  switch (section) {
    case '':
      page = <Overview {...pageProps} />
      break
    case 'logs':
      page = id ? <LogDetails key={id} id={id} revision={revision} /> : <LogExplorer key={path} revision={revision} />
      break
    case 'incidents':
      page = id ? <Investigation key={id} id={id} {...pageProps} /> : <Incidents revision={revision} />
      break
    case 'anomalies':
      page = <Anomalies revision={revision} />
      break
    case 'services':
      page = <Services key={path} revision={revision} />
      break
    case 'upload':
      page = <DataUpload {...pageProps} />
      break
    case 'settings':
      page = <SettingsView {...pageProps} />
      break
    default:
      page = <div className="empty"><h1>Page unavailable</h1><a className="button" href="#/">Return to overview</a></div>
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content" onClick={(event) => {
      event.preventDefault()
      document.getElementById('main-content')?.focus()
    }}>Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="#/" aria-label="TraceLens overview">
        <span className="brand-mark"><AudioLines size={20} strokeWidth={2.4} /></span>
        <span>Trace<span className="brand-accent">Lens</span><small>INCIDENT INTELLIGENCE</small></span>
      </a>
      <nav aria-label="Workspace">
        {routes.map(({ path: target, title, icon: Icon }, index) => <a key={target}
          className={`nav-item ${current?.path === target ? 'active' : ''} ${index === 5 ? 'nav-group' : ''}`}
          href={'#' + target} aria-current={current?.path === target ? 'page' : undefined}>
          <Icon size={17} aria-hidden="true" /><span>{title}</span>
        </a>)}
      </nav>
      <div className="sidebar-footer">
        <span className={`connection-dot ${online ? 'online' : ''}`} />
        <div><strong>Local workspace</strong><small>{health.loading ? 'Checking API' : online ? 'API connected' : 'API unavailable'}</small></div>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar"><div><PanelTop size={16} /><span>Workspace</span><span className="slash">/</span><strong>{current?.title ?? 'Unavailable'}</strong></div>
        <a className="top-action" href="#/upload">Import logs <ArrowUpRight size={15} /></a>
      </header>
      <main id="main-content" tabIndex={-1}>{page}</main>
    </div>
  </div>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
