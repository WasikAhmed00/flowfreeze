import { useEffect, useState } from 'react'
import { api, formatDate, formatMoney } from '../api.js'
import TransactionGraph from '../components/TransactionGraph.jsx'
import WalletPanel from '../components/WalletPanel.jsx'
import TaintTable from '../components/TaintTable.jsx'
import PredictionBars from '../components/PredictionBars.jsx'
import EvidencePanel from '../components/EvidencePanel.jsx'
import RecommendationCard from '../components/RecommendationCard.jsx'
import ApprovalButtons from '../components/ApprovalButtons.jsx'
import BaselineComparison from '../components/BaselineComparison.jsx'

export default function IncidentDetail({ scenarioId, incident, onRefresh }) {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedWallet, setSelectedWallet] = useState('')
  const [illustrative, setIllustrative] = useState(false)
  const [risk, setRisk] = useState('0.82')
  const [moves, setMoves] = useState({ forward: '0.2', cashout: '0.65', no_movement: '0.15' })
  const [analysisKey, setAnalysisKey] = useState(0)

  useEffect(() => {
    if (!scenarioId) return
    let alive = true
    setLoading(true); setError(''); setAnalysis(null)
    const params = new URLSearchParams()
    if (illustrative) {
      params.set('fraud_risk', risk)
      params.set('p_forward', moves.forward); params.set('p_cashout', moves.cashout); params.set('p_no_movement', moves.no_movement)
    }
    const query = params.toString()
    api(`/api/analysis/${encodeURIComponent(scenarioId)}${query ? `?${query}` : ''}`)
      .then((value) => { if (alive) { setAnalysis(value); setSelectedWallet(value.recommendation?.recommendations?.[0]?.wallet_id || value.taint?.wallets?.[0]?.wallet_id || '') } })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [scenarioId, analysisKey])

  const runAnalysis = () => setAnalysisKey((n) => n + 1)
  const allWallets = analysis?.taint?.wallets || []
  const walletRec = analysis?.recommendation?.recommendations?.find((row) => row.wallet_id === selectedWallet)
  const candidate = walletRec || (selectedWallet ? allWallets.find((row) => row.wallet_id === selectedWallet) : null)
  const detailIncident = analysis?.incident || incident || {}
  const activeRecommendation = walletRec || (candidate ? { ...candidate, action: 'monitor_and_review', reasons: ['No simulated hold proposal is available without qualifying policy evidence and supplied model scores.'], proposed_simulated_hold_bdt: '0.00', evidence_transaction_ids: [] } : null)

  if (!scenarioId) return <div className="empty-state">Select an incident from the Overview page.</div>
  return <>
    <div className="detail-heading">
      <div><div className="eyebrow"><button className="back-link" onClick={() => window.dispatchEvent(new CustomEvent('flowfreeze:navigate', { detail: 'dashboard' }))}>← INCIDENTS</button><span className="eyebrow-dot" /> {detailIncident.incident_id || scenarioId}</div>
        <h1>{(detailIncident.scenario_type || 'Incident review').replaceAll('_', ' ')}</h1><p>{scenarioId} <span className="detail-divider">·</span> Reported {formatDate(detailIncident.reported_at)} <span className="detail-divider">·</span> {formatMoney(detailIncident.reported_amount)}</p></div>
      <div className="detail-actions"><span className="status-pill"><i /> {detailIncident.status || 'new'}</span><button className="button button-secondary" onClick={runAnalysis}>↻ Refresh analysis</button></div>
    </div>
    <div className="synthetic-banner compact-banner"><span className="banner-symbol">✳</span><div><b>Analysis snapshot · {formatDate(analysis?.as_of || detailIncident.analysis_at)}</b><span>Only events visible at the recorded analysis time are included. All records are synthetic.</span></div><span className="banner-tag">NOT A FINDING</span></div>
    {error && <div className="inline-error">{error}</div>}
    {loading && <div className="loading-card"><span className="loader" /> Building replay, graph, and taint evidence…</div>}
    {analysis && <>
      <div className="summary-strip">
        <div><span>EVENTS IN SNAPSHOT</span><b>{analysis.replay.transaction_count}</b></div>
        <div><span>DOWNSTREAM WALLETS</span><b>{analysis.trace.downstream_wallet_ids.length}</b></div>
        <div><span>POTENTIALLY TAINTED REMAINING</span><b>{formatMoney(analysis.taint.remaining_potentially_tainted_bdt)}</b></div>
        <div><span>OBSERVED CASHOUT</span><b>{formatMoney(analysis.taint.cashed_out_potentially_tainted_bdt)}</b></div>
      </div>
      <BaselineComparison trace={analysis.trace} taint={analysis.taint} />
      <section className="content-card model-input-card">
        <div className="model-input-top"><div><div className="eyebrow">MODEL OUTPUTS</div><h2>Fraud and next-move scores</h2><p>{analysis.model_predictions?.message || 'Model scores are advisory synthetic outputs. Recommendations remain subject to the displayed policy and analyst review.'}</p></div><label className="toggle-label"><input type="checkbox" checked={illustrative} onChange={(e) => { setIllustrative(e.target.checked); runAnalysis() }} /><span className="toggle-track" /> Add illustrative inputs</label></div>
        {illustrative && <div className="illustrative-fields"><div className="illustrative-warning">Illustrative values only · these are not model predictions or evidence.</div><label>Fraud risk <input type="number" min="0" max="1" step="0.01" value={risk} onChange={(e) => setRisk(e.target.value)} /></label>{Object.keys(moves).map((key) => <label key={key}>P({key.replaceAll('_', ' ')})<input type="number" min="0" max="1" step="0.01" value={moves[key]} onChange={(e) => setMoves({ ...moves, [key]: e.target.value })} /></label>)}<button className="button button-dark" onClick={runAnalysis}>Re-run with illustrative scores</button></div>}
        <PredictionBars probabilities={walletRec?.next_move_probabilities} fraudRisk={walletRec?.risk_score} source={analysis.model_predictions?.source} />
      </section>
      <div className="analysis-grid">
        <section className="content-card graph-card"><div className="section-head"><div><div className="eyebrow">FUND FLOW</div><h2>Transaction graph</h2></div><span className="legend"><i className="legend-report" /> Reported transfer <i className="legend-path" /> Observed movement</span></div><TransactionGraph trace={analysis.trace} incident={detailIncident} onWallet={setSelectedWallet} selectedWallet={selectedWallet} /></section>
        <WalletPanel wallet={candidate} onClear={() => setSelectedWallet('')} />
      </div>
      <div className="analysis-grid lower-grid">
        <section className="content-card"><div className="section-head"><div><div className="eyebrow">PROPORTIONAL ATTRIBUTION</div><h2>Taint estimate by wallet</h2></div><span className="method-pill">{analysis.taint.method?.replaceAll('_', ' ') || 'proportional'}</span></div><TaintTable wallets={allWallets} onSelect={setSelectedWallet} selectedWallet={selectedWallet} /></section>
        <EvidencePanel trace={analysis.trace} taint={analysis.taint} />
      </div>
      <div className="recommendation-layout"><RecommendationCard recommendation={activeRecommendation} />
        <ApprovalButtons scenarioId={scenarioId} wallet={candidate} recommendation={activeRecommendation} onRecorded={onRefresh} />
      </div>
    </>}
  </>
}
