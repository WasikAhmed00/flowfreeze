import { useEffect, useState } from 'react'
import { api } from './api.js'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Cases from './pages/Cases.jsx'
import IncidentDetail from './pages/IncidentDetail.jsx'
import Evaluation from './pages/Evaluation.jsx'
import AuditLog from './pages/AuditLog.jsx'

const nav = [
  { id: 'dashboard', label: 'Overview', icon: '⌂' },
  { id: 'cases', label: 'Cases', icon: '▤' },
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
  const [refreshToken, setRefreshToken] = useState(0)
  useEffect(() => { const handleNavigate = (event) => setPage(event.detail || 'dashboard'); window.addEventListener('flowfreeze:navigate', handleNavigate); return () => window.removeEventListener('flowfreeze:navigate', handleNavigate) }, [])
  useEffect(() => {
    let alive = true
    Promise.all([api('/api/incidents?limit=200&offset=0'), api('/api/metrics')]).then(async ([first, metricData]) => {
      const pages = []; for (let offset = first.incidents.length; offset < first.total; offset += 200) pages.push(offset)
      const rest = await Promise.all(pages.map((offset) => api(`/api/incidents?limit=200&offset=${offset}`)))
      const all = [...(first.incidents || []), ...rest.flatMap((item) => item.incidents || [])]
      if (!alive) return
      setIncidents(all); setIncidentTotal(first.total || all.length); setMetrics(metricData); setScenarioId((current) => current || all.find((item) => item.scenario_type === 'fanout_cashout')?.scenario_id || all.find((item) => item.scenario_type === 'multi_hop')?.scenario_id || all[0]?.scenario_id || ''); setError('')
    }).catch((e) => alive && setError(e.message)); return () => { alive = false }
  }, [refreshToken])
  if (!authenticated) return <Login onContinue={() => setAuthenticated(true)} />
  const selected = incidents.find((item) => item.scenario_id === scenarioId)
  const chooseIncident = (id) => { setScenarioId(id); setPage('incident') }
  const refresh = () => setRefreshToken((n) => n + 1)
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand-lockup"><div className="brand-mark">F</div><div><b>FlowFreeze</b><small>SUPERVISOR CONSOLE</small></div></div><nav className="side-nav" aria-label="Main navigation">{nav.map((item) => <button key={item.id} className={`nav-item ${page === item.id || (item.id === 'cases' && page === 'incident') ? 'active' : ''}`} onClick={() => setPage(item.id)}><span className="nav-icon">{item.icon}</span>{item.label}{item.id === 'cases' && <span className="nav-count">{incidentTotal}</span>}</button>)}</nav><div className="sidebar-bottom"><div className="profile-row"><div className="avatar">DS</div><div><b>Demo supervisor</b><small>Local session</small></div><button className="icon-button logout" title="Sign out" aria-label="Sign out" onClick={() => setAuthenticated(false)}>↗</button></div></div></aside>
    <main className="main-area"><header className="topbar"><div className="breadcrumbs"><span>FlowFreeze</span><span className="crumb-slash">/</span><b>{page === 'incident' ? `Cases / ${selected ? selected.incident_id?.replace(/^INC-/, 'FF-') : 'Case'}` : nav.find((n) => n.id === page)?.label || 'Case review'}</b></div><div className="topbar-right"><span className="environment-pill">Demo · synthetic data</span><div className="top-avatar">DS</div></div></header>{error && <div className="global-error"><strong>API unavailable</strong><span>{error}</span><button onClick={refresh}>Retry</button></div>}<div className="page-wrap">{page === 'dashboard' && <Dashboard incidents={incidents} totalCount={incidentTotal} metrics={metrics} onSelect={chooseIncident} loading={!metrics && !error} />}{page === 'cases' && <Cases incidents={incidents} onSelect={chooseIncident} />}{page === 'incident' && <IncidentDetail scenarioId={scenarioId} incident={selected} onRefresh={refresh} />}{page === 'evaluation' && <Evaluation metrics={metrics} onRefresh={refresh} />}{page === 'audit' && <AuditLog refreshToken={refreshToken} incidents={incidents} onSelect={chooseIncident} />}</div><footer className="page-footer">FlowFreeze demo · recommendations only, no live actions.</footer></main>
  </div>
}
