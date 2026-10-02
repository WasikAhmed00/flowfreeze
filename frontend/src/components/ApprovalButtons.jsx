import { useEffect, useState } from 'react'
import { api, formatMoney } from '../api.js'

export default function ApprovalButtons({ scenarioId, wallet, recommendation, onRecorded }) {
  const eligible = recommendation?.action === 'propose_bounded_simulated_hold' && Number(recommendation.proposed_simulated_hold_bdt) > 0
  const [decision, setDecision] = useState('approve')
  const [amount, setAmount] = useState(recommendation?.proposed_simulated_hold_bdt || '0.00')
  const [reason, setReason] = useState('')
  const [actor, setActor] = useState('demo_analyst')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [recorded, setRecorded] = useState(null)
  const [outcome, setOutcome] = useState(null)

  useEffect(() => {
    setDecision(eligible ? 'approve' : 'reject')
    setAmount(recommendation?.proposed_simulated_hold_bdt || '0.00')
    setRecorded(null); setOutcome(null); setError('')
  }, [scenarioId, wallet?.wallet_id, eligible, recommendation?.proposed_simulated_hold_bdt])

  const record = async () => {
    if (!wallet || !reason.trim()) { setError('Select a wallet and enter a review reason.'); return }
    setSaving(true); setError(''); setOutcome(null)
    try {
      const body = {
        scenario_id: scenarioId, wallet_id: wallet.wallet_id, decision,
        proposed_amount_bdt: decision === 'reject' ? '0.00' : amount,
        reason: reason.trim(), actor: actor.trim() || 'demo_analyst',
      }
      const saved = await api('/api/decisions', { method: 'POST', body: JSON.stringify(body) })
      setRecorded(saved); onRecorded?.()
    } catch (e) { setError(e.message) } finally { setSaving(false) }
  }
  const simulate = async () => {
    setSaving(true); setError('')
    try { setOutcome(await api(`/api/simulation/${recorded.decision_id}`, { method: 'POST' })); onRecorded?.() }
    catch (e) { setError(e.message) } finally { setSaving(false) }
  }

  return <section className="content-card approval-card"><div className="eyebrow">ANALYST DECISION</div><h2>Record your review</h2>
    {!wallet ? <div className="empty-state compact-empty">Select a wallet to record a decision.</div> : <>
      <div className="decision-target"><span>Selected target</span><b>{wallet.wallet_id}</b><small>Balance {formatMoney(wallet.balance_bdt)}</small></div>
      {!eligible && <div className="review-only-note">No policy hold proposal is available for this wallet. You can record a rejection or continue monitoring; supply explicitly illustrative inputs above only for demo exploration.</div>}
      {!recorded ? <>
        <label className="form-label">REVIEW OUTCOME</label><div className="decision-options">{['approve', 'modify', 'reject'].map((item) => <button key={item} className={`decision-option ${decision === item ? `chosen chosen-${item}` : ''} ${item !== 'reject' && !eligible ? 'disabled-option' : ''}`} disabled={item !== 'reject' && !eligible} onClick={() => setDecision(item)}>{item === 'approve' ? '✓ Approve' : item === 'modify' ? '≋ Modify' : '× Reject'}</button>)}</div>
        {decision !== 'reject' && <label className="form-label amount-field">SIMULATED AMOUNT (BDT)<input type="number" min="0.01" max={Number(wallet.balance_bdt)} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>}
        <label className="form-label amount-field">ANALYST REASON<textarea rows="3" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Record why this decision was made…" /></label>
        <label className="form-label amount-field">ACTOR LABEL<input value={actor} onChange={(e) => setActor(e.target.value)} /></label>
        {error && <div className="inline-error">{error}</div>}
        <button className="button button-dark full-button" disabled={saving} onClick={record}>{saving ? 'Saving…' : 'Record decision'} <span>→</span></button>
      </> : <div className="recorded-box"><div className="recorded-check">✓</div><b>Decision recorded · #{recorded.decision_id}</b><span>This entry is in the local audit log. No real wallet was changed.</span>{!outcome ? <button className="button button-secondary full-button" disabled={saving} onClick={simulate}>{saving ? 'Calculating…' : 'Run simulated outcome'}</button> : <div className="outcome-box"><b>Scenario estimate</b><span>Potentially tainted preserved <strong>{formatMoney(outcome.estimated_tainted_preserved_bdt)}</strong></span><span>Legitimate value affected <strong>{formatMoney(outcome.estimated_legitimate_value_affected_bdt)}</strong></span><small>Ledger unchanged · synthetic simulation</small></div>}{error && <div className="inline-error">{error}</div>}</div>}
    </>}
  </section>
}
