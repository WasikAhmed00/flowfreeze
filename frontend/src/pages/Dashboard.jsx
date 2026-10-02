import { useMemo, useState } from 'react'
import StatCard from '../components/StatCard.jsx'
import { formatDate, formatMoney } from '../api.js'

const categoryLabel = (value = '') => value.replaceAll('_', ' ')
const today = new Intl.DateTimeFormat('en-BD', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' }).format(new Date()).toUpperCase()

export default function Dashboard({ incidents, totalCount, metrics, onSelect, loading }) {
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const pageSize = 12
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    return term ? incidents.filter((row) => `${row.incident_id} ${row.scenario_id} ${row.scenario_type} ${row.incident_type}`.toLowerCase().includes(term)) : incidents
  }, [incidents, query])
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize)
  const displayedStart = filtered.length ? page * pageSize + 1 : 0
  const displayedEnd = Math.min((page + 1) * pageSize, filtered.length)
  return <>
    <div className="page-heading heading-row">
      <div><div className="eyebrow">{today} <span className="eyebrow-dot" /> SANDBOX</div><h1>Good morning, analyst</h1><p>Here’s what’s happening across your synthetic incident workspace.</p></div>
      <button className="button button-primary" onClick={() => incidents[0] && onSelect(incidents[0].scenario_id)}><span>＋</span> Review an incident</button>
    </div>
    <div className="synthetic-banner"><span className="banner-symbol">✳</span><div><b>Working with synthetic data</b><span>All wallets, transactions, and performance figures on this screen are generated for the hackathon demo.</span></div><span className="banner-tag">SANDBOX ONLY</span></div>
    <div className="stats-grid">
      <StatCard label="INCIDENT CASES" value={metrics?.dataset?.incident_count?.toLocaleString() ?? '—'} sub="Synthetic cases available" icon="⌁" tone="green" />
      <StatCard label="TRANSACTIONS TRACED" value={metrics?.dataset?.transaction_count?.toLocaleString() ?? '—'} sub="Generated ledger events" icon="⇢" tone="blue" />
      <StatCard label="WALLETS IN SCOPE" value={metrics?.dataset?.wallet_count?.toLocaleString() ?? '—'} sub="Across generated scenarios" icon="◉" tone="violet" />
      <StatCard label="SIMULATED VALUE PRESERVED" value={formatMoney(metrics?.simulations?.estimated_tainted_value_preserved_bdt)} sub={`${metrics?.simulations?.count ?? 0} recorded what-if outcomes`} icon="৳" tone="amber" />
    </div>
    <section className="content-card incident-list-card">
      <div className="section-head"><div><div className="eyebrow">CASE QUEUE</div><h2>Incident cases <span className="count-badge">{totalCount}</span></h2></div><div className="list-tools"><input className="incident-search" aria-label="Search incidents" value={query} onChange={(e) => { setQuery(e.target.value); setPage(0) }} placeholder="Search case or scenario" /><span className="filter-chip"><i /> All cases</span></div></div>
      {loading ? <div className="empty-state">Loading synthetic incident list…</div> : incidents.length === 0 ? <div className="empty-state">No incidents returned. Check that the API is connected and the database has been generated.</div> :
        <div className="table-scroll"><table className="data-table incident-table"><thead><tr><th>INCIDENT</th><th>SCENARIO TYPE</th><th>REPORTED</th><th>AMOUNT</th><th>STATUS</th><th /></tr></thead><tbody>
          {visible.map((item) => <tr key={item.incident_id} onClick={() => onSelect(item.scenario_id)} tabIndex="0" onKeyDown={(event) => event.key === 'Enter' && onSelect(item.scenario_id)}>
            <td><div className="incident-id">{item.incident_id}</div><div className="scenario-id">{item.scenario_id}</div></td>
            <td><span className={`type-pill ${item.incident_type === 'wrong_recipient_dispute' ? 'type-dispute' : ''}`}>{categoryLabel(item.scenario_type)}</span></td>
            <td className="date-cell">{formatDate(item.reported_at)}</td><td className="amount-cell">{formatMoney(item.reported_amount)}</td>
            <td><span className="status-pill"><i /> {categoryLabel(item.status || 'new')}</span></td><td className="row-arrow">↗</td>
          </tr>)}
        </tbody></table>{visible.length === 0 && <div className="empty-state">No cases match “{query}”. Try a scenario family or case ID.</div>}</div>}
      <div className="table-foot"><span>Showing {displayedStart}–{displayedEnd} of {filtered.length} matching synthetic cases</span><div className="pagination"><button disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>←</button><span>{page + 1} / {pageCount}</span><button disabled={page + 1 >= pageCount} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>→</button></div></div>
    </section>
    <div className="dashboard-bottom-grid">
      <section className="content-card quick-card"><div className="section-head compact"><div><div className="eyebrow">HOW TO READ THIS</div><h2>Analyst-first by design</h2></div><span className="round-icon">✳</span></div><p>Risk, tracing, and taint are evidence for review. FlowFreeze never makes a legal finding or executes a real wallet action.</p><button className="text-action" onClick={() => onSelect(incidents[0]?.scenario_id)}>Start with a sample case <span>→</span></button></section>
      <section className="content-card mini-stat-card"><div className="eyebrow">AUDIT ACTIVITY</div><div className="audit-total">{metrics?.audit?.decision_count ?? '—'} <span>analyst decisions</span></div><div className="mini-stat-row"><span>Approved</span><b>{metrics?.audit?.decision_counts?.approve ?? 0}</b></div><div className="mini-stat-row"><span>Modified</span><b>{metrics?.audit?.decision_counts?.modify ?? 0}</b></div><div className="mini-stat-row"><span>Rejected</span><b>{metrics?.audit?.decision_counts?.reject ?? 0}</b></div></section>
    </div>
  </>
}
