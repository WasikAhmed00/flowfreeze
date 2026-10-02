import { formatMoney } from '../api.js'

export default function RecommendationCard({ recommendation }) {
  if (!recommendation) return <section className="recommendation-card"><div className="eyebrow">POLICY OUTPUT</div><h2>No wallet selected</h2><p>Choose a wallet from the graph or taint table to review its policy output.</p></section>
  const proposed = Number(recommendation.proposed_simulated_hold_bdt || 0)
  const eligible = recommendation.action === 'propose_bounded_simulated_hold'
  return <section className={`recommendation-card ${eligible ? 'recommendation-eligible' : ''}`}>
    <div className="recommendation-top"><div><div className="eyebrow">POLICY OUTPUT · {recommendation.urgency?.replaceAll('_', ' ') || 'review'}</div><h2>{eligible ? 'Bounded simulated hold proposal' : recommendation.action === 'review_dispute' ? 'Route for dispute review' : 'Monitor and review'}</h2></div><span className={`recommend-icon ${eligible ? 'recommend-icon-green' : ''}`}>{eligible ? '↗' : '◷'}</span></div>
    <p className="recommend-intro">{eligible ? 'Policy thresholds and supplied evidence qualify this wallet for an analyst-reviewed simulation.' : 'Current evidence does not qualify a simulated hold proposal. Continue review with the limits below in mind.'}</p>
    <div className="recommend-amount"><span>PROPOSED SIMULATION</span><b>{formatMoney(proposed)}</b><small>Policy-bounded · no wallet action executed</small></div>
    <div className="collateral-line"><span>Estimated legitimate value affected</span><b>{formatMoney(recommendation.estimated_legitimate_value_affected_bdt)}</b></div>
    <ul className="reason-list">{(recommendation.reasons || []).slice(0, 4).map((reason, index) => <li key={index}><span>✓</span>{reason}</li>)}</ul>
    <div className="review-required"><span>◎</span><b>Analyst review required</b><small>Policy v1.0 · synthetic prototype</small></div>
  </section>
}
