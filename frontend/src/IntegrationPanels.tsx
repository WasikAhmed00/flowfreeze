import { useCallback, useEffect, useRef, useState } from 'react';
import { Activity, AlertTriangle, ArrowRight, CirclePlay, CircleStop, Gauge, Network, Plus, RefreshCw, ShieldCheck } from 'lucide-react';
import './integration.css';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const WRITE_KEY = import.meta.env.VITE_DEMO_WRITE_KEY || '';
const HEADERS: HeadersInit = { 'Content-Type': 'application/json', ...(WRITE_KEY ? { 'X-FlowFreeze-Write-Key': WRITE_KEY } : {}) };

type StreamEvent = {
  transaction: { transaction_id: string; timestamp: string; sender_wallet: string; receiver_wallet: string; amount_bdt: string | number; transaction_type: string; channel?: string };
  analysis: { risk_score: number; risk_band: string; taint: { potentially_tainted_bdt_estimate: string }; alerts: Array<{ code: string; severity: string; message: string }>; predictions: { next_move_probabilities: Record<string, number> } };
  graph: { nodes: string[]; edges: Array<{ transaction_id: string; from: string; to: string; amount_bdt: string }>; node_count: number; edge_count: number };
  processing_ms: number;
  graph_processing_ms: number;
};
type CaseRecord = { id: string; case_id: string; transaction_id?: string | null; risk_score: number; investigator: string; status: string; title: string; notes: string; created_at: string };
type Operational = { status: string; api: { requests_total: number; server_errors_total: number; mean_response_ms: number; max_response_ms: number }; stream_transactions_total: number; stream_transactions_with_alerts: number; cases_total: number; open_cases: number };

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_ORIGIN}${path}`, { ...options, headers: { ...HEADERS, ...(options.headers || {}) } });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body); } catch { /* use status */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
const amount = (value: string | number) => `৳${new Intl.NumberFormat('en-BD', { maximumFractionDigits: 0 }).format(Number(value) || 0)}`;

export function IntegrationCenter() {
  const [latest, setLatest] = useState<StreamEvent | null>(null);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const onEvent = useCallback((event: StreamEvent) => { setLatest(event); setEvents((items) => [event, ...items].slice(0, 8)); setRefreshKey((value) => value + 1); }, []);
  return <section className="integration-center">
    <div className="integration-heading"><div><div className="panel-eyebrow"><Activity size={13} /> SCALABILITY &amp; INTEGRATION</div><h2>Event stream &amp; case operations</h2><p>Synthetic adapter workflow; ready for a partner-governed MFS connector, with no production connection enabled.</p></div><span className="integration-synthetic">SYNTHETIC ONLY</span></div>
    <div className="integration-grid"><LiveSimulationPanel onEvent={onEvent} events={events} /><CaseManagementPanel latest={latest} refreshKey={refreshKey} /></div>
    <FairnessDashboardPanel />
  </section>;
}

function LiveSimulationPanel({ onEvent, events }: { onEvent: (event: StreamEvent) => void; events: StreamEvent[] }) {
  const [running, setRunning] = useState(false);
  const [health, setHealth] = useState<'checking' | 'online' | 'offline'>('checking');
  const [operational, setOperational] = useState<Operational | null>(null);
  const [error, setError] = useState('');
  const runningRef = useRef(false);
  const loadStatus = useCallback(async () => {
    const [healthResult, metricResult] = await Promise.allSettled([
      api<{ status: string }>('/health'), api<{ operational: Operational }>('/api/metrics'),
    ]);
    setHealth(healthResult.status === 'fulfilled' && healthResult.value.status === 'ok' ? 'online' : 'offline');
    if (metricResult.status === 'fulfilled') setOperational(metricResult.value.operational);
  }, []);
  useEffect(() => { void loadStatus(); }, [loadStatus]);
  useEffect(() => () => { runningRef.current = false; }, []);
  const stop = () => { runningRef.current = false; setRunning(false); };
  const start = async () => {
    if (runningRef.current) return;
    runningRef.current = true; setRunning(true); setError('');
    while (runningRef.current) {
      try {
        const result = await api<{ transactions: StreamEvent[] }>('/api/transactions/simulate', { method: 'POST', body: JSON.stringify({ count: 1 }) });
        result.transactions.forEach(onEvent);
        void loadStatus();
      } catch (e) { setError(e instanceof Error ? e.message : 'Simulation request failed'); stop(); break; }
      await new Promise<void>((resolve) => { window.setTimeout(resolve, 900); });
    }
  };
  const latest = events[0];
  const latestGraph = latest?.graph;
  return <section className="integration-panel live-panel">
    <div className="integration-panel-head"><div className="integration-icon live-icon"><Network size={17} /></div><div><div className="panel-eyebrow">REAL-TIME SYNTHETIC STREAM</div><h3>Live simulation</h3></div><span className={`integration-status ${health}`}><i />{health === 'online' ? 'API healthy' : health === 'offline' ? 'API unavailable' : 'Checking'}</span></div>
    <p className="integration-copy">Each generated event runs through incremental risk scoring, a bounded transaction subgraph, taint estimate, alert rules and next-move prediction.</p>
    <button className={`button ${running ? 'button-danger' : 'button-primary'} integration-run`} onClick={running ? stop : () => void start()}>
      {running ? <><CircleStop size={16} /> Stop simulation</> : <><CirclePlay size={16} /> Start Live Simulation</>}
    </button>
    {error && <div className="integration-error"><AlertTriangle size={14} />{error}</div>}
    <div className="stream-kpis">
      <div><span>Stream events</span><b>{operational?.stream_transactions_total?.toLocaleString() ?? '—'}</b></div>
      <div><span>With alerts</span><b>{operational?.stream_transactions_with_alerts?.toLocaleString() ?? '—'}</b></div>
      <div><span>API mean</span><b>{operational ? `${operational.api.mean_response_ms.toFixed(1)} ms` : '—'}</b></div>
    </div>
    {latest && <>
      <div className="stream-analysis"><div className="stream-risk"><span>Latest risk</span><b className={`risk-${latest.analysis.risk_band}`}>{Math.round(latest.analysis.risk_score * 100)}% · {latest.analysis.risk_band}</b><small>Potential taint estimate {amount(latest.analysis.taint.potentially_tainted_bdt_estimate)}</small></div>
        <div className="stream-predictions"><span>Next-move prediction</span>{Object.entries(latest.analysis.predictions.next_move_probabilities).map(([name, probability]) => <small key={name}>{name.replace('_', ' ')} <b>{Math.round(probability * 100)}%</b></small>)}</div>
      </div>
      <div className="stream-graph"><div className="stream-graph-title"><span><Network size={14} /> Latest local graph</span><small>{latestGraph?.node_count ?? 0} wallets · {latestGraph?.edge_count ?? 0} edges</small></div>
        <div className="stream-edge"><span>{latest.transaction.sender_wallet}</span><ArrowRight size={14} /><span>{latest.transaction.receiver_wallet}</span><b>{amount(latest.transaction.amount_bdt)}</b></div>
      </div>
      <div className="stream-alerts"><span><AlertTriangle size={14} /> Alert rules</span>{latest.analysis.alerts.length ? latest.analysis.alerts.map((alert) => <small key={alert.code} className={`alert-${alert.severity}`}>{alert.severity}: {alert.message}</small>) : <small>No rule alerts on the latest event.</small>}</div>
      <div className="stream-latest"><b>Latest event</b><span>{latest.transaction.transaction_id}</span><small>analysis {latest.processing_ms.toFixed(2)} ms · graph {latest.graph_processing_ms.toFixed(2)} ms</small></div>
    </>}
    {!latest && <div className="integration-empty">Start the simulator to generate its first synthetic event.</div>}
    <button className="integration-refresh" onClick={() => void loadStatus()}><RefreshCw size={13} /> Refresh API status</button>
  </section>;
}

function CaseManagementPanel({ latest, refreshKey }: { latest: StreamEvent | null; refreshKey: number }) {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [title, setTitle] = useState('Review synthetic stream alert');
  const [investigator, setInvestigator] = useState('Nadia Rahman');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { const result = await api<{ cases: CaseRecord[] }>('/api/cases?limit=10'); setCases(result.cases); }
    catch (e) { setError(e instanceof Error ? e.message : 'Case list unavailable'); }
  }, []);
  useEffect(() => { void load(); }, [load, refreshKey]);
  const create = async () => {
    setBusy(true); setError('');
    try {
      await api<CaseRecord>('/api/cases', { method: 'POST', body: JSON.stringify({
        transaction_id: latest?.transaction.transaction_id,
        risk_score: latest?.analysis.risk_score ?? 0.25,
        investigator: investigator.trim() || 'Unassigned', title: title.trim() || 'Synthetic review', status: 'new',
      }) });
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Case creation failed'); }
    finally { setBusy(false); }
  };
  const patch = async (id: string, fields: Partial<CaseRecord>) => {
    try { await api(`/api/cases/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(fields) }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Case update failed'); }
  };
  return <section className="integration-panel case-ops-panel">
    <div className="integration-panel-head"><div className="integration-icon case-icon"><ShieldCheck size={17} /></div><div><div className="panel-eyebrow">CASE-MANAGEMENT ADAPTER</div><h3>Investigation cases</h3></div><span className="case-total">{cases.length} shown</span></div>
    <p className="integration-copy">Create a review record from the latest stream event, then assign an investigator and track status through the case API.</p>
    <div className="case-create"><label>Case title<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={200} /></label><label>Investigator<input value={investigator} onChange={(event) => setInvestigator(event.target.value)} maxLength={120} /></label>
      <button className="button button-secondary" onClick={() => void create()} disabled={busy}><Plus size={15} /> {busy ? 'Creating…' : 'Create review case'}</button>
    </div>
    {error && <div className="integration-error"><AlertTriangle size={14} />{error}</div>}
    <div className="case-table-wrap"><table className="case-table"><thead><tr><th>Case ID</th><th>Risk</th><th>Investigator</th><th>Status</th></tr></thead><tbody>
      {cases.map((item) => <tr key={item.case_id}><td><b>{item.case_id}</b><small>{item.title}</small></td><td><span className={`case-risk ${item.risk_score >= 0.7 ? 'high' : item.risk_score >= 0.4 ? 'medium' : 'low'}`}>{Math.round(item.risk_score * 100)}%</span></td>
        <td><input aria-label={`Investigator for ${item.case_id}`} defaultValue={item.investigator} onBlur={(event) => { if (event.target.value !== item.investigator) void patch(item.case_id, { investigator: event.target.value }); }} /></td>
        <td><select aria-label={`Status for ${item.case_id}`} value={item.status} onChange={(event) => void patch(item.case_id, { status: event.target.value })}><option value="new">New</option><option value="investigating">Investigating</option><option value="escalated">Escalated</option><option value="resolved">Resolved</option><option value="closed">Closed</option></select></td></tr>)}
      {!cases.length && <tr><td colSpan={4} className="case-empty"><Gauge size={14} />No cases yet. Generate a stream event, then create a review case.</td></tr>}
    </tbody></table></div>
    <div className="case-panel-foot"><span><Activity size={13} /> {cases.filter((item) => !['resolved', 'closed'].includes(item.status)).length} open cases</span><button className="integration-refresh" onClick={() => void load()}><RefreshCw size={13} /> Refresh</button></div>
  </section>;
}

