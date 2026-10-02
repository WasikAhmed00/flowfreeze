import { useEffect, useState } from 'react'
import { api, formatMoney } from '../api.js'
import StatCard from '../components/StatCard.jsx'

export default function Evaluation({ metrics: initialMetrics, onRefresh }) {
  const [metrics, setMetrics] = useState(initialMetrics)
  const [error, setError] = useState('')
  useEffect(() => { api('/api/metrics').then(setMetrics).catch((e) => setError(e.message)) }, [initialMetrics])
  return <>
    <div className="page-heading heading-row"><div><div className="eyebrow">EVALUATION <span className="eyebrow-dot" /> SYNTHETIC DATA</div><h1>Measure the prototype</h1><p>Current metrics describe generated data and recorded what-if outcomes, not production performance.</p></div><button className="button button-secondary" onClick={onRefresh}>↻ Refresh</button></div>
    {error && <div className="inline-error">{error}</div>}
    <div className="stats-grid eval-stats"><StatCard label="INCIDENT CASES" value={metrics?.dataset?.incident_count?.toLocaleString() ?? '—'} sub="All seeded synthetic cases" icon="⌁" tone="green" /><StatCard label="TRANSACTION EVENTS" value={metrics?.dataset?.transaction_count?.toLocaleString() ?? '—'} sub="Across generated scenarios" icon="⇢" tone="blue" /><StatCard label="SIMULATIONS RECORDED" value={metrics?.simulations?.count ?? '—'} sub="Analyst decisions with outcomes" icon="◌" tone="violet" /><StatCard label="ESTIMATED VALUE PRESERVED" value={formatMoney(metrics?.simulations?.estimated_tainted_value_preserved_bdt)} sub="Simulated estimate only" icon="৳" tone="amber" /></div>
    <div className="evaluation-grid"><section className="content-card eval-note"><div className="eyebrow">CURRENT EVIDENCE</div><h2>What these numbers mean</h2><p>The current endpoint reports synthetic record counts and estimates from analyst-approved, modified, or rejected simulations. It does not report fraud-model accuracy.</p><div className="eval-callout"><b>ML evaluation is not available yet</b><span>Roadmap Step 5 remains open. Precision, recall, F1, and PR-AUC must be measured after leakage-safe model training against the held-out synthetic test cases.</span></div></section>
      <section className="content-card impact-card"><div className="eyebrow">SIMULATED COLLATERAL IMPACT</div><h2>Preserved vs. affected estimate</h2><div className="impact-number">{formatMoney(metrics?.simulations?.estimated_tainted_value_preserved_bdt)}<span>estimated tainted value preserved</span></div><div className="impact-divider" /><div className="impact-secondary">{formatMoney(metrics?.simulations?.estimated_legitimate_value_affected_bdt)}<span>estimated legitimate value affected</span></div><small>Estimates use proportional attribution and the scenario replay snapshot.</small></section></div>
  </>
}
