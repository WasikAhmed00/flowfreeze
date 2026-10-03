import { useEffect, useState } from 'react'
import { api, formatDate, formatMoney } from '../api.js'

const PAGE_SIZE = 25

export default function AuditLog({ refreshToken }) {
  const [audit, setAudit] = useState({ decisions: [], total: 0 })
  const [searchInput, setSearchInput] = useState('')
  const [query, setQuery] = useState('')
  const [decision, setDecision] = useState('all')
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) })
    if (decision !== 'all') params.set('decision', decision)
    if (query) params.set('q', query)
    setLoading(true)
    setError('')
    api(`/api/decisions?${params.toString()}`)
      .then((value) => {
        if (!alive) return
        setAudit(value)
        const lastPage = Math.max(0, Math.ceil((value.total || 0) / PAGE_SIZE) - 1)
        if (page > lastPage) setPage(lastPage)
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [refreshToken, decision, query, page])

  const hasFilters = Boolean(query || decision !== 'all')
  const pageCount = Math.max(1, Math.ceil((audit.total || 0) / PAGE_SIZE))
  const firstResult = audit.total ? page * PAGE_SIZE + 1 : 0
  const lastResult = Math.min((page + 1) * PAGE_SIZE, audit.total || 0)

  return <>
    <div className="page-heading"><div><div className="eyebrow">AUDIT TRAIL <span className="eyebrow-dot" /> APPEND-ONLY VIEW</div><h1>Analyst decisions</h1><p>Every decision records a reason, actor, timestamp, scenario, and proposed simulated amount.</p></div></div>
    <div className="synthetic-banner"><span className="banner-symbol">⌁</span><div><b>Decision history is local to this demo</b><span>Resetting the synthetic database clears these records. Decisions never trigger a real account action.</span></div><span className="banner-tag">{audit.total} RECORDS</span></div>
    {error && <div className="inline-error" role="alert">{error}</div>}
    <section className="content-card audit-card"><div className="section-head"><div><div className="eyebrow">REVIEW HISTORY · NEWEST FIRST</div><h2>Decision log <span className="count-badge">{audit.total}</span></h2></div></div>
      <div className="audit-toolbar">
        <form className="audit-search" onSubmit={(event) => { event.preventDefault(); setPage(0); setQuery(searchInput.trim()) }}>
          <label htmlFor="audit-search-input">Search scenario, wallet, actor, or reason</label>
          <div><input id="audit-search-input" type="search" maxLength={120} value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="e.g. SCN-06 or review reason" /><button className="button button-secondary" type="submit">Search</button></div>
        </form>
        <label className="audit-filter"><span>Decision</span><select aria-label="Filter audit log by decision" value={decision} onChange={(event) => { setDecision(event.target.value); setPage(0) }}><option value="all">All decisions</option><option value="approve">Approved</option><option value="modify">Modified</option><option value="reject">Rejected</option></select></label>
        {hasFilters && <button type="button" className="clear-filter" onClick={() => { setSearchInput(''); setQuery(''); setDecision('all'); setPage(0) }}>Clear filters</button>}
      </div>
      {loading ? <div className="empty-state" role="status">Loading decision history…</div> : audit.total === 0 ? <div className="empty-state">{hasFilters ? 'No decisions match these filters. Clear them or try another search.' : 'No decisions have been recorded yet. Review a case and record the analyst’s choice.'}</div> : <div className="table-scroll"><table className="data-table audit-table"><thead><tr><th>TIME</th><th>SCENARIO / WALLET</th><th>DECISION</th><th>SIMULATED AMOUNT</th><th>ACTOR</th><th>REASON</th></tr></thead><tbody>{audit.decisions.map((item) => <tr key={item.decision_id}><td>{formatDate(item.created_at)}</td><td><div className="incident-id">{item.scenario_id}</div><div className="scenario-id">{item.wallet_id}</div></td><td><span className={`decision-pill decision-${item.decision}`}>{item.decision}</span></td><td className="amount-cell">{formatMoney(item.proposed_amount_bdt)}</td><td>{item.actor}</td><td className="reason-cell">{item.reason}</td></tr>)}</tbody></table></div>}
      <div className="table-foot audit-foot"><span>Showing {firstResult}–{lastResult} of {audit.total} matching decisions</span><div className="pagination"><button aria-label="Previous audit page" disabled={page === 0 || loading} onClick={() => setPage((value) => Math.max(0, value - 1))}>←</button><span>{page + 1} / {pageCount}</span><button aria-label="Next audit page" disabled={page + 1 >= pageCount || loading} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>→</button></div></div>
    </section>
  </>
}