type FairnessMetrics = {
  synthetic: boolean;
  evaluation_split: string;
  test_threshold: number;
  overall_test_metrics: Record<string, any>;
  test_metrics_by_segment: Record<string, Array<{ segment: string; metrics: Record<string, any>; gaps_vs_overall: Record<string, any> }>>;
  gap_comparisons: Record<string, Record<string, any>>;
  threshold_analysis: { split: string; warning: string; points: Array<{ threshold: number; matches_model_selected_threshold: boolean; metrics: Record<string, any>; false_positive_count: number; legitimate_value_affected_bdt: number; analyst_workload: Record<string, any> }> };
  intervention_policy_comparison: { results: Array<{ label: string; candidate_wallet_case_recommendations: number; false_positive_count: number; false_positive_rate: number | null; false_negative_count: number; missed_fraud_rate: number | null; precision: number | null; simulated_legitimate_value_affected_bdt: number; analyst_workload: { estimated_analyst_workload_minutes: number }; human_review_required_before_any_action: boolean }> };
  false_positive_impact: { false_positive_count: number; false_positive_rate: number | null; legitimate_value_affected_bdt: number; affected_legitimate_transaction_count: number };
  limitations: string[];
};
type FalsePositiveMetrics = { synthetic: boolean; overall: { false_positive_count: number; false_positive_rate: number | null; legitimate_value_affected_bdt: number; average_legitimate_value_affected_bdt: number | null; median_legitimate_value_affected_bdt: number | null; affected_legitimate_transaction_count: number; segment_impact: Array<{ segment_dimension: string; segment: string; false_positive_wallets: number; affected_case_count: number; simulated_legitimate_value_affected_bdt: number }> } };

