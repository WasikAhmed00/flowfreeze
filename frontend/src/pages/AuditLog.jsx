import { useEffect, useState } from 'react'
import { api, formatDate, formatMoney, maskWallet, shortCaseId } from '../api.js'

export default function AuditLog({ refreshToken }) {
  const [audit, setAudit] = useState({ decisions: [], total: 0 })
  const [error, setError] = useState('')
  useEffect(() => { api('/api/decisions?limit=200').then(setAudit).catch((e) => setError(e.message)) }, [refreshToken])
  return <>
    <div className="page-heading"><div><div className="eyebrow">AUDIT TRAIL <span className="eyebrow-dot" /> APPEND-ONLY VIEW</div><h1>Supervisor decisions</h1><p>Every decision records a reason, actor, timestamp, scenario, and proposed simulated amount.</p></div></div>
    {error && <div className="inline-error">{error}</div>}
    <section className="content-card audit-card"><div className="section-head"><div><div className="eyebrow">REVIEW HISTORY</div><h2>Decision log <span className="count-badge">{audit.total}</span></h2></div></div>
      {!audit.decisions?.length ? <div className="empty-state">No decisions yet. Decisions you submit will appear here.</div> : <div className="table-scroll"><table className="data-table audit-table"><thead><tr><th>TIME</th><th>CASE</th><th>DECISION</th><th>AMOUNT</th><th>SUPERVISOR</th><th>REASON</th></tr></thead><tbody>{audit.decisions.map((item) => <tr key={item.decision_id}><td>{formatDate(item.created_at)}</td><td><div className="incident-id">{shortCaseId(item.scenario_id)}</div><div className="scenario-id">{maskWallet(item.wallet_id)}</div></td><td><span className={`decision-pill decision-${item.decision}`}>{item.decision}</span></td><td className="amount-cell">{formatMoney(item.proposed_amount_bdt)}</td><td>{item.actor === 'demo_analyst' ? 'Demo supervisor' : item.actor}</td><td className="reason-cell">{item.reason}</td></tr>)}</tbody></table></div>}
    </section>
  </>
}
