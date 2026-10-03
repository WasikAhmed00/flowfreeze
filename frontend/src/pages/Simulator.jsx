import { useEffect, useState } from 'react'
import { api, formatDate, formatMoney } from '../api.js'
import TransactionGraph from '../components/TransactionGraph.jsx'
import WalletPanel from '../components/WalletPanel.jsx'
import TaintTable from '../components/TaintTable.jsx'
import PredictionBars from '../components/PredictionBars.jsx'
import EvidencePanel from '../components/EvidencePanel.jsx'
import RecommendationCard from '../components/RecommendationCard.jsx'
import ApprovalButtons from '../components/ApprovalButtons.jsx'

export default function Simulator({ incidents, scenarioId, onSelect, onRefresh }) {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedWallet, setSelectedWallet] = useState('')
  const [illustrative, setIllustrative] = useState(false)
  const [risk, setRisk] = useState('0.82')
  const [moves, setMoves] = useState({ forward: '0.2', cashout: '0.65', no_movement: '0.15' })
  const [runNumber, setRunNumber] = useState(0)

  useEffect(() => {
    if (!scenarioId) return
    let alive = true
    setLoading(true); setError(''); setAnalysis(null)
    const params = new URLSearchParams()
    if (illustrative) {
      params.set('fraud_risk', risk)
      params.set('p_forward', moves.forward)
      params.set('p_cashout', moves.cashout)
      params.set('p_no_movement', moves.no_movement)
    }
    const query = params.toString()
    api(`/api/analysis/${encodeURIComponent(scenarioId)}${query ? `?${query}` : ''}`)
      .then((value) => {
        if (!alive) return
        setAnalysis(value)
        setSelectedWallet(value.recommendation?.recommendations?.[0]?.wallet_id || value.taint?.wallets?.[0]?.wallet_id || '')
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false))
    return () => { alive = false }
  }, [scenarioId, runNumber])

  const runSimulation = () => setRunNumber((value) => value + 1)
  const incident = incidents.find((item) => item.scenario_id === scenarioId) || analysis?.incident || {}
  const allWallets = analysis?.taint?.wallets || []
  const walletRec = analysis?.recommendation?.recommendations?.find((row) => row.wallet_id === selectedWallet)
  const candidate = walletRec || (selectedWallet ? allWallets.find((row) => row.wallet_id === selectedWallet) : null)
  const recommendation = walletRec || (candidate ? { ...candidate, action: 'monitor_and_review', reasons: ['No simulated hold proposal is available without qualifying policy evidence and supplied model scores.'], proposed_simulated_hold_bdt: '0.00', evidence_transaction_ids: [] } : null)

  if (!scenarioId) return <div className="empty-state">Choose a seeded case to start a simulation.</div>

  return <>
    <div className="page-heading heading-row simulation-heading">
      <div><div className="eyebrow">SIMULATION LAB <span className="eyebrow-dot" /> COUNTERFACTUAL TESTING</div><h1>Test a response before review</h1><p>Change illustrative inputs, compare the predicted movement, and document a synthetic outcome without touching a wallet.</p></div>
      <button className="button button-secondary" onClick={runSimulation}>↻ Reset run</button>
    </div>

    <section className="simulation-setup">
      <div className="content-card scenario-selector-card"><div className="eyebrow">1 · CHOOSE A STARTING CASE</div><h2>Scenario setup</h2><p>Pick a generated incident as the starting state for this experiment.</p><label htmlFor="scenario-picker">SCENARIO</label><select id="scenario-picker" value={scenarioId} onChange={(event) => onSelect(event.target.value)}>{incidents.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.scenario_type.replaceAll('_', ' ')} · {item.scenario_id}</option>)}</select><div className="scenario-meta"><span>Reported amount</span><b>{formatMoney(incident.reported_amount)}</b><small>{incident.incident_id || scenarioId} · {formatDate(incident.reported_at)}</small></div></div>
      <div className="content-card simulation-instructions"><div className="eyebrow">2 · RUN A COUNTERFACTUAL</div><h2>How this lab works</h2><div className="simulation-steps"><div><b>Adjust</b><span>Supply clearly marked illustrative risk and movement values.</span></div><div><b>Run</b><span>Rebuild the replay, graph, and wallet-level estimates.</span></div><div><b>Compare</b><span>Review the result before recording an analyst decision.</span></div></div><div className="simulation-safety">Synthetic only · balances, customer records, and payment rails remain unchanged.</div></div>
    </section>

    {error && <div className="inline-error">{error}</div>}
    {loading && <div className="loading-card"><span className="loader" /> Running the synthetic response test…</div>}
    {analysis && <>
      <section className="content-card simulation-controls"><div className="simulation-control-head"><div><div className="eyebrow">3 · SET TEST INPUTS</div><h2>Illustrative control panel</h2><p>Model outputs are advisory. Values here are not evidence and are not applied to production systems.</p></div><label className="toggle-label"><input type="checkbox" checked={illustrative} onChange={(event) => { setIllustrative(event.target.checked); runSimulation() }} /><span className="toggle-track" /> Enable illustrative inputs</label></div>
        {!illustrative ? <div className="control-disabled"><span>◎</span><div><b>Using trained synthetic model output</b><small>Enable illustrative inputs to test a different fraud risk or next-move mix.</small></div></div> : <div className="illustrative-fields"><div className="illustrative-warning">Illustrative values only · these are not model predictions or evidence.</div><label>Fraud risk <input type="number" min="0" max="1" step="0.01" value={risk} onChange={(event) => setRisk(event.target.value)} /></label>{Object.keys(moves).map((key) => <label key={key}>P({key.replaceAll('_', ' ')}) <input type="number" min="0" max="1" step="0.01" value={moves[key]} onChange={(event) => setMoves({ ...moves, [key]: event.target.value })} /></label>)}<button className="button button-primary" onClick={runSimulation}>Run this test <span>→</span></button></div>}
        <PredictionBars probabilities={walletRec?.next_move_probabilities} fraudRisk={walletRec?.risk_score} source={analysis.model_predictions?.source} />
      </section>

      <div className="simulation-output-bar"><div><div className="eyebrow">4 · OBSERVE THE OUTPUT</div><h2>Response impact preview</h2></div><div className="simulation-run-label">Run {runNumber + 1} · Snapshot {formatDate(analysis.as_of || incident.analysis_at)}</div></div>
      <div className="summary-strip simulation-summary"><div><span>EVENTS REPLAYED</span><b>{analysis.replay.transaction_count}</b></div><div><span>WALLETS TRACED</span><b>{analysis.trace.downstream_wallet_ids.length}</b></div><div><span>TAINTED VALUE REMAINING</span><b>{formatMoney(analysis.taint.remaining_potentially_tainted_bdt)}</b></div><div><span>CASHED OUT</span><b>{formatMoney(analysis.taint.cashed_out_potentially_tainted_bdt)}</b></div></div>
      <div className="simulation-primary-grid"><section className="content-card graph-card simulation-graph-card"><div className="section-head"><div><div className="eyebrow">NETWORK OUTPUT</div><h2>Predicted fund flow</h2></div><button className="button button-secondary" onClick={runSimulation}>Refresh output</button></div><TransactionGraph trace={analysis.trace} incident={incident} onWallet={setSelectedWallet} selectedWallet={selectedWallet} /></section><WalletPanel wallet={candidate} onClear={() => setSelectedWallet('')} /></div>
      <div className="simulation-secondary-grid"><section className="content-card"><div className="section-head"><div><div className="eyebrow">WALLET IMPACT</div><h2>Attribution by wallet</h2></div><span className="method-pill">{analysis.taint.method?.replaceAll('_', ' ') || 'proportional'}</span></div><TaintTable wallets={allWallets} onSelect={setSelectedWallet} selectedWallet={selectedWallet} /></section><EvidencePanel trace={analysis.trace} taint={analysis.taint} /></div>
      <div className="simulation-decision-grid"><div><div className="eyebrow">5 · DOCUMENT THE RESULT</div><RecommendationCard recommendation={recommendation} /></div><ApprovalButtons scenarioId={scenarioId} wallet={candidate} recommendation={recommendation} onRecorded={onRefresh} /></div>
    </>}
  </>
}
