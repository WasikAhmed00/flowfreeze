import { useEffect, useState } from 'react'
import { api } from './api.js'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import IncidentDetail from './pages/IncidentDetail.jsx'
import Simulator from './pages/Simulator.jsx'
import Evaluation from './pages/Evaluation.jsx'
import AuditLog from './pages/AuditLog.jsx'

const nav = [
  { id: 'dashboard', label: 'Overview', icon: '◫' },
  { id: 'incident', label: 'Incidents', icon: '⌁' },
  { id: 'simulator', label: 'What-if lab', icon: '◌' },
  { id: 'evaluation', label: 'Evaluation', icon: '▥' },
  { id: 'audit', label: 'Audit trail', icon: '≡' },
]

export default function App() {
  const [authenticated, setAuthenticated] = useState(false)
  const [page, setPage] = useState('dashboard')
  const [incidents, setIncidents] = useState([])
  const [incidentTotal, setIncidentTotal] = useState(0)
  const [scenarioId, setScenarioId] = useState('')
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState('')
  const [incidentsLoading, setIncidentsLoading] = useState(true)
  const [refreshToken, setRefreshToken] = useState(0)

  useEffect(() => {
    const handleNavigate = (event) => setPage(event.detail || 'dashboard')
    window.addEventListener('flowfreeze:navigate', handleNavigate)
    return () => window.removeEventListener('flowfreeze:navigate', handleNavigate)
  }, [])

  useEffect(() => {
    let alive = true
    setIncidentsLoading(true)
    setError('')
    const loadIncidents = async () => {
      try {
        const firstPage = await api('/api/incidents?limit=200&offset=0')
        const offsets = []
        for (let offset = firstPage.incidents.length; offset < firstPage.total; offset += 200) offsets.push(offset)
        const remainingPages = await Promise.all(offsets.map((offset) => api(`/api/incidents?limit=200&offset=${offset}`)))
        const incidentData = { ...firstPage, incidents: [...firstPage.incidents, ...remainingPages.flatMap((page) => page.incidents)] }
        if (!alive) return
        const nextIncidents = incidentData.incidents || []
        setIncidents(nextIncidents)
        setIncidentTotal(incidentData.total || 0)
        setScenarioId((current) => nextIncidents.some((item) => item.scenario_id === current) ? current : nextIncidents[0]?.scenario_id || '')
      } catch (e) {
        if (!alive) return
        setIncidents([])
        setIncidentTotal(0)
        setScenarioId('')
        setError((current) => [current, `Incidents: ${e.message}`].filter(Boolean).join(' '))
      } finally {
        if (alive) setIncidentsLoading(false)
      }
    }
    const loadMetrics = async () => {
      try {
        const metricData = await api('/api/metrics')
        if (alive) setMetrics(metricData)
      } catch (e) {
        if (!alive) return
        setMetrics(null)
        setError((current) => [current, `Metrics: ${e.message}`].filter(Boolean).join(' '))
      }
    }
    loadIncidents()
    loadMetrics()
    return () => { alive = false }
  }, [refreshToken])

  if (!authenticated) return <Login onContinue={() => setAuthenticated(true)} />

  const selected = incidents.find((item) => item.scenario_id === scenarioId)
  const chooseIncident = (id) => { setScenarioId(id); setPage('incident') }
  const refresh = () => setRefreshToken((n) => n + 1)

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup"><div className="brand-mark">F</div><div><b>flowfreeze</b><small>UPAY BD · HACKATHON</small></div></div>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {nav.map((item) => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => setPage(item.id)}>
            <span className="nav-icon">{item.icon}</span>{item.label}{item.id === 'incident' && <span className="nav-count">{incidentTotal}</span>}
          </button>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="side-safety"><span className="safety-icon">✳</span><div><b>Synthetic environment</b><small>No live wallets connected</small></div></div>
          <div className="profile-row"><div className="avatar">DA</div><div><b>Demo analyst</b><small>Local session</small></div><button className="icon-button logout" title="Sign out" onClick={() => setAuthenticated(false)}>↗</button></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>FlowFreeze</span><span className="crumb-slash">/</span><b>{nav.find((n) => n.id === page)?.label || 'Incident review'}</b></div>
          <div className="topbar-right"><span className="environment-pill"><i /> DEMO MODE</span><button className="icon-button" aria-label="Refresh data" onClick={refresh}>↻</button><div className="top-avatar">DA</div></div>
        </header>
        {error && <div className="global-error" role="alert"><strong>Some workspace data could not be loaded</strong><span>{error}</span><button onClick={refresh}>Retry</button></div>}
        <div className="page-wrap">
          {page === 'dashboard' && <Dashboard incidents={incidents} totalCount={incidentTotal} metrics={metrics} onSelect={chooseIncident} loading={incidentsLoading} />}
          {page === 'incident' && <IncidentDetail scenarioId={scenarioId} incident={selected} onRefresh={refresh} />}
          {page === 'simulator' && <Simulator incidents={incidents} scenarioId={scenarioId} onSelect={setScenarioId} onRefresh={refresh} />}
          {page === 'evaluation' && <Evaluation metrics={metrics} onRefresh={refresh} />}
          {page === 'audit' && <AuditLog refreshToken={refreshToken} />}
        </div>
        <footer className="page-footer"><span>FlowFreeze prototype · synthetic data only</span><span>Recommendations are for analyst review, not wallet execution.</span></footer>
      </main>
    </div>
  )
}