const percent = (value: unknown) => value === null || value === undefined || !Number.isFinite(Number(value)) ? '—' : `${(Number(value) * 100).toFixed(1)}%`;

function FairnessDashboardPanel() {
  const [token, setToken] = useState('');
  const [report, setReport] = useState<FairnessMetrics | null>(null);
  const [impact, setImpact] = useState<FalsePositiveMetrics | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const load = async () => {
    if (!token.trim()) { setError('Enter a configured fairness:read bearer token.'); return; }
    setBusy(true); setError('');
    const headers = { Authorization: `Bearer ${token.trim()}` };
    try {
      const [metrics, harm] = await Promise.all([
        api<FairnessMetrics>('/api/metrics/fairness', { headers }),
        api<FalsePositiveMetrics>('/api/metrics/false-positive-impact', { headers }),
      ]);
      setReport(metrics); setImpact(harm);
    } catch (e) { setError(e instanceof Error ? e.message : 'Protected fairness metrics could not be loaded.'); }
    finally { setBusy(false); }
  };
  const segmentRows = report ? Object.entries(report.test_metrics_by_segment).flatMap(([dimension, rows]) => rows.map((row) => ({ dimension, ...row }))) : [];
  const segmentImpact = impact?.overall.segment_impact ?? [];
  const gapRows = report ? Object.entries(report.gap_comparisons) : [];
  return <section className="integration-panel fairness-panel">
    <div className="integration-panel-head"><div className="integration-icon fairness-icon"><ShieldCheck size={17} /></div><div><div className="panel-eyebrow">SYNTHETIC EVALUATION — NOT PRODUCTION FAIRNESS VALIDATION</div><h3>Subgroup errors &amp; customer-impact review</h3></div><span className="case-total">AGGREGATE ONLY</span></div>
    <p className="integration-copy">Compares false-positive/false-negative rates, true-positive rates, precision and policy counterfactuals across existing synthetic operational cohorts. This is not evidence of fairness on real MFS customers.</p>
    <div className="fairness-auth"><label>Fairness read token <small>Sent only to this API request; kept in memory and never saved.</small><input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} placeholder="Operator-configured bearer token" /></label><button className="button button-secondary" onClick={() => void load()} disabled={busy}>{busy ? 'Loading…' : 'Load protected metrics'}</button></div>
    {error && <div className="integration-error"><AlertTriangle size={14} />{error}</div>}
    {!report && <div className="integration-empty">Fairness metrics are access-controlled. Configure <code>FLOWFREEZE_RBAC_TOKENS</code> on the API, then enter a role token here.</div>}
    {report && <>
      <div className="fairness-kpis"><div><span>Held-out test FPR</span><b>{percent(report.overall_test_metrics.false_positive_rate)}</b></div><div><span>Held-out test FNR</span><b>{percent(report.overall_test_metrics.false_negative_rate)}</b></div><div><span>Precision</span><b>{percent(report.overall_test_metrics.precision)}</b></div><div><span>False-positive wallet-cases</span><b>{(impact?.overall.false_positive_count ?? report.false_positive_impact.false_positive_count).toLocaleString()}</b></div><div><span>Legitimate value exposed</span><b>{amount(impact?.overall.legitimate_value_affected_bdt ?? report.false_positive_impact.legitimate_value_affected_bdt)}</b></div><div><span>Operating threshold</span><b>{percent(report.test_threshold)}</b></div></div>
      <div className="fairness-value-stats"><span>Per affected legitimate synthetic transaction:</span><b>mean {impact?.overall.average_legitimate_value_affected_bdt !== null && impact?.overall.average_legitimate_value_affected_bdt !== undefined ? amount(impact.overall.average_legitimate_value_affected_bdt) : '—'}</b><b>median {impact?.overall.median_legitimate_value_affected_bdt !== null && impact?.overall.median_legitimate_value_affected_bdt !== undefined ? amount(impact.overall.median_legitimate_value_affected_bdt) : '—'}</b><small>{impact?.overall.affected_legitimate_transaction_count ?? report.false_positive_impact.affected_legitimate_transaction_count} distinct generated transactions</small></div>
      <div className="fairness-table-wrap"><table className="fairness-table"><thead><tr><th>Cohort</th><th>Population (n)</th><th>Fraud prevalence</th><th>TPR</th><th>FPR</th><th>FNR</th><th>Precision</th><th>FP wallets / cases</th><th>Legitimate value</th><th>Support</th></tr></thead><tbody>
        {segmentRows.map((row) => { const harm = segmentImpact.find((item) => item.segment_dimension === row.dimension && item.segment === row.segment); return <tr key={`${row.dimension}:${row.segment}`}><td><b>{row.segment}</b><small>{row.dimension.replaceAll('_', ' ')}</small></td><td>{row.metrics.sample_count}</td><td>{percent(row.metrics.fraud_prevalence)}</td><td>{row.metrics.reliability.metric_reliable.true_positive_rate ? percent(row.metrics.true_positive_rate) : '—'}</td><td>{row.metrics.reliability.metric_reliable.false_positive_rate ? percent(row.metrics.false_positive_rate) : '—'}</td><td>{row.metrics.reliability.metric_reliable.false_negative_rate ? percent(row.metrics.false_negative_rate) : '—'}</td><td>{row.metrics.reliability.metric_reliable.precision ? percent(row.metrics.precision) : '—'}</td><td>{harm ? `${harm.false_positive_wallets} / ${harm.affected_case_count}` : '—'}</td><td>{amount(harm?.simulated_legitimate_value_affected_bdt ?? 0)}</td><td>{row.metrics.reliability.status === 'meets_exploratory_minimums' ? 'Exploratory' : 'Low support'}</td></tr>; })}
      </tbody></table></div>
      <div className="fairness-gap-summary"><b>Observed best-to-worst cohort gaps · held-out test split</b>{gapRows.map(([dimension, metrics]) => <div key={dimension}><strong>{dimension.replaceAll('_', ' ')}</strong><span>FPR {percent(metrics.false_positive_rate?.best_to_worst_absolute_gap)} · FNR {percent(metrics.false_negative_rate?.best_to_worst_absolute_gap)} · TPR {percent(metrics.true_positive_rate?.best_to_worst_absolute_gap)} · precision {percent(metrics.precision?.best_to_worst_absolute_gap)}</span><small>Descriptive ranges only · unsupported one-class comparisons are suppressed.</small></div>)}</div>
      <div className="fairness-strategies"><b>Test-split strategy comparison</b><div className="fairness-strategy-grid">{report.intervention_policy_comparison.results.map((strategy) => <div key={strategy.label}><strong>{strategy.label}</strong><span>{strategy.candidate_wallet_case_recommendations.toLocaleString()} review candidates · {strategy.false_positive_count.toLocaleString()} false positives · {percent(strategy.false_positive_rate)} FPR</span><span>{strategy.false_negative_count.toLocaleString()} missed fraud wallet-cases · {percent(strategy.missed_fraud_rate)} FNR · {percent(strategy.precision)} precision</span><span>{amount(strategy.simulated_legitimate_value_affected_bdt)} legitimate transaction value exposed · {strategy.analyst_workload.estimated_analyst_workload_minutes.toFixed(0)} assumed analyst min</span><small>{strategy.human_review_required_before_any_action ? 'Human review required; no action executed.' : 'Aggressive counterfactual only; no action executed.'}</small></div>)}</div></div>
      <details className="fairness-threshold-details"><summary>Validation threshold diagnostics ({report.threshold_analysis.split} split only)</summary><p>{report.threshold_analysis.warning}</p><div className="fairness-table-wrap"><table className="fairness-table"><thead><tr><th>Threshold</th><th>FPR</th><th>FNR</th><th>False positives</th><th>Value exposed</th></tr></thead><tbody>{report.threshold_analysis.points.map((point) => <tr key={point.threshold}><td>{percent(point.threshold)}{point.matches_model_selected_threshold ? ' · selected' : ''}</td><td>{percent(point.metrics.false_positive_rate)}</td><td>{percent(point.metrics.false_negative_rate)}</td><td>{point.false_positive_count}</td><td>{amount(point.legitimate_value_affected_bdt)}</td></tr>)}</tbody></table></div></details>
      <div className="fairness-footnote">Synthetic records only · identifiers are not returned · value is a counterfactual transaction-volume proxy, not measured harm. Review gaps as investigation signals, not fairness claims.</div>
    </>}
  </section>;
}
