import { useEffect, useState } from 'react'
import { api, formatMoney } from '../api.js'
import StatCard from '../components/StatCard.jsx'

function Metric({ label, value }) {
  return <div className="metric-row"><span>{label}</span><b>{value == null ? '—' : Number(value).toFixed(3)}</b></div>
}

export default function Evaluation({ metrics: initialMetrics, onRefresh }) {
  const [metrics, setMetrics] = useState(initialMetrics)
  const [error, setError] = useState('')
  useEffect(() => { api('/api/metrics').then(setMetrics).catch((e) => setError(e.message)) }, [initialMetrics])
  const ml = metrics?.ml_evaluation
  const test = ml?.held_out_test
  const fraud = test?.fraud
  const movement = test?.next_move
  const experiment = metrics?.end_to_end_evaluation?.results
  const baseline = experiment?.direct_recipient_only
  const network = experiment?.flowfreeze_network
  return <>
    <div className="page-heading heading-row"><div><div className="eyebrow">EVALUATION <span className="eyebrow-dot" /> SYNTHETIC DATA</div><h1>Measure the prototype</h1><p>Current metrics describe generated data and recorded what-if outcomes, not production performance.</p></div><button className="button button-secondary" onClick={onRefresh}>↻ Refresh</button></div>
    {error && <div className="inline-error">{error}</div>}
    <div className="stats-grid eval-stats"><StatCard label="INCIDENT CASES" value={metrics?.dataset?.incident_count?.toLocaleString() ?? '—'} sub="All seeded synthetic cases" icon="⌁" tone="green" /><StatCard label="TRANSACTION EVENTS" value={metrics?.dataset?.transaction_count?.toLocaleString() ?? '—'} sub="Across generated scenarios" icon="⇢" tone="blue" /><StatCard label="SIMULATIONS RECORDED" value={metrics?.simulations?.count ?? '—'} sub="Analyst decisions with outcomes" icon="◌" tone="violet" /><StatCard label="ESTIMATED VALUE PRESERVED" value={formatMoney(metrics?.simulations?.estimated_tainted_value_preserved_bdt)} sub="Simulated estimate only" icon="৳" tone="amber" /></div>
    <div className="evaluation-grid"><section className="content-card eval-note"><div className="eyebrow">HELD-OUT MODEL RESULTS · SYNTHETIC</div><h2>ML evaluation</h2>
      {!ml?.metrics_available ? <div className="eval-callout"><b>Metrics are not available</b><span>Run <code>python -m ml.train</code> from the repository root. The generated metrics file is local and can be committed for review.</span></div> : <>
        <p>Test split: {test?.scenario_cases} scenario cases and {test?.wallet_rows} wallet rows. Selected fraud model: {ml.metadata?.fraud_model_selection?.selected_fraud_model}; validation-selected threshold: {fraud?.threshold?.toFixed(3)}.</p>
        <div className="metric-section"><h3>Fraud detection</h3><Metric label="Precision" value={fraud?.precision} /><Metric label="Recall" value={fraud?.recall} /><Metric label="F1" value={fraud?.f1} /><Metric label="PR-AUC · average precision" value={fraud?.pr_auc_average_precision} /><Metric label="Balanced accuracy" value={fraud?.balanced_accuracy} /></div>
        <div className="metric-section"><h3>Next-move classification</h3><Metric label="Macro F1" value={movement?.f1_macro} /><Metric label="Macro PR-AUC · one-vs-rest" value={movement?.pr_auc_macro_ovr} /><Metric label="Accuracy" value={movement?.accuracy} /><Metric label="Multiclass log loss" value={movement?.log_loss} /><Metric label="Multiclass Brier score" value={movement?.brier_score_multiclass} /></div>
        <div className="eval-callout"><b>{ml.artifact_available ? 'Trained synthetic models are available locally' : 'Metrics available; model artifacts are not present'}</b><span>{ml.warning} The held-out set contains variants of the same eight generated scenario families; it is not an unseen-family, temporal, or real-world evaluation. Scores do not establish production accuracy or calibrated upay BD risk.</span></div>
      </>}</section>
      <section className="content-card impact-card"><div className="eyebrow">SIMULATED COLLATERAL IMPACT</div><h2>Recorded analyst simulations</h2><div className="impact-number">{formatMoney(metrics?.simulations?.estimated_tainted_value_preserved_bdt)}<span>estimated tainted value preserved</span></div><div className="impact-divider" /><div className="impact-secondary">{formatMoney(metrics?.simulations?.estimated_legitimate_value_affected_bdt)}<span>estimated legitimate value affected</span></div><small>Recorded analyst decisions only. Estimates use the prototype's proportional attribution.</small></section></div>
    <section className="content-card end-to-end-card"><div className="eyebrow">STEP 9 · SAME HELD-OUT CASES</div><h2>Direct-recipient baseline vs. FlowFreeze network</h2>
      {!metrics?.end_to_end_evaluation?.metrics_available ? <div className="eval-callout"><b>End-to-end benchmark is not available</b><span>Run <code>python -m core.baseline</code> after training models and generating the default database.</span></div> : <>
        <p>{experiment.scenario_cases} held-out incident cases · same model scores, policy, snapshot, and per-wallet cap for both strategies.</p>
        <div className="comparison-matrix"><div></div><b>Direct recipient only</b><b>FlowFreeze network</b><b>Network minus baseline</b>
          <span>Est. tainted value preserved</span><strong>{formatMoney(baseline?.estimated_tainted_value_preserved_bdt)}</strong><strong>{formatMoney(network?.estimated_tainted_value_preserved_bdt)}</strong><strong>{formatMoney(experiment.network_minus_baseline?.estimated_tainted_value_preserved_bdt)}</strong>
          <span>Est. legitimate value affected</span><strong>{formatMoney(baseline?.estimated_legitimate_value_affected_bdt)}</strong><strong>{formatMoney(network?.estimated_legitimate_value_affected_bdt)}</strong><strong>{formatMoney(experiment.network_minus_baseline?.estimated_legitimate_value_affected_bdt)}</strong>
          <span>Cases with a proposal</span><strong>{baseline?.cases_with_proposal ?? '—'}</strong><strong>{network?.cases_with_proposal ?? '—'}</strong><strong>{network && baseline ? network.cases_with_proposal - baseline.cases_with_proposal : '—'}</strong>
          <span>Mean downstream wallets traced</span><strong>Direct recipient only</strong><strong>{experiment.tracing?.average_downstream_wallets_found_per_case ?? '—'}</strong><strong>—</strong>
        </div>
        <div className="timing-note">Median recommendation time: {experiment.timing?.median_recommendation_ms} ms per case · p95: {experiment.timing?.p95_recommendation_ms} ms. {experiment.limitation}</div>
        <div className="eval-callout"><b>Counterfactual estimates, not observed impact</b><span>{experiment.outcome_assumptions?.join(' ')} They are synthetic scenario calculations, not upay BD production statistics.</span></div>
      </>}
    </section>
  </>
}
