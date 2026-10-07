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
