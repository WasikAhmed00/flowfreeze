import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowLeftRight, ArrowRight, ArrowUpRight,
  Bell, Check, CheckCircle2, ChevronDown, ChevronRight, CircleDollarSign, Clock3,
  FileCheck2, FlaskConical, Gauge, GitBranch, History, Info, Landmark, LockKeyhole,
  LogOut, Menu, Network, RefreshCw, Search, ShieldAlert, ShieldCheck, SlidersHorizontal,
  Sparkles, WalletCards, X, Zap,
} from 'lucide-react';
import type { Analysis, DecisionRecord, Incident, Metrics, WalletRecommendation, WalletTaint } from './types';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const WRITE_KEY = import.meta.env.VITE_DEMO_WRITE_KEY || '';
const API_HEADERS: HeadersInit = { 'Content-Type': 'application/json', ...(WRITE_KEY ? { 'X-FlowFreeze-Write-Key': WRITE_KEY } : {}) };
const DEMO_LABEL = 'SYNTHETIC DEMO';
const DEFAULT_DEMO_SCENARIO = 'SCN-02-FANOUT-0001';

type View = 'dashboard' | 'incidents' | 'case' | 'graph' | 'wallets' | 'recommendations' | 'simulator' | 'evaluation' | 'business-impact' | 'shadow-mode' | 'audit';
type Edge = { id: string; from: string; to: string; amount: number; taint: number; time: string; cashout: boolean; type: string };
type BusinessImpact = { synthetic: boolean; label: string; case_count: number; fraud_loss: Record<string, any>; investigation_efficiency: Record<string, any>; customer_harm: Record<string, any>; analyst_productivity: Record<string, any>; baseline_vs_flowfreeze: Record<string, any>; assumptions: string[]; limitations: string[]; validation_targets: Record<string, any> };
type ShadowImpact = { synthetic: boolean; label: string; pilot_label: string; cases_evaluated: number; current_process: Record<string, any>; flowfreeze_shadow: Record<string, any>; investigation: Record<string, any>; business: Record<string, any>; human: Record<string, any>; feedback_summary: Record<string, any>; business_success_targets: Record<string, any>; assumptions: string[]; limitations: string[]; automatic_execution: boolean; financial_actions_executed: number };
type FeedbackInput = { was_useful: 'yes' | 'partially' | 'no'; recommendation_feedback: 'helpful' | 'not_helpful'; trace_accuracy: 'accurate' | 'partially_accurate' | 'inaccurate'; confidence: 'low' | 'medium' | 'high'; reason: string };

type DecisionDraft = { recommendation: WalletRecommendation; decision: 'approve' | 'reject' | 'modify' } | null;

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_ORIGIN}${path}`, {
    ...options,
    headers: { ...API_HEADERS, ...(options.headers || {}) },
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* keep the status text */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const money = (value: unknown, compact = false) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return `৳${new Intl.NumberFormat('en-BD', { maximumFractionDigits: 0, notation: compact ? 'compact' : 'standard' }).format(number)}`;
};
const moneyExact = (value: unknown) => {
  const number = Number(value);
  return Number.isFinite(number) ? `৳${new Intl.NumberFormat('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(number)}` : '—';
};
const shortId = (value = '') => value.length > 23 ? `${value.slice(0, 11)}…${value.slice(-7)}` : value;
const walletName = (id = '') => id.split('-').slice(-1)[0].replaceAll('_', ' ');
const titleCase = (value = '') => value.replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase());
const dateTime = (value?: string) => value ? new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '—';
const pct = (value: unknown) => Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(0)}%` : '—';

const NAV: { id: View; label: string; icon: typeof Activity; group: string }[] = [
  { id: 'dashboard', label: 'Overview', icon: Activity, group: 'Workspace' },
  { id: 'incidents', label: 'Incidents', icon: ShieldAlert, group: 'Workspace' },
  { id: 'case', label: 'Case review', icon: FileCheck2, group: 'Workspace' },
  { id: 'graph', label: 'Fund-flow graph', icon: Network, group: 'Intelligence' },
  { id: 'wallets', label: 'Wallet intelligence', icon: WalletCards, group: 'Intelligence' },
  { id: 'recommendations', label: 'Recommendations', icon: CheckCircle2, group: 'Decisioning' },
  { id: 'simulator', label: 'What-if simulator', icon: FlaskConical, group: 'Decisioning' },
  { id: 'evaluation', label: 'Evaluation', icon: Gauge, group: 'Governance' },
  { id: 'business-impact', label: 'Business impact', icon: CircleDollarSign, group: 'Governance' },
  { id: 'shadow-mode', label: 'Shadow mode', icon: ShieldCheck, group: 'Governance' },
  { id: 'audit', label: 'Audit history', icon: History, group: 'Governance' },
];

function buildEdges(analysis?: Analysis | null): Edge[] {
  const movements = analysis?.taint?.movements || [];
  const result = new Map<string, Edge>();
  movements.forEach((move: Record<string, any>) => {
    const id = String(move.transaction_id || `${move.from_wallet}-${move.to_wallet}-${move.timestamp}`);
    result.set(id, {
      id,
      from: String(move.from_wallet || ''),
      to: String(move.to_wallet || ''),
      amount: Number(move.gross_amount_bdt || 0),
      taint: Number(move.potentially_tainted_bdt || 0),
      time: String(move.timestamp || ''),
      cashout: Boolean(move.terminal_cashout),
      type: String(move.transaction_type || 'transfer'),
    });
  });
  return [...result.values()].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
}

function App() {
  const [analyst, setAnalyst] = useState(() => sessionStorage.getItem('flowfreeze-analyst') || '');
  const [analystInput, setAnalystInput] = useState('Nadia Rahman');
  const [view, setView] = useState<View>('dashboard');
  const [mobileNav, setMobileNav] = useState(false);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentOffset, setIncidentOffset] = useState(0);
  const [incidentTotal, setIncidentTotal] = useState(0);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [businessImpact, setBusinessImpact] = useState<BusinessImpact | null>(null);
  const [shadowImpact, setShadowImpact] = useState<ShadowImpact | null>(null);
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [apiState, setApiState] = useState<'checking' | 'online' | 'offline'>('checking');
  const [apiError, setApiError] = useState('');
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [pendingCount, setPendingCount] = useState<number | null>(null);
  const [analysisMs, setAnalysisMs] = useState<number | null>(null);
  const [analysisTimes, setAnalysisTimes] = useState<number[]>([]);
  const [searchText, setSearchText] = useState('');
  const [decisionDraft, setDecisionDraft] = useState<DecisionDraft>(null);
  const [toast, setToast] = useState('');

  const selectedIncident = useMemo(() => incidents.find((incident) => incident.scenario_id === selectedId) || analysis?.incident || null, [incidents, selectedId, analysis]);
  const recommendationList = analysis?.recommendation?.recommendations || [];
  const edgeList = useMemo(() => buildEdges(analysis), [analysis]);
  const selectedWallets = analysis?.taint?.wallets || [];

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    api<{ status: string }>('/health').then(() => setApiState('online')).catch(() => setApiState('offline'));
  }, []);

  useEffect(() => {
    if (!analyst) return;
    let live = true;
    const load = async () => {
      setBusy(true);
      const [healthResult, incidentResult, metricResult, impactResult, shadowResult, decisionResult, pendingResult] = await Promise.allSettled([
        api<{ status: string }>('/health'),
        api<{ incidents: Incident[]; total: number }>(`/api/incidents?limit=100&offset=${incidentOffset}`),
        api<Metrics>('/api/metrics'),
        api<BusinessImpact>('/api/metrics/business-impact'),
        api<ShadowImpact>('/api/metrics/shadow-mode'),
        api<{ decisions: DecisionRecord[] }>('/api/decisions?limit=100'),
        api<{ total: number }>('/api/incidents?status=new&limit=1'),
      ]);
      if (!live) return;
      if (healthResult.status === 'fulfilled') { setApiState('online'); setApiError(''); }
      else { setApiState('offline'); setApiError(healthResult.reason instanceof Error ? healthResult.reason.message : 'API is unavailable'); }
      if (incidentResult.status === 'fulfilled') {
        setIncidents(incidentResult.value.incidents || []);
        setIncidentTotal(incidentResult.value.total || 0);
        setSelectedId((current) => current || DEFAULT_DEMO_SCENARIO || incidentResult.value.incidents?.[0]?.scenario_id || '');
      } else setIncidents([]);
      if (metricResult.status === 'fulfilled') setMetrics(metricResult.value);
      if (impactResult.status === 'fulfilled') setBusinessImpact(impactResult.value);
      if (shadowResult.status === 'fulfilled') setShadowImpact(shadowResult.value);
      if (decisionResult.status === 'fulfilled') setDecisions(decisionResult.value.decisions || []);
      if (pendingResult.status === 'fulfilled') setPendingCount(pendingResult.value.total);
      setBusy(false);
    };
    void load();
    return () => { live = false; };
  }, [analyst, reloadKey, incidentOffset]);

  useEffect(() => {
    if (!analyst || !selectedId) { setAnalysis(null); return; }
    let live = true;
    const started = performance.now();
    setAnalysis(null);
    api<Analysis>(`/api/analysis/${encodeURIComponent(selectedId)}`)
      .then((result) => {
        if (!live) return;
        setAnalysis(result);
        const elapsed = performance.now() - started;
        setAnalysisMs(elapsed);
        setAnalysisTimes((times) => [...times, elapsed].slice(-20));
      })
      .catch((error: Error) => { if (live) setApiError(error.message); });
    return () => { live = false; };
  }, [analyst, selectedId, reloadKey]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(''), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const enterWorkspace = () => {
    const name = analystInput.trim() || 'Demo Analyst';
    sessionStorage.setItem('flowfreeze-analyst', name);
    setAnalyst(name);
  };
  const signOut = () => { sessionStorage.removeItem('flowfreeze-analyst'); setAnalyst(''); setAnalysis(null); };
  const openIncident = (incident: Incident, nextView: View = 'case') => {
    setSelectedId(incident.scenario_id);
    setView(nextView);
    setMobileNav(false);
  };

  const makeDecision = async (decision: 'approve' | 'reject' | 'modify', recommendation: WalletRecommendation, amount: number, reason: string, feedback: FeedbackInput) => {
    if (!selectedId || !reason.trim()) return;
    try {
      const saved = await api<DecisionRecord>('/api/decisions', {
        method: 'POST',
        body: JSON.stringify({
          scenario_id: selectedId,
          wallet_id: recommendation.wallet_id,
          decision,
          proposed_amount_bdt: decision === 'reject' ? '0.00' : amount.toFixed(2),
          reason: reason.trim(),
          actor: analyst || 'Demo Analyst',
        }),
      });
      let feedbackNote = '';
      try {
        await api(`/api/decisions/${saved.decision_id}/feedback`, { method: 'POST', body: JSON.stringify({ ...feedback, actor: analyst || 'Demo Analyst' }) });
        feedbackNote = ' · feedback saved to the append-only audit log';
      } catch (feedbackError) {
        feedbackNote = ` · decision saved, but feedback could not be recorded (${feedbackError instanceof Error ? feedbackError.message : 'API error'})`;
      }
      let outcomeNote = '';
      try {
        const outcome = await api<Record<string, any>>(`/api/simulation/${saved.decision_id}`, { method: 'POST' });
        outcomeNote = ` · simulated ${money(outcome.estimated_tainted_preserved_bdt)} potentially tainted value preserved`;
      } catch (simulationError) {
        outcomeNote = ` · decision recorded; outcome simulation unavailable (${simulationError instanceof Error ? simulationError.message : 'API error'})`;
      }
      setToast(`Decision recorded${outcomeNote}${feedbackNote}. No wallet or ledger action was taken.`);
      setDecisionDraft(null);
      refresh();
    } catch (error) {
      setToast(`Could not record this decision: ${error instanceof Error ? error.message : 'API error'}`);
    }
  };

  if (!analyst) return <LoginScreen value={analystInput} onChange={setAnalystInput} onEnter={enterWorkspace} apiState={apiState} />;

  const viewTitle = NAV.find((item) => item.id === view)?.label || 'Overview';
  const displayedIncidents = incidents.filter((incident) => `${incident.incident_id} ${incident.scenario_id} ${incident.scenario_type} ${incident.incident_type}`.toLowerCase().includes(searchText.toLowerCase()));
  const sampleIncidentValue = incidents.slice(0, 6).reduce((sum, incident) => sum + Number(incident.reported_amount || 0), 0);
  const averageAnalysisMs = analysisTimes.length ? analysisTimes.reduce((sum, value) => sum + value, 0) / analysisTimes.length : analysisMs;
  const preservedValue = metrics?.simulations?.estimated_tainted_value_preserved_bdt || '0';
  const remainingTaint = analysis?.taint?.remaining_potentially_tainted_bdt || 0;
  const highRiskWalletCount = analysis?.model_predictions?.source === 'trained_synthetic_models' ? recommendationList.filter((item) => item.risk_score != null && item.risk_score >= 0.65).length : null;
  const pendingReviewCount = recommendationList.filter((item) => !decisions.some((decision) => decision.scenario_id === selectedId && decision.wallet_id === item.wallet_id)).length;

  const renderPage = () => {
    switch (view) {
      case 'dashboard':
        return <DashboardPage
          incidents={incidents.slice(0, 6)}
          selected={selectedIncident}
          onOpen={(incident) => openIncident(incident, 'case')}
          onViewAll={() => setView('incidents')}
          pendingCount={pendingCount}
          totalCount={incidentTotal}
          latestValue={sampleIncidentValue}
          reachable={remainingTaint}
          preserved={preservedValue}
          highRiskCount={highRiskWalletCount}
          analysisMs={averageAnalysisMs}
          simulationCount={metrics?.simulations?.count || 0}
          pendingReviewCount={pendingReviewCount}
          modelStatus={analysis?.model_predictions}
          analysis={analysis}
          decisions={decisions}
        />;
      case 'incidents':
        return <IncidentsPage incidents={displayedIncidents} total={incidentTotal} offset={incidentOffset} pageSize={100} selectedId={selectedId} onOpen={(incident) => openIncident(incident, 'case')} onPage={setIncidentOffset} />;
      case 'case':
        return <CaseReviewPage incident={selectedIncident} analysis={analysis} loading={!analysis && Boolean(selectedId)} onGoGraph={() => setView('graph')} onGoRecommendation={() => setView('recommendations')} />;
      case 'graph':
        return <GraphPage incident={selectedIncident} analysis={analysis} edges={edgeList} />;
      case 'wallets':
        return <WalletsPage wallets={selectedWallets} recommendations={recommendationList} analysis={analysis} onReview={(item) => setDecisionDraft({ recommendation: item, decision: 'approve' })} />;
      case 'recommendations':
        return <RecommendationsPage incident={selectedIncident} analysis={analysis} recommendations={recommendationList} onDecide={(item, decision) => setDecisionDraft({ recommendation: item, decision })} />;
      case 'simulator':
        return <SimulatorPage incident={selectedIncident} analysis={analysis} metrics={metrics} />;
      case 'evaluation':
        return <EvaluationPage metrics={metrics} />;
      case 'business-impact':
        return <BusinessImpactPage impact={businessImpact} />;
      case 'shadow-mode':
        return <ShadowModePage shadow={shadowImpact} />;
      case 'audit':
        return <AuditPage decisions={decisions} onOpen={(incident) => openIncident(incident, 'case')} />;
      default:
        return null;
    }
  };

  const pageActions = <>
    <button className="icon-button notification" aria-label="Notifications" onClick={() => setView('recommendations')}><Bell size={17} /><span /></button>
    <button className="avatar-button" title={`Sign out ${analyst}`} aria-label={`Sign out ${analyst}`} onClick={signOut}>{analyst.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</button>
  </>;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="brand"><div className="brand-mark"><span>F</span><i /></div><div><b>flowfreeze</b><small>ANALYST WORKSPACE</small></div><button className="mobile-close icon-button" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={17} /></button></div>
        <div className="workspace-chip"><div className="workspace-symbol">U</div><div><strong>upay BD</strong><span>Fraud operations</span></div><ChevronDown size={15} /></div>
        <nav className="side-nav">
          {['Workspace', 'Intelligence', 'Decisioning', 'Governance'].map((group) => <div className="nav-group" key={group}>
            <span className="nav-label">{group}</span>
            {NAV.filter((item) => item.group === group).map((item) => {
              const Icon = item.icon;
              return <button className={`nav-item ${view === item.id ? 'active' : ''}`} key={item.id} onClick={() => { setView(item.id); setMobileNav(false); }}><Icon size={17} strokeWidth={1.8} /><span>{item.label}</span>{item.id === 'recommendations' && pendingReviewCount > 0 ? <em>{pendingReviewCount > 99 ? '99+' : pendingReviewCount}</em> : null}</button>;
            })}
          </div>)}
        </nav>
        <div className="sidebar-bottom">
          <div className="safe-card"><div className="safe-icon"><ShieldCheck size={17} /></div><div><b>Safe demo environment</b><span>Synthetic data · no live wallet access</span></div></div>
          <button className="profile-row" onClick={signOut}><div className="avatar avatar-small">{analyst.split(' ').map((part) => part[0]).slice(0, 2).join('').toUpperCase()}</div><div className="profile-meta"><b>{analyst}</b><span>Demo analyst access</span></div><LogOut size={15} /></button>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left"><button className="mobile-menu icon-button" onClick={() => setMobileNav(true)} aria-label="Open menu"><Menu size={19} /></button><div className="breadcrumbs"><span>FlowFreeze</span><ChevronRight size={13} /><b>{viewTitle}</b></div></div>
          <div className="topbar-right"><div className={`service-status ${apiState}`}><span className="status-dot" />{apiState === 'online' ? 'API connected' : apiState === 'offline' ? 'API offline' : 'Connecting'}</div><button className="icon-button refresh-button" onClick={refresh} disabled={busy} title="Refresh data"><RefreshCw size={16} className={busy ? 'spin' : ''} /></button>{pageActions}</div>
        </header>
        <main className="page-content">
          <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-mark" />{DEMO_LABEL}<span className="eyebrow-divider">/</span> upay BD</div><h1>{viewTitle}</h1><p>{pageDescription(view, selectedIncident)}</p></div>
            <div className="heading-tools"><label className="search-box"><Search size={16} /><input value={searchText} onChange={(event) => { setSearchText(event.target.value); if (view !== 'incidents' && event.target.value) setView('incidents'); }} placeholder="Search cases, wallets…" /><kbd>⌘ K</kbd></label><button className="button button-secondary" onClick={refresh}><RefreshCw size={15} /> Refresh</button></div>
          </div>
          <div className="synthetic-banner"><div className="banner-icon"><Info size={16} /></div><div><strong>Synthetic demonstration only.</strong> All amounts and model outputs are generated for this prototype—not upay BD production statistics or customer records.</div><span className="banner-pill">NO LIVE WALLET ACTIONS</span></div>
          {apiState === 'offline' && <div className="inline-alert"><AlertTriangle size={17} /><div><b>Backend not connected</b><span>{apiError || 'Start the FastAPI service to load incident data and record decisions.'} The UI remains available, but live synthetic data is unavailable.</span></div><button className="text-button" onClick={refresh}>Retry</button></div>}
          {renderPage()}
          <footer className="app-footer"><span>FlowFreeze <i>·</i> Analyst decision support prototype</span><span><ShieldCheck size={13} /> Human review required <i>·</i> Simulated actions only</span></footer>
        </main>
      </div>
      {mobileNav && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      {decisionDraft && <DecisionModal draft={decisionDraft} analyst={analyst} onClose={() => setDecisionDraft(null)} onSubmit={makeDecision} />}
      {toast && <div className="toast"><CheckCircle2 size={17} />{toast}<button onClick={() => setToast('')} aria-label="Dismiss"><X size={15} /></button></div>}
    </div>
  );
}

function pageDescription(view: View, incident: Incident | null) {
  const name = incident ? shortId(incident.incident_id) : 'selected synthetic case';
  const descriptions: Record<View, string> = {
    dashboard: 'A clear view of the investigation queue and simulated case outcomes.',
    incidents: 'Review reported transfers and move from intake to evidence-backed analysis.',
    case: `Trace, assess and document the selected incident · ${name}.`,
    graph: 'Follow downstream wallet movement, branching paths and cash-out evidence.',
    wallets: 'Inspect attributed value, current replay balance and available model signals.',
    recommendations: 'Review bounded proposals and record an analyst decision for the selected case.',
    simulator: 'Explore the trade-off between potentially preserved value and legitimate value affected.',
    evaluation: 'Compare FlowFreeze with a direct-recipient baseline on held-out synthetic cases.',
    'business-impact': 'Synthetic counterfactuals for exposure, investigation effort, and customer-harm trade-offs.',
    'shadow-mode': 'Record-only simulation and readiness measures for a future partner-governed pilot.',
    audit: 'Append-only record of synthetic analyst decisions and simulated outcomes.',
  };
  return descriptions[view];
}

function LoginScreen({ value, onChange, onEnter, apiState }: { value: string; onChange: (value: string) => void; onEnter: () => void; apiState: string }) {
  return <div className="login-screen"><div className="login-glow login-glow-one" /><div className="login-glow login-glow-two" /><div className="login-top"><div className="brand brand-login"><div className="brand-mark"><span>F</span><i /></div><div><b>flowfreeze</b><small>ANALYST WORKSPACE</small></div></div><div className="login-demo-tag"><span className="status-dot" /> SYNTHETIC DEMO ENVIRONMENT</div></div>
    <div className="login-layout"><div className="login-story"><div className="login-kicker"><ShieldCheck size={15} /> PROTECTING THE DIGITAL FLOW</div><h1>Follow the money.<br /><span>Before it disappears.</span></h1><p>FlowFreeze helps fraud analysts trace reported MFS transfers through downstream wallets, understand potential exposure, and review proportionate next steps.</p>
      <div className="login-flow"><div className="flow-step"><span className="step-icon"><ArrowLeftRight size={17} /></span><div><b>Trace fund movement</b><small>Follow the path across wallet hops</small></div></div><div className="flow-connector" /><div className="flow-step"><span className="step-icon step-icon-amber"><Sparkles size={17} /></span><div><b>Assess risk & taint</b><small>Explore evidence and uncertainty</small></div></div><div className="flow-connector" /><div className="flow-step"><span className="step-icon step-icon-lime"><Check size={17} /></span><div><b>Keep people in control</b><small>Analyst review before any simulation</small></div></div></div>
      <div className="login-quote"><span>“</span><div>Trace suspicious funds, predict where they go next, and help contain them while they’re still digital.</div></div>
    </div><div className="login-panel"><div className="login-panel-mark"><LockKeyhole size={18} /></div><div className="login-panel-eyebrow">ANALYST ACCESS</div><h2>Enter the workspace</h2><p>Choose a display name to continue to this local demonstration.</p><label className="form-label" htmlFor="analyst-name">Analyst name</label><div className="input-with-icon"><span className="initial-badge">{value.slice(0, 1).toUpperCase() || 'A'}</span><input id="analyst-name" value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') onEnter(); }} placeholder="e.g. Nadia Rahman" /></div><button className="button button-primary login-submit" onClick={onEnter}>Open analyst workspace <ArrowRight size={16} /></button><div className="login-no-auth"><Info size={14} /><span>This demo gate is <b>not authentication</b>. Do not enter customer or production data.</span></div><div className="login-api"><span className={`status-dot ${apiState === 'offline' ? 'dot-red' : ''}`} />{apiState === 'online' ? 'Synthetic case API connected' : apiState === 'offline' ? 'API unavailable · start backend to load cases' : 'Checking API connection'}</div></div></div>
    <div className="login-footer"><span>upay BD · Hackathon prototype</span><span>Advisory only <i>·</i> No real customer data <i>·</i> No wallet-control capability</span></div>
  </div>;
}

function DashboardPage(props: {
  incidents: Incident[]; selected: Incident | null; onOpen: (incident: Incident) => void; onViewAll: () => void;
  pendingCount: number | null; totalCount?: number; latestValue: number; reachable: unknown; preserved: unknown;
  highRiskCount: number | null; analysisMs: number | null; simulationCount: number; pendingReviewCount: number; modelStatus?: Record<string, unknown>; analysis: Analysis | null; decisions: DecisionRecord[];
}) {
  const { incidents, selected, onOpen, onViewAll, pendingCount, totalCount, latestValue, reachable, preserved, highRiskCount, analysisMs, simulationCount, pendingReviewCount, modelStatus, analysis, decisions } = props;
  const preservedValue = Number(preserved || 0);
  return <div className="page-stack">
    <div className="welcome-strip"><div className="welcome-icon"><Zap size={18} /></div><div><strong>Good day, analyst.</strong><span>Here’s what’s happening across your synthetic investigation queue.</span></div><button className="button button-white" onClick={onViewAll}>Open case queue <ArrowRight size={15} /></button></div>
    <div className="kpi-grid">
      <KpiCard label="Active incidents" value={pendingCount == null ? '—' : pendingCount.toLocaleString()} note={`${totalCount?.toLocaleString() || '—'} total synthetic cases`} icon={ShieldAlert} accent="teal" />
      <KpiCard label="Suspicious value" value={money(latestValue, true)} note={`Latest ${incidents.length || 0} cases in view`} icon={CircleDollarSign} accent="amber" />
      <KpiCard label="Potentially reachable" value={money(reachable, true)} note="Selected scenario · remaining taint estimate" icon={Network} accent="blue" />
      <KpiCard label="Value preserved" value={money(preservedValue, true)} note={`${simulationCount} recorded simulations`} icon={Landmark} accent="green" />
    </div>
    <div className="dashboard-grid">
      <section className="panel panel-cases"><div className="panel-head"><div><div className="panel-eyebrow">INVESTIGATION QUEUE</div><h2>Recent incidents</h2><p>Cases from the generated synthetic dataset</p></div><button className="button button-light button-sm" onClick={onViewAll}>View all <ArrowRight size={14} /></button></div>
        {incidents.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Incident</th><th>Scenario</th><th>Reported value</th><th>Status</th><th /></tr></thead><tbody>{incidents.map((incident) => <tr key={incident.incident_id} onClick={() => onOpen(incident)} className="click-row"><td><div className="incident-id"><span className="incident-icon"><ShieldAlert size={15} /></span><div><b>{shortId(incident.incident_id)}</b><small>{dateTime(incident.reported_at)}</small></div></div></td><td><span className="scenario-pill">{titleCase(incident.scenario_type)}</span></td><td className="amount-cell">{money(incident.reported_amount)}</td><td><StatusBadge status={incident.status} /></td><td><ChevronRight size={15} className="muted-icon" /></td></tr>)}</tbody></table></div> : <EmptyState title="No incident data yet" text="Connect the FastAPI backend and seed the synthetic database to load cases." />}
      </section>
      <div className="dashboard-right">
        <section className="panel review-panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">NEEDS YOUR ATTENTION</div><h2>Review snapshot</h2></div><span className="review-status"><span className="status-dot" />DEMO</span></div>
          <div className="review-metric-row"><div className="review-icon review-icon-orange"><ClipboardMark /></div><div><strong>{pendingReviewCount.toLocaleString()}</strong><span>Pending analyst reviews · selected case</span></div><ArrowUpRight size={15} /></div>
          <div className="review-metric-row"><div className="review-icon review-icon-red"><AlertTriangle size={16} /></div><div><strong>{highRiskCount == null ? '—' : highRiskCount}</strong><span>High-risk wallets in selected case</span></div><ArrowUpRight size={15} /></div>
          <div className="review-metric-row"><div className="review-icon review-icon-blue"><Clock3 size={16} /></div><div><strong>{analysisMs == null ? '—' : analysisMs < 1000 ? `${Math.max(1, Math.round(analysisMs))}ms` : `${(analysisMs / 1000).toFixed(1)}s`}</strong><span>Mean API response · this session</span></div><span className="live-measured">MEAN</span></div>
          <div className="review-footnote">{modelStatus?.source === 'trained_synthetic_models' ? 'Synthetic model outputs are advisory only; all recommendations require analyst review.' : 'No trained scores? Recommendations remain conservative and require human review.'}</div>
        </section>
        <section className="panel selected-panel"><div className="selected-top"><span className="panel-eyebrow">ACTIVE CASE</span><span className="priority-chip"><span /> {analysis?.recommendation?.status === 'recommendations_available' ? 'IN REVIEW' : 'SELECTED'}</span></div><h3>{selected ? shortId(selected.incident_id) : 'Select a case'}</h3><p>{selected ? `${titleCase(selected.scenario_type)} · ${money(selected.reported_amount)} reported` : 'Open an incident to begin analysis.'}</p><div className="selected-progress"><div><span>Analysis status</span><b>{analysis ? 'Complete' : 'Loading'}</b></div><div className="progress-track"><span style={{ width: analysis ? '100%' : '42%' }} /></div><div className="selected-facts"><span><GitBranch size={14} /> {analysis?.trace?.downstream_wallet_ids?.length ?? 0} downstream wallets</span><span><WalletCards size={14} /> {analysis?.taint?.wallets?.length ?? 0} wallets in replay</span></div></div><button className="button button-primary button-full" onClick={() => selected && onOpen(selected)}>Continue investigation <ArrowRight size={15} /></button></section>
      </div>
    </div>
    <section className="bottom-grid"><div className="panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">CASE SIGNALS</div><h2>Selected case at a glance</h2></div><span className="micro-tag">{DEMO_LABEL}</span></div><div className="signal-grid"><div className="signal-cell"><span>Incident value</span><b>{money(selected?.reported_amount)}</b><small>Reported transfer</small></div><div className="signal-cell"><span>Potential taint</span><b>{money(analysis?.taint?.remaining_potentially_tainted_bdt)}</b><small>Currently attributed in replay</small></div><div className="signal-cell"><span>Next move</span><b>{modelStatus?.source === 'trained_synthetic_models' ? 'Modelled' : 'Not scored'}</b><small>Only shown when model is available</small></div><div className="signal-cell"><span>Recorded decisions</span><b>{decisions.length}</b><small>Across loaded audit history</small></div></div></div><div className="panel model-note"><div className="model-note-icon"><Sparkles size={17} /></div><div><div className="panel-eyebrow">MODEL STATUS</div><h3>{modelStatus?.source === 'trained_synthetic_models' ? 'Synthetic models available' : 'Scores unavailable'}</h3><p>{String(modelStatus?.message || 'Risk and next-move predictions are not shown unless trained synthetic artifacts are available.')}</p><span className="model-note-foot"><Info size={13} /> Scores are advisory, not proof of fraud.</span></div></div></section>
  </div>;
}

function ClipboardMark() { return <FileCheck2 size={16} />; }

function KpiCard({ label, value, note, icon: Icon, accent }: { label: string; value: string; note: string; icon: typeof Activity; accent: string }) {
  return <div className={`kpi-card kpi-${accent}`}><div className="kpi-top"><span>{label}</span><span className="kpi-icon"><Icon size={17} /></span></div><div className="kpi-value">{value}</div><div className="kpi-note"><span className="kpi-dot" />{note}</div></div>;
}

function StatusBadge({ status }: { status: string }) {
  const normalized = (status || 'new').toLowerCase();
  return <span className={`status-badge status-${normalized.replaceAll('_', '-')}`}><i />{titleCase(normalized)}</span>;
}

function IncidentsPage({ incidents, total, offset, pageSize, selectedId, onOpen, onPage }: { incidents: Incident[]; total?: number; offset: number; pageSize: number; selectedId: string; onOpen: (incident: Incident) => void; onPage: (offset: number) => void }) {
  const [statusFilter, setStatusFilter] = useState('all');
  const filtered = incidents.filter((incident) => statusFilter === 'all' || incident.status.toLowerCase() === statusFilter);
  return <div className="page-stack"><section className="panel incident-list-panel"><div className="panel-head"><div><div className="panel-eyebrow">CASE INTAKE</div><h2>Incident register</h2><p>{total?.toLocaleString() || incidents.length} synthetic incidents · newest reports first</p></div><div className="filter-tools"><SlidersHorizontal size={16} /><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="new">New</option><option value="reviewing">Reviewing</option><option value="closed">Closed</option></select></div></div>
    <div className="table-wrap"><table className="data-table incident-register"><thead><tr><th>Incident reference</th><th>Reported</th><th>Case type</th><th>Reported transaction</th><th>Amount</th><th>State</th><th /></tr></thead><tbody>{filtered.map((incident) => <tr key={incident.incident_id} className={`click-row ${incident.scenario_id === selectedId ? 'selected-row' : ''}`} onClick={() => onOpen(incident)}><td><div className="incident-id"><span className="incident-icon"><ShieldAlert size={15} /></span><div><b>{shortId(incident.incident_id)}</b><small>{shortId(incident.scenario_id)}</small></div></div></td><td>{dateTime(incident.reported_at)}</td><td><span className="scenario-pill">{titleCase(incident.scenario_type)}</span></td><td className="mono">{shortId(incident.reported_transaction_id)}</td><td className="amount-cell">{money(incident.reported_amount)}</td><td><StatusBadge status={incident.status} /></td><td><ChevronRight size={15} className="muted-icon" /></td></tr>)}</tbody></table></div>
    {filtered.length === 0 && <EmptyState title="No incidents match" text="Try a different status or clear the search in the toolbar." />}
    <div className="table-caption"><span>Showing {total ? `${Math.min(offset + 1, total)}–${Math.min(offset + incidents.length, total)} of ${total.toLocaleString()}` : '0'} synthetic incidents</span><div className="page-controls"><button disabled={offset <= 0} onClick={() => onPage(Math.max(0, offset - pageSize))}>Previous</button><b>{total ? `${Math.floor(offset / pageSize) + 1} / ${Math.ceil(total / pageSize)}` : '—'}</b><button disabled={!total || offset + pageSize >= total} onClick={() => onPage(offset + pageSize)}>Next</button></div></div></section></div>;
}

function CaseReviewPage({ incident, analysis, loading, onGoGraph, onGoRecommendation }: { incident: Incident | null; analysis: Analysis | null; loading: boolean; onGoGraph: () => void; onGoRecommendation: () => void }) {
  const [tab, setTab] = useState<'overview' | 'evidence' | 'wallets'>('overview');
  if (!incident) return <EmptyState title="Choose an incident" text="Open a synthetic case from the incident register to begin the investigation." />;
  if (loading || !analysis) return <div className="panel loading-card"><div className="loading-spinner" /><h3>Preparing case replay</h3><p>Loading graph, taint and policy analysis from the local API…</p></div>;
  const recs = analysis.recommendation?.recommendations || [];
  const graphEdges = buildEdges(analysis);
  const reportedMove = analysis.taint?.movements?.find((move: Record<string, any>) => move.transaction_id === incident.reported_transaction_id);
  const model = analysis.model_predictions || {};
  return <div className="page-stack"><div className="case-hero"><div className="case-hero-main"><div className="case-hero-label"><span className="case-live-dot" /> REPORTED INCIDENT <span className="hero-divider">/</span> {titleCase(incident.incident_type)}</div><h2>{shortId(incident.incident_id)}</h2><p>Scenario {shortId(incident.scenario_id)} <i>·</i> reported {dateTime(incident.reported_at)} <i>·</i> {titleCase(incident.scenario_type)}</p></div><div className="case-hero-value"><span>REPORTED VALUE</span><b>{moneyExact(incident.reported_amount)}</b><small>{incident.reported_transaction_id}</small></div></div>
    <div className="case-tabs"><button className={tab === 'overview' ? 'current' : ''} onClick={() => setTab('overview')}>Overview</button><button className={tab === 'evidence' ? 'current' : ''} onClick={() => setTab('evidence')}>Evidence <span>{graphEdges.length}</span></button><button className={tab === 'wallets' ? 'current' : ''} onClick={() => setTab('wallets')}>Wallets <span>{analysis.taint.wallets.length}</span></button><div className="case-tab-actions"><button className="button button-light button-sm" onClick={onGoGraph}><Network size={14} /> Open graph</button><button className="button button-primary button-sm" onClick={onGoRecommendation}>Review recommendation <ArrowRight size={14} /></button></div></div>
    {tab === 'overview' && <div className="case-grid"><div className="case-main-column"><div className="mini-kpi-grid"><MiniMetric label="Risk score" value={recs[0]?.risk_score == null ? 'Unavailable' : pct(recs[0].risk_score)} sub={recs[0]?.risk_score == null ? 'No model score loaded' : 'Synthetic model estimate'} color="red" /><MiniMetric label="Remaining taint" value={money(analysis.taint.remaining_potentially_tainted_bdt)} sub="Proportional-flow estimate" color="amber" /><MiniMetric label="Downstream wallets" value={String(analysis.trace.downstream_wallet_ids?.length || 0)} sub={`Up to ${analysis.trace.limits?.hop_limit ?? '—'} hops`} color="blue" /></div>
        <section className="panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">FUND MOVEMENT</div><h2>Transaction graph</h2></div><button className="text-button" onClick={onGoGraph}>Explore graph <ArrowRight size={14} /></button></div><GraphCanvas analysis={analysis} incident={incident} edges={graphEdges} compact /></section>
        <section className="panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">INVESTIGATION TIMELINE</div><h2>What happened</h2></div></div><Timeline incident={incident} analysis={analysis} reportedMove={reportedMove} /></section></div>
      <div className="case-side-column"><section className="panel risk-panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">RISK EXPLANATION</div><h2>Why this case matters</h2></div><span className="info-dot" title="Synthetic decision-support indicators">i</span></div><div className="risk-status-line"><div className="risk-score-ring" style={{ '--ring': recs[0]?.risk_score == null ? 0 : Number(recs[0].risk_score) * 100 } as CSSProperties}><strong>{recs[0]?.risk_score == null ? '—' : pct(recs[0].risk_score)}</strong><span>MODEL</span></div><div><span className="risk-label">{recs[0]?.risk_score == null ? 'Score unavailable' : Number(recs[0].risk_score) >= .65 ? 'Elevated signal' : 'Below model threshold'}</span><small>{String(model.message || 'Risk is not model-assessed unless trained synthetic artifacts are available.')}</small></div></div><div className="signal-list"><Signal icon={Zap} title="Movement behavior" text={analysis.trace.rapid_forwards?.length ? `${analysis.trace.rapid_forwards.length} rapid-forward signal(s) observed` : 'No rapid-forward evidence in the trace window'} /><Signal icon={GitBranch} title="Wallet branching" text={analysis.trace.fanout_wallets?.length ? `${analysis.trace.fanout_wallets.length} branching wallet(s) observed` : 'No fan-out evidence in the trace window'} /><Signal icon={ArrowDownRight} title="Cash-out evidence" text={analysis.trace.cashouts?.length ? `${analysis.trace.cashouts.length} cash-out path(s) identified` : 'No cash-out observed within the trace window'} /></div><div className="caution-note"><Info size={14} /><span>Signals are evidence for review—not a finding of fraud or ownership.</span></div></section>
        <section className="panel taint-panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">TAINT ASSESSMENT</div><h2>Potential exposure</h2></div></div><div className="taint-total"><strong>{money(analysis.taint.remaining_potentially_tainted_bdt)}</strong><span>still attributed to digital wallets</span></div><div className="taint-breakdown"><div><span><i className="taint-dot dot-teal" /> In wallets</span><b>{money(analysis.taint.remaining_potentially_tainted_bdt)}</b></div><div><span><i className="taint-dot dot-red" /> Cash-out attributed</span><b>{money(analysis.taint.cashed_out_potentially_tainted_bdt)}</b></div><div><span><i className="taint-dot dot-gray" /> Unattributed</span><b>{money(analysis.taint.unattributed_bdt)}</b></div></div><small className="method-caption">Method: proportional balance attribution · observed as of {dateTime(analysis.as_of)}</small></section>
        <section className="next-move-card"><div className="next-move-top"><span className="next-move-icon"><Activity size={16} /></span><span className="next-move-label">NEXT-MOVE OUTLOOK</span></div>{recs[0]?.next_move_probabilities ? <div className="move-probs">{[['Forward', recs[0].next_move_probabilities.forward], ['Cash-out', recs[0].next_move_probabilities.cashout], ['No movement', recs[0].next_move_probabilities.no_movement]].map(([label, value]) => <div key={String(label)}><div><span>{label}</span><b>{pct(value)}</b></div><div className="move-bar"><i style={{ width: `${Number(value) * 100}%` }} /></div></div>)}</div> : <div className="unavailable-note">Prediction is not available for this scenario yet. Train synthetic models to enable it.</div>}<div className="next-move-foot"><Info size={13} /> Synthetic model signal · advisory only</div></section></div></div>}
    {tab === 'evidence' && <div className="case-evidence-grid"><section className="panel"><div className="panel-head"><div><div className="panel-eyebrow">TRACE EVIDENCE</div><h2>Observed movements</h2><p>Time-bounded graph edges with proportional attribution</p></div><span className="micro-tag">{graphEdges.length} EDGES</span></div><MovementTable edges={graphEdges} /></section><section className="panel"><div className="panel-head"><div><div className="panel-eyebrow">METHOD NOTES</div><h2>How to interpret</h2></div></div><div className="method-copy"><p><b>Reported transfer.</b> {shortId(incident.reported_transaction_id)} seeds the potentially tainted amount at the direct recipient.</p><p><b>Downstream attribution.</b> Later transfers move a proportional share of a wallet’s attributed balance; this is a bookkeeping assumption, not evidence of legal ownership.</p><p><b>Scope limits.</b> Tracing uses the selected synthetic scenario replay and the configured hop/time limits. Missing model artifacts mean predictions are not supplied.</p><p><b>Cash-out.</b> A cash-out edge ends a digital-wallet path and is reported separately from remaining digital value.</p></div></section></div>}
    {tab === 'wallets' && <WalletsPage wallets={analysis.taint.wallets} recommendations={recs} analysis={analysis} onReview={() => {}} />}
  </div>;
}

function MiniMetric({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) { return <div className={`mini-metric mini-${color}`}><span>{label}</span><strong>{value}</strong><small>{sub}</small></div>; }

function Timeline({ incident, analysis, reportedMove }: { incident: Incident; analysis: Analysis; reportedMove: Record<string, any> | undefined }) {
  const firstRecommendation = analysis.recommendation?.recommendations?.[0];
  const steps = [
    { time: incident.reported_at, title: 'Incident reported', note: `${money(incident.reported_amount)} transfer flagged for review`, state: 'done' },
    { time: reportedMove?.timestamp || incident.reported_at, title: 'Victim transfer identified', note: `${walletName(reportedMove?.from_wallet)} → ${walletName(reportedMove?.to_wallet)} · ${shortId(incident.reported_transaction_id)}`, state: 'done' },
    { time: analysis.as_of, title: 'Fund-flow replay completed', note: `${analysis.trace.downstream_wallet_ids?.length || 0} downstream wallet(s) · ${analysis.trace.paths?.length || 0} path(s) traced`, state: 'done' },
    { time: analysis.as_of, title: firstRecommendation ? 'Recommendation prepared' : 'Monitoring recommendation', note: firstRecommendation ? `${titleCase(firstRecommendation.action)} · analyst approval required` : 'No positive taint recommendation at the analysis point', state: 'current' },
  ];
  return <div className="timeline">{steps.map((step, index) => <div className={`timeline-item ${step.state}`} key={`${step.title}-${index}`}><div className="timeline-rail"><span className="timeline-point">{step.state === 'done' ? <Check size={11} /> : <span />}</span>{index < steps.length - 1 && <i />}</div><div className="timeline-content"><div className="timeline-top"><b>{step.title}</b><time>{dateTime(step.time)}</time></div><p>{step.note}</p></div></div>)}</div>;
}

function Signal({ icon: Icon, title, text }: { icon: typeof Activity; title: string; text: string }) { return <div className="signal-row"><span className="signal-icon"><Icon size={15} /></span><div><b>{title}</b><small>{text}</small></div><ChevronRight size={14} /></div>; }

function GraphPage({ incident, analysis, edges }: { incident: Incident | null; analysis: Analysis | null; edges: Edge[] }) {
  return <div className="page-stack"><section className="panel graph-page-panel"><div className="graph-page-heading"><div><div className="panel-eyebrow">NETWORK TRACE · {incident ? shortId(incident.incident_id) : 'NO CASE SELECTED'}</div><h2>Follow the flow</h2><p>Each edge shows gross transaction value; the sublabel shows estimated attributed value.</p></div><div className="graph-legend"><span><i className="legend-victim" /> Report source</span><span><i className="legend-wallet" /> Digital wallet</span><span><i className="legend-cash" /> Cash-out</span></div></div>{analysis ? <GraphCanvas analysis={analysis} incident={incident} edges={edges} /> : <LoadingInline text="Waiting for case analysis…" />}<div className="graph-foot"><span><Info size={14} /> Trace is limited to the configured time window and hop count.</span><span>{analysis?.trace?.limits?.hop_limit ?? '—'} max hops <i>·</i> {analysis?.trace?.limits?.time_window_minutes ?? '—'} min window</span></div></section>
    <div className="graph-detail-grid"><section className="panel"><div className="panel-head panel-head-tight"><div><div className="panel-eyebrow">EDGE REGISTER</div><h2>Transaction evidence</h2></div><span className="micro-tag">{edges.length} OBSERVED</span></div><MovementTable edges={edges} /></section><section className="panel graph-summary"><div className="panel-eyebrow">TRACE SUMMARY</div><div className="summary-stat"><span>Downstream wallets</span><b>{analysis?.trace?.downstream_wallet_ids?.length ?? '—'}</b></div><div className="summary-stat"><span>Unique paths</span><b>{analysis?.trace?.paths?.length ?? '—'}</b></div><div className="summary-stat"><span>Cash-out evidence</span><b>{analysis?.trace?.cashouts?.length ?? '—'}</b></div><div className="summary-stat"><span>Rapid forwards</span><b>{analysis?.trace?.rapid_forwards?.length ?? '—'}</b></div><div className="graph-summary-note">Gross edge amounts are not the same as estimated tainted value. Attribution is calculated separately.</div></section></div></div>;
}

function GraphCanvas({ analysis, incident, edges, compact = false }: { analysis: Analysis; incident: Incident | null; edges: Edge[]; compact?: boolean }) {
  if (!edges.length) return <div className={`graph-empty ${compact ? 'graph-empty-compact' : ''}`}><div><Network size={24} /><b>No downstream movement in this replay</b><span>The reported transfer is available, but no qualifying post-report edge was found inside the trace window.</span></div></div>;
  const list = edges.slice(0, compact ? 9 : 24);
  const root = list.find((edge) => edge.id === incident?.reported_transaction_id)?.from || list[0].from;
  const levels: Record<string, number> = { [root]: 0 };
  list.forEach((edge) => { if (levels[edge.from] == null) levels[edge.from] = 0; if (levels[edge.to] == null) levels[edge.to] = levels[edge.from] + 1; });
  const nodeIds = [...new Set(list.flatMap((edge) => [edge.from, edge.to]))];
  const maxLevel = Math.max(1, ...nodeIds.map((id) => levels[id] || 0));
  const width = 960;
  const height = Math.max(compact ? 270 : 370, ...Array.from({ length: maxLevel + 1 }, (_, level) => nodeIds.filter((id) => levels[id] === level).length * (compact ? 100 : 116) + 80));
  const byLevel: Record<number, string[]> = {};
  nodeIds.forEach((id) => { const level = levels[id] || 0; (byLevel[level] ||= []).push(id); });
  const points: Record<string, { x: number; y: number }> = {};
  Object.entries(byLevel).forEach(([levelString, ids]) => {
    const level = Number(levelString);
    ids.forEach((id, index) => { points[id] = { x: 84 + level * ((width - 168) / Math.max(1, maxLevel)), y: 54 + (height - 108) * (index + 1) / (ids.length + 1) }; });
  });
  return <div className={`graph-canvas-wrap ${compact ? 'compact' : ''}`}><svg className="graph-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Synthetic transaction graph for ${analysis.scenario_id}`}><defs><pattern id="graphGrid" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#e7eeec" /></pattern><marker id="arrowTeal" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#19a69b" /></marker><marker id="arrowRed" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#d26a61" /></marker></defs><rect width={width} height={height} fill="url(#graphGrid)" />
    {list.map((edge, index) => { const from = points[edge.from]; const to = points[edge.to]; if (!from || !to) return null; const dx = to.x - from.x; const curve = Math.max(28, Math.abs(dx) * .38); const path = `M ${from.x + 27} ${from.y} C ${from.x + curve} ${from.y}, ${to.x - curve} ${to.y}, ${to.x - 31} ${to.y}`; const midX = (from.x + to.x) / 2; const midY = (from.y + to.y) / 2 - (index % 2 ? 14 : -12); return <g key={edge.id}><title>{`${edge.id} · ${edge.type} · ${money(edge.amount)} gross · ${money(edge.taint)} attributed`}</title><path d={path} fill="none" stroke={edge.cashout ? '#d26a61' : '#19a69b'} strokeWidth={edge.cashout ? 2.7 : 2.2} strokeDasharray={edge.cashout ? '6 4' : undefined} markerEnd={edge.cashout ? 'url(#arrowRed)' : 'url(#arrowTeal)'} opacity=".78" /><g className="edge-label" transform={`translate(${midX},${midY})`}><rect x="-49" y="-18" width="98" height="36" rx="8" fill="#fff" stroke={edge.cashout ? '#f0c9c4' : '#d9e9e6'} /><text textAnchor="middle" y="-3" className="edge-amount">{money(edge.amount, true)}</text><text textAnchor="middle" y="10" className="edge-taint">taint {money(edge.taint, true)}</text></g></g>; })}
    {nodeIds.map((id) => { const point = points[id]; const isRoot = id === root; const isCash = list.some((edge) => edge.to === id && edge.cashout); const label = walletName(id); return <g key={id} className="graph-node"><title>{id}</title><circle cx={point.x} cy={point.y} r="27" fill={isCash ? '#fff2f0' : isRoot ? '#e3f3f0' : '#fff'} stroke={isCash ? '#d26a61' : isRoot ? '#167c73' : '#cbd9d6'} strokeWidth="2" /><text x={point.x} y={point.y + 4} textAnchor="middle" className="node-short">{label.length > 8 ? label.slice(0, 7) : label}</text><text x={point.x} y={point.y + 47} textAnchor="middle" className="node-kind">{isRoot ? 'REPORT SOURCE' : isCash ? 'CASH-OUT' : 'WALLET'}</text></g>; })}
    </svg></div>;
}

function MovementTable({ edges }: { edges: Edge[] }) {
  if (!edges.length) return <EmptyState title="No movement evidence" text="No edges were returned in this selected case trace." />;
  return <div className="movement-list">{edges.slice(0, 18).map((edge) => <div className="movement-row" key={edge.id}><div className={`movement-step ${edge.cashout ? 'cashout-step' : ''}`}>{edge.cashout ? <ArrowDownRight size={15} /> : <ArrowRight size={15} />}</div><div className="movement-route"><b>{walletName(edge.from)} <ArrowRight size={13} /> {walletName(edge.to)}</b><span className="mono">{shortId(edge.id)}</span></div><div className="movement-value"><b>{money(edge.amount)}</b><small>taint {money(edge.taint)}</small></div><div className="movement-time">{dateTime(edge.time)}</div><span className={`edge-type ${edge.cashout ? 'edge-cashout' : ''}`}>{edge.cashout ? 'Cash-out' : titleCase(edge.type)}</span></div>)}</div>;
}

function WalletsPage({ wallets, recommendations, analysis, onReview }: { wallets: WalletTaint[]; recommendations: WalletRecommendation[]; analysis: Analysis | null; onReview: (item: WalletRecommendation) => void }) {
  const [filter, setFilter] = useState('all');
  const recById = new Map(recommendations.map((item) => [item.wallet_id, item]));
  const visible = wallets.filter((wallet) => filter === 'all' || (filter === 'tainted' ? Number(wallet.potentially_tainted_bdt) > 0 : Number(recById.get(wallet.wallet_id)?.risk_score || 0) >= .65));
  return <div className="page-stack"><div className="wallet-intro"><div className="wallet-intro-icon"><WalletCards size={20} /></div><div><b>Wallets in selected replay</b><span>{analysis ? `${analysis.taint.wallets.length} digital wallets · ${shortId(analysis.scenario_id)}` : 'Select an incident to load wallet intelligence.'}</span></div><div className="wallet-method-chip"><Info size={13} /> Synthetic replay only</div></div><section className="panel wallet-panel"><div className="panel-head"><div><div className="panel-eyebrow">WALLET INTELLIGENCE</div><h2>Balances & attributed value</h2><p>Proportional taint is an estimate—not an ownership determination.</p></div><div className="filter-tools"><SlidersHorizontal size={16} /><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All wallets</option><option value="tainted">Potentially tainted</option><option value="risk">High model score</option></select></div></div><div className="table-wrap"><table className="data-table wallet-table"><thead><tr><th>Wallet</th><th>Type</th><th>Replay balance</th><th>Potential taint</th><th>Potentially legitimate</th><th>Taint ratio</th><th>Risk signal</th><th>Action</th></tr></thead><tbody>{visible.map((wallet) => { const rec = recById.get(wallet.wallet_id); return <tr key={wallet.wallet_id} id={`wallet-${wallet.wallet_id}`}><td><div className="wallet-ident"><span className="wallet-ident-icon"><WalletCards size={15} /></span><div><b>{walletName(wallet.wallet_id)}</b><small title={wallet.wallet_id}>{shortId(wallet.wallet_id)}</small></div></div></td><td><span className="type-label">{titleCase(wallet.customer_type)}</span></td><td className="amount-cell">{money(wallet.balance_bdt)}</td><td><div className="taint-cell"><b>{money(wallet.potentially_tainted_bdt)}</b><span className="tiny-progress"><i style={{ width: `${Math.min(100, Number(wallet.potentially_tainted_ratio) * 100)}%` }} /></span></div></td><td>{money(wallet.potentially_legitimate_bdt)}</td><td><span className="ratio-pill">{pct(wallet.potentially_tainted_ratio)}</span></td><td>{rec?.risk_score == null ? <span className="no-score">Not scored</span> : <span className={`risk-pill ${rec.risk_score >= .65 ? 'risk-high' : 'risk-low'}`}>{pct(rec.risk_score)}</span>}</td><td>{rec ? <button className="tiny-action" onClick={() => onReview(rec)}>Review <ChevronRight size={13} /></button> : <span className="no-score">—</span>}</td></tr>; })}</tbody></table></div>{visible.length === 0 && <EmptyState title="No wallets in this filter" text="Change the filter or select a different incident." />}<div className="table-caption"><span>{visible.length} of {wallets.length} wallets shown</span><span>Balances reflect analysis snapshot only</span></div></section><div className="wallet-caveat"><ShieldCheck size={16} /><span><b>Privacy and fairness note:</b> customer type is synthetic metadata. Do not use demographics as a decision criterion; rely on transaction evidence and human review.</span></div></div>;
}

function RecommendationsPage({ incident, analysis, recommendations, onDecide }: { incident: Incident | null; analysis: Analysis | null; recommendations: WalletRecommendation[]; onDecide: (item: WalletRecommendation, decision: 'approve' | 'reject' | 'modify') => void }) {
  const [selectedFilter, setSelectedFilter] = useState('all');
  const list = recommendations.filter((item) => selectedFilter === 'all' || item.urgency === selectedFilter || item.action === selectedFilter);
  return <div className="page-stack"><div className="recommendation-header"><div><div className="panel-eyebrow">HUMAN-IN-THE-LOOP DECISIONING</div><h2>{incident ? shortId(incident.incident_id) : 'Select a synthetic case'}</h2><p>Every suggestion is advisory. No action is executed automatically.</p></div><div className="recommendation-controls"><select value={selectedFilter} onChange={(event) => setSelectedFilter(event.target.value)}><option value="all">All recommendations</option><option value="urgent_review">Urgent review</option><option value="standard_review">Standard review</option><option value="propose_bounded_simulated_hold">Hold proposed</option><option value="monitor_and_review">Monitor & review</option></select></div></div>
    <div className="decision-callout"><span><ShieldCheck size={17} /></span><div><b>Analyst approval required</b><p>Approve, reject or modify the proposed <i>simulation</i> amount. Decisions are stored in the local audit database; they do not freeze or move real funds.</p></div><div className="callout-badge">NO AUTOMATIC EXECUTION</div></div>
    {analysis && <div className="recommendation-summary"><div><span>Policy version</span><b>{analysis.recommendation.policy_version || '—'}</b></div><div><span>Model status</span><b>{String(analysis.model_predictions?.source || 'Unavailable').replaceAll('_', ' ')}</b></div><div><span>Potential taint</span><b>{money(analysis.taint.remaining_potentially_tainted_bdt)}</b></div><div><span>Review queue</span><b>{recommendations.length} wallet proposals</b></div></div>}
    <div className="recommendation-list">{list.map((item) => <RecommendationCard key={item.wallet_id} item={item} onDecide={onDecide} />)}</div>{list.length === 0 && <div className="panel no-recommendations"><div className="no-rec-icon"><ShieldCheck size={23} /></div><h3>No wallet proposal available</h3><p>{analysis?.recommendation?.status === 'no_tainted_wallets_at_analysis_time' ? 'No potentially tainted digital balance was present at this analysis snapshot.' : 'No wallet meets the configured proposal criteria. Monitoring and analyst review remain available.'}</p><span>Absence of a proposal is not a finding that a transaction is legitimate.</span></div>}
    {analysis && <div className="policy-limitations"><Info size={15} /><div><b>Recommendation limitations</b><ul>{(analysis.recommendation.limitations || []).map((line: string) => <li key={line}>{line}</li>)}</ul></div></div>}</div>;
}

function RecommendationCard({ item, onDecide }: { item: WalletRecommendation; onDecide: (item: WalletRecommendation, decision: 'approve' | 'reject' | 'modify') => void }) {
  const score = item.risk_score;
  return <article className="panel recommendation-card"><div className="rec-card-top"><div className="wallet-ident"><span className="wallet-ident-icon"><WalletCards size={16} /></span><div><b>{walletName(item.wallet_id)}</b><small title={item.wallet_id}>{item.wallet_id}</small></div></div><span className={`urgency-tag ${item.urgency === 'urgent_review' ? 'urgent' : ''}`}><i />{titleCase(item.urgency)}</span></div>
    <div className="rec-core-grid"><div className="rec-main-amount"><span>PROPOSED SIMULATED HOLD</span><b>{moneyExact(item.proposed_simulated_hold_bdt)}</b><small>{item.action === 'propose_bounded_simulated_hold' ? 'Bounded by replay balance and policy cap' : 'No hold amount proposed · monitor & review'}</small></div><div className="rec-info"><span>Wallet balance</span><b>{money(item.balance_bdt)}</b><small>At analysis snapshot</small></div><div className="rec-info"><span>Potential taint</span><b>{money(item.potentially_tainted_bdt)}</b><small>Proportional-flow estimate</small></div><div className="rec-info"><span>Legitimate value at risk</span><b>{money(item.estimated_legitimate_value_affected_bdt)}</b><small>Estimated collateral impact</small></div></div>
    <div className="rec-signals"><div className="rec-risk"><span>Risk score</span>{score == null ? <b className="muted-score">Not available</b> : <><b className={score >= .65 ? 'text-danger' : 'text-success'}>{pct(score)}</b><div className="risk-progress"><i style={{ width: `${score * 100}%` }} /></div></>}</div><div className="rec-risk"><span>Likely cash-out</span><b>{item.next_move_probabilities ? pct(item.next_move_probabilities.cashout) : 'Not scored'}</b><small>Next-move estimate</small></div><div className="rec-risk"><span>Evidence references</span><b>{item.evidence_transaction_ids?.length || 0} transaction(s)</b><small>{item.evidence_transaction_ids?.slice(0, 2).map(shortId).join(', ') || 'No linked transaction IDs'}</small></div></div>
    <div className="rec-reasons"><div className="panel-eyebrow">WHY THIS WAS SUGGESTED</div><ul>{(item.reasons || []).slice(0, 4).map((reason) => <li key={reason}><span><Check size={12} /></span>{reason}</li>)}</ul></div>
    <div className="rec-actions"><button className="button button-primary" onClick={() => onDecide(item, 'approve')}><Check size={15} /> Approve simulation</button><button className="button button-light" onClick={() => onDecide(item, 'modify')}><SlidersHorizontal size={15} /> Modify amount</button><button className="button button-quiet-danger" onClick={() => onDecide(item, 'reject')}><X size={15} /> Reject</button></div>
  </article>;
}

function SimulatorPage({ incident, analysis, metrics }: { incident: Incident | null; analysis: Analysis | null; metrics: Metrics | null }) {
  const recommendation = analysis?.recommendation?.recommendations?.[0];
  const wallet = analysis?.taint?.wallets?.find((item) => item.wallet_id === recommendation?.wallet_id) || analysis?.taint?.wallets?.find((item) => Number(item.potentially_tainted_bdt) > 0);
  const max = Number(wallet?.balance_bdt || 0);
  const [amount, setAmount] = useState(0);
  useEffect(() => { setAmount(Math.min(Number(recommendation?.proposed_simulated_hold_bdt || 0), max)); }, [analysis?.scenario_id, recommendation?.wallet_id, recommendation?.proposed_simulated_hold_bdt, max]);
  const taint = Number(wallet?.potentially_tainted_bdt || 0);
  const preserved = Math.min(amount, taint);
  const collateral = Math.max(0, amount - preserved);
  const ratio = max > 0 ? Math.min(100, (amount / max) * 100) : 0;
  const benchmark = metrics?.end_to_end_evaluation?.results;
  const baseline = benchmark?.direct_recipient_only;
  const network = benchmark?.flowfreeze_network;
  return <div className="page-stack"><div className="simulator-intro"><div className="simulator-intro-icon"><FlaskConical size={21} /></div><div><div className="panel-eyebrow">SCENARIO LAB</div><h2>What if we intervene?</h2><p>Adjust a hypothetical hold amount and see the estimated trade-off for this synthetic replay.</p></div><span className="synthetic-chip"><span /> SIMULATED ONLY</span></div>
    <div className="simulator-grid"><section className="panel sim-controls"><div className="panel-head"><div><div className="panel-eyebrow">INTERVENTION INPUT</div><h2>Adjust the amount</h2><p>{incident ? `${shortId(incident.scenario_id)} · ${wallet ? walletName(wallet.wallet_id) : 'No tainted wallet selected'}` : 'Select a case to begin.'}</p></div><span className="edit-mark"><SlidersHorizontal size={16} /></span></div>
      {wallet ? <><div className="sim-amount-readout"><span>Proposed simulated amount</span><strong>{moneyExact(amount)}</strong></div><input className="amount-range" type="range" min="0" max={Math.max(max, 1)} step={100} value={Math.min(amount, max)} onChange={(event) => setAmount(Number(event.target.value))} style={{ '--range-progress': `${ratio}%` } as CSSProperties} /><div className="range-labels"><span>৳0</span><span>Available balance {money(max)}</span></div><label className="amount-input-label">Enter amount (BDT)<div className="amount-input"><span>৳</span><input type="number" min="0" max={max} value={amount} onChange={(event) => setAmount(Math.min(max, Math.max(0, Number(event.target.value))))} /></div></label><div className="sim-wallet-facts"><div><span>Potential taint</span><b>{money(taint)}</b></div><div><span>Potentially legitimate balance</span><b>{money(wallet.potentially_legitimate_bdt)}</b></div><div><span>Policy amount</span><b>{money(recommendation?.proposed_simulated_hold_bdt || 0)}</b></div></div></> : <EmptyState title="Wallet replay unavailable" text="Choose a case with a digital wallet replay to run a what-if estimate." />}
    </section>
    <section className="panel sim-outcome"><div className="panel-head"><div><div className="panel-eyebrow">ESTIMATED OUTCOME</div><h2>Value at this setting</h2><p>Purely illustrative arithmetic from the synthetic taint snapshot.</p></div><div className="outcome-icon"><CircleDollarSign size={18} /></div></div><div className="outcome-total"><span>Hypothetical amount</span><strong>{money(amount)}</strong><div className="outcome-bar"><i style={{ width: `${ratio}%` }} /></div></div><div className="outcome-split"><div className="outcome-row outcome-green"><span><i />Potentially tainted value preserved</span><b>{moneyExact(preserved)}</b></div><div className="outcome-row outcome-amber"><span><i />Potentially legitimate value affected</span><b>{moneyExact(collateral)}</b></div><div className="outcome-row outcome-gray"><span><i />Remaining potentially tainted value</span><b>{moneyExact(Math.max(0, taint - preserved))}</b></div></div><div className="outcome-caveat"><ShieldCheck size={15} /><span>Estimated preservation assumes the hypothetical proposal takes effect immediately. This is not observed prevented loss and does not change a wallet ledger.</span></div></section></div>
    <section className="panel baseline-panel"><div className="panel-head"><div><div className="panel-eyebrow">HELD-OUT BASELINE COMPARISON</div><h2>Direct recipient vs. network trace</h2><p>Precomputed experiment from the generated test split · not production performance.</p></div><span className="micro-tag">{benchmark?.scenario_cases || '—'} CASES</span></div>{baseline && network ? <><div className="baseline-metrics"><div className="baseline-measure"><span>Estimated tainted value preserved</span><div><div className="baseline-track"><i style={{ width: '50%' }} /></div><b>{money(baseline.estimated_tainted_value_preserved_bdt)}</b></div><div><div className="baseline-track track-network"><i style={{ width: '100%' }} /></div><b>{money(network.estimated_tainted_value_preserved_bdt)}</b></div></div><div className="baseline-legend"><span><i className="legend-baseline" />Direct-recipient-only baseline</span><span><i className="legend-network" />FlowFreeze network trace</span><span className="baseline-delta">+{money(benchmark?.network_minus_baseline?.estimated_tainted_value_preserved_bdt)} estimated</span></div></div><div className="baseline-footnote"><Info size={14} /> Assumes immediate hypothetical action; values are generator-label counterfactual estimates, not observed savings. Innocent value affected in network strategy: {money(network.estimated_legitimate_value_affected_bdt)}.</div></> : <div className="no-benchmark"><Info size={16} /><span>{metrics?.end_to_end_evaluation?.warning || 'No tracked baseline artifact is available from the API.'}</span></div>}</section>
  </div>;
}

function EvaluationPage({ metrics }: { metrics: Metrics | null }) {
  const result = metrics?.end_to_end_evaluation?.results;
  const baseline = result?.direct_recipient_only;
  const network = result?.flowfreeze_network;
  const fraud = metrics?.ml_evaluation?.held_out_test?.fraud;
  const next = metrics?.ml_evaluation?.held_out_test?.next_move;
  return <div className="page-stack"><div className="evaluation-banner"><div className="evaluation-banner-icon"><Gauge size={20} /></div><div><div className="panel-eyebrow">EVIDENCE, NOT A PROMISE</div><h2>How did the synthetic experiment perform?</h2><p>Evaluation data is tied to a held-out synthetic scenario split. It should not be read as a measure of upay BD performance.</p></div></div>
    <div className="evaluation-kpis"><div className="evaluation-kpi"><span>Held-out cases</span><b>{result?.scenario_cases?.toLocaleString?.() || metrics?.ml_evaluation?.held_out_test?.scenario_cases || '—'}</b><small>Same test set for both strategies</small></div><div className="evaluation-kpi"><span>Median analysis time</span><b>{result?.timing?.median_recommendation_ms ? `${Number(result.timing.median_recommendation_ms).toFixed(0)} ms` : '—'}</b><small>Local CPU wall time · excludes startup</small></div><div className="evaluation-kpi"><span>Downstream wallets found</span><b>{result?.tracing?.total_downstream_wallets_found ?? '—'}</b><small>{result?.tracing?.ground_truth_tainted_downstream_wallets_found ?? '—'} labeled tainted in generator</small></div><div className="evaluation-kpi"><span>Model artifacts</span><b>{metrics?.ml_evaluation?.artifact_available ? 'Available' : 'Not loaded'}</b><small>{metrics?.ml_evaluation?.synthetic_only ? 'Synthetic-only evaluation' : 'Unavailable'}</small></div></div>
    <section className="panel comparison-panel"><div className="panel-head"><div><div className="panel-eyebrow">SAME CASES · SAME ASSUMPTIONS</div><h2>Containment estimate comparison</h2><p>Baseline can propose only for the direct recipient; FlowFreeze can consider positively attributed downstream wallets.</p></div><span className="benchmark-badge">{result?.split ? `${titleCase(result.split)} split` : 'Synthetic benchmark'}</span></div>{baseline && network ? <div className="comparison-cards"><ComparisonCard label="Direct-recipient-only" tone="baseline" caseRate={baseline.case_proposal_rate} proposed={baseline.proposed_hold_bdt} preserved={baseline.estimated_tainted_value_preserved_bdt} affected={baseline.estimated_legitimate_value_affected_bdt} wallets={baseline.wallets_with_proposal} cases={baseline.case_count} /><div className="comparison-vs">VS</div><ComparisonCard label="FlowFreeze network trace" tone="network" caseRate={network.case_proposal_rate} proposed={network.proposed_hold_bdt} preserved={network.estimated_tainted_value_preserved_bdt} affected={network.estimated_legitimate_value_affected_bdt} wallets={network.wallets_with_proposal} cases={network.case_count} /></div> : <EmptyState title="Baseline artifact unavailable" text={metrics?.end_to_end_evaluation?.warning || 'Tracked end-to-end metrics are not available.'} />}
    {baseline && network && <div className="comparison-delta"><div><ArrowUpRight size={17} /><span>Additional estimated tainted value preserved</span><b>{money(result?.network_minus_baseline?.estimated_tainted_value_preserved_bdt)}</b></div><div><AlertTriangle size={17} /><span>Additional legitimate value affected</span><b>{money(result?.network_minus_baseline?.estimated_legitimate_value_affected_bdt)}</b></div><div><Network size={17} /><span>Average downstream wallets per case</span><b>{result?.tracing?.average_downstream_wallets_found_per_case ?? '—'}</b></div></div>}
    <div className="comparison-caveat"><Info size={15} /><span>{result?.limitation || metrics?.warning || 'Synthetic counterfactual estimates; not observed losses prevented, customer outcomes, or upay BD production statistics.'}</span></div></section>
    <section className="panel model-evaluation-panel"><div className="panel-head"><div><div className="panel-eyebrow">MODEL QUALITY SNAPSHOT</div><h2>Held-out model diagnostics</h2><p>Generated labels can be easier than real-world fraud; class balance and drift matter.</p></div></div>{fraud || next ? <div className="model-score-grid"><div className="model-score-card"><div><ShieldAlert size={16} /> Fraud model</div><ScoreMeter label="Precision" value={fraud?.precision} /><ScoreMeter label="Recall" value={fraud?.recall} /><ScoreMeter label="F1" value={fraud?.f1} /><ScoreMeter label="PR-AUC" value={fraud?.pr_auc_average_precision} /></div><div className="model-score-card"><div><Activity size={16} /> Next-move model</div><ScoreMeter label="Accuracy" value={next?.accuracy} /><ScoreMeter label="Macro F1" value={next?.f1_macro} /><ScoreMeter label="Macro PR-AUC" value={next?.pr_auc_macro_ovr} /><ScoreMeter label="Brier score" value={next?.brier_score_multiclass} inverse /></div></div> : <EmptyState title="Model artifacts not loaded" text={String(metrics?.ml_evaluation?.warning || 'Train the synthetic models to produce scores for individual cases.')} />}<div className="model-eval-caveat"><AlertTriangle size={15} /><span>These diagnostics are based on synthetic generated labels. A high score does not establish real-world accuracy, fairness, or fitness for operational use.</span></div></section>
  </div>;
}

function ShadowModePage({ shadow }: { shadow: ShadowImpact | null }) {
  if (!shadow) return <div className="panel impact-empty"><Info size={18} /><span>Shadow-mode simulation unavailable. Ensure the backend and generated data are available.</span></div>;
  const ff = shadow.flowfreeze_shadow, human = shadow.feedback_summary;
  return <div className="page-stack shadow-page">
    <div className="shadow-banner"><ShieldCheck size={20} /><div><b>SHADOW MODE — PILOT READINESS</b><span>{shadow.pilot_label} · Recommendations are record-only; no operational decision is changed.</span></div><strong>NO FINANCIAL ACTIONS</strong></div>
    <div className="impact-kpis shadow-kpis">
      <div className="impact-kpi"><span>CASES EVALUATED</span><b>{shadow.cases_evaluated.toLocaleString()}</b><small>Synthetic records only</small></div>
      <div className="impact-kpi"><span>FLOWFREEZE RECOMMENDATIONS</span><b>{Number(ff.recommendations).toLocaleString()}</b><small>Would prioritize for analyst review</small></div>
      <div className="impact-kpi"><span>ANALYST AGREEMENT</span><b>{human.analyst_agreement_rate == null ? 'Not measured' : pct(human.analyst_agreement_rate)}</b><small>{Number(human.feedback_records || 0)} feedback record(s)</small></div>
      <div className="impact-kpi"><span>ANALYST OVERRIDE</span><b>{human.override_rate == null ? 'Not measured' : pct(human.override_rate)}</b><small>Based on audited demo decisions</small></div>
      <div className="impact-kpi"><span>POTENTIAL EXPOSURE IDENTIFIED</span><b>{money(ff.estimated_exposure_identified_bdt, true)}</b><small>Generated labels; not recoverable funds</small></div>
      <div className="impact-kpi"><span>ESTIMATED TIME SAVED</span><b>{Number(shadow.investigation.estimated_time_saved_minutes).toLocaleString()} min</b><small>Synthetic workload model, not analyst-measured: FlowFreeze {Number(shadow.investigation.synthetic_analyst_workload_minutes).toLocaleString()} min</small></div>
      <div className="impact-kpi"><span>FALSE POSITIVES</span><b>{Number(ff.false_positives).toLocaleString()}</b><small>Against generated labels</small></div>
      <div className="impact-kpi"><span>FALSE NEGATIVES</span><b>{Number(ff.false_negatives).toLocaleString()}</b><small>Against generated labels</small></div>
    </div>
    <section className="panel shadow-compare"><div className="panel-head"><div><div className="panel-eyebrow">INDEPENDENT COMPARISON · SYNTHETIC</div><h2>Current process vs FlowFreeze shadow output</h2><p>Neither comparator represents a real operator or a deployed model.</p></div><span className="micro-tag">{shadow.cases_evaluated.toLocaleString()} CASES</span></div><div className="shadow-columns"><div><h3>Current-process proxy</h3><p>{shadow.current_process.description}</p><b>{Number(shadow.current_process.recommendations).toLocaleString()}</b><small>synthetic priorities</small></div><div><h3>FlowFreeze shadow</h3><p>{shadow.flowfreeze_shadow.description}</p><b>{Number(ff.recommendations).toLocaleString()}</b><small>record-only recommendations</small></div><div><h3>Detection proxy</h3><p>Measured against synthetic generator labels, not real fraud outcomes.</p><b>{pct(ff.precision)} / {pct(ff.recall)}</b><small>precision / recall · PR-AUC {ff.pr_auc_average_precision == null ? 'N/A' : pct(ff.pr_auc_average_precision)}</small></div></div></section>
    <div className="impact-lower-grid"><section className="panel impact-harm"><div className="panel-head"><div><div className="panel-eyebrow">HUMAN FEEDBACK</div><h2>Analyst feedback summary</h2><p>Only recorded demo feedback is included.</p></div></div><div className="impact-harm-rows"><div><span>Recommendation helpful rate</span><b>{human.recommendation_helpful_rate == null ? 'Not measured' : pct(human.recommendation_helpful_rate)}</b></div><div><span>Useful · yes / partially / no</span><b>{human.usefulness_counts ? `${human.usefulness_counts.yes} / ${human.usefulness_counts.partially} / ${human.usefulness_counts.no}` : '0 / 0 / 0'}</b></div><div><span>Trace · accurate / partial / inaccurate</span><b>{human.trace_accuracy_counts ? `${human.trace_accuracy_counts.accurate} / ${human.trace_accuracy_counts.partially_accurate} / ${human.trace_accuracy_counts.inaccurate}` : '0 / 0 / 0'}</b></div><div><span>Confidence · low / medium / high</span><b>{human.confidence_counts ? `${human.confidence_counts.low} / ${human.confidence_counts.medium} / ${human.confidence_counts.high}` : '0 / 0 / 0'}</b></div></div></section>
      <section className="panel impact-productivity"><div className="panel-head"><div><div className="panel-eyebrow">CUSTOMER-HARM INDICATORS</div><h2>Synthetic only</h2><p>Not customer impact measurements</p></div></div><div className="impact-harm-rows"><div><span>Unnecessary intervention rate</span><b>{pct(shadow.business.unnecessary_intervention_rate)}</b></div><div><span>Legitimate value affected</span><b>{money(shadow.business.legitimate_value_affected_bdt)}</b></div><div><span>Simulated prevented exposure</span><b>{money(shadow.business.simulated_prevented_exposure_bdt)}</b></div><div><span>Financial actions executed</span><b>{shadow.financial_actions_executed}</b></div></div></section></div>
    <details className="panel impact-method"><summary>Safety, limitations & partner-agreed targets</summary><div>All success thresholds are labeled <b>{shadow.business_success_targets.status}</b>; none are represented as achieved. Edit <code>core/pilot_targets.json</code> with a partner-approved value when agreed.</div><div className="target-list">{Object.entries(shadow.business_success_targets.targets || {}).map(([key, item]: [string, any]) => <div key={key}><span>{titleCase(key.replaceAll('_', ' '))}</span><b>{item.target == null ? 'Not agreed' : item.target} · {item.unit}</b></div>)}</div><ul>{shadow.assumptions.map((item: string) => <li key={item}>{item}</li>)}</ul><ul>{shadow.limitations.map((item: string) => <li key={item}>{item}</li>)}</ul><span>See docs/PILOT_PLAN.md for the staged partner pilot plan.</span></details>
  </div>;
}

function BusinessImpactPage({ impact }: { impact: BusinessImpact | null }) {
  if (!impact) return <div className="panel impact-empty"><Info size={18} /><span>Business impact simulation is unavailable. Start the backend and ensure generated synthetic CSV data is present.</span></div>;
  const loss = impact.fraud_loss;
  const efficiency = impact.investigation_efficiency;
  const harm = impact.customer_harm;
  const comparison = impact.baseline_vs_flowfreeze;
  return <div className="page-stack business-impact-page">
    <div className="impact-warning"><FlaskConical size={18} /><div><b>{impact.label}</b><span>Every result is synthetic. This is not measured MFS performance, actual loss avoided, or observed customer harm.</span></div><strong>{impact.case_count.toLocaleString()} CASES</strong></div>
    <div className="impact-kpis">
      <div className="impact-kpi"><span>POTENTIAL EXPOSURE IDENTIFIED</span><b>{money(comparison.flowfreeze_exposure_identified_bdt, true)}</b><small>Generated taint labels found through observed downstream tracing</small></div>
      <div className="impact-kpi"><span>SIMULATED PREVENTED EXPOSURE</span><b>{money(loss.simulated_prevented_exposure_bdt, true)}</b><small>Counterfactual, not actual prevented loss</small></div>
      <div className="impact-kpi"><span>INVESTIGATION TIME SAVED</span><b>{Number(efficiency.investigation_time_saved_minutes).toLocaleString()} min</b><small>Synthetic manual-timing model</small></div>
      <div className="impact-kpi"><span>LEGITIMATE VALUE PROTECTED</span><b>{money(Math.max(0, Number(harm.overly_aggressive_policy_legitimate_value_affected_bdt) - Number(harm.flowfreeze_legitimate_value_affected_bdt)), true)}</b><small>Compared with overly aggressive simulated policy</small></div>
    </div>
    <section className="panel impact-compare"><div className="panel-head"><div><div className="panel-eyebrow">SAME GENERATED CASES · COUNTERFACTUAL COMPARISON</div><h2>Baseline vs FlowFreeze</h2><p>Direct-recipient-only manual discovery compared with observed-flow multihop tracing.</p></div><span className="micro-tag">{impact.case_count.toLocaleString()} SYNTHETIC CASES</span></div>
      <div className="impact-compare-grid"><div><span>Potential exposure identified</span><div><small>Baseline</small><b>{money(comparison.baseline_exposure_identified_bdt, true)}</b></div><div><small>FlowFreeze</small><b>{money(comparison.flowfreeze_exposure_identified_bdt, true)}</b></div></div><div><span>Modeled investigation time</span><div><small>Baseline</small><b>{Number(comparison.baseline_time_minutes).toLocaleString()} min</b></div><div><small>FlowFreeze</small><b>{Number(comparison.flowfreeze_time_minutes).toLocaleString()} min</b></div></div><div><span>Simulated prevented exposure</span><div><small>Baseline</small><b>{money(loss.baseline_simulated_prevented_exposure_bdt, true)}</b></div><div><small>FlowFreeze</small><b>{money(loss.simulated_prevented_exposure_bdt, true)}</b></div></div></div>
      <div className="impact-formula"><Info size={14} /> Simulated loss-reduction rate: {pct(loss.simulated_loss_reduction_rate)} = simulated prevented exposure ÷ initial suspicious value. It is a synthetic ratio, not an actual loss-reduction claim.</div>
    </section>
    <div className="impact-lower-grid"><section className="panel impact-harm"><div className="panel-head"><div><div className="panel-eyebrow">CUSTOMER HARM</div><h2>Unnecessary intervention rate</h2><p>Synthetic policy comparison only</p></div><span className="harm-rate">{pct(harm.unnecessary_intervention_rate)}</span></div><div className="impact-harm-rows"><div><span>Overly aggressive-policy unnecessary holds</span><b>{Number(harm.overly_aggressive_policy_unnecessary_holds).toLocaleString()}</b></div><div><span>FlowFreeze-proxy unnecessary holds</span><b>{Number(harm.flowfreeze_unnecessary_holds).toLocaleString()}</b></div><div><span>Legitimate value affected · aggressive</span><b>{money(harm.overly_aggressive_policy_legitimate_value_affected_bdt)}</b></div><div><span>Legitimate value affected · FlowFreeze proxy</span><b>{money(harm.flowfreeze_legitimate_value_affected_bdt)}</b></div><div><span>Legitimate cases correctly left alone</span><b>{Number(harm.legitimate_cases_correctly_left_alone).toLocaleString()}</b></div></div><div className="impact-caveat">The FlowFreeze proxy bounds interventions to generated taint labels, so modeled collateral is zero by construction. This is not evidence of real-world false-positive or customer-harm reduction.</div></section>
      <section className="panel impact-productivity"><div className="panel-head"><div><div className="panel-eyebrow">ANALYST PRODUCTIVITY</div><h2>Operational simulation</h2><p>Illustrative assumptions, not analyst trial timings</p></div></div><div className="impact-harm-rows"><div><span>Baseline modeled cases/hour</span><b>{efficiency.baseline_minutes_per_case ? (60 / Number(efficiency.baseline_minutes_per_case)).toFixed(1) : '—'}</b></div><div><span>FlowFreeze modeled cases/hour</span><b>{efficiency.flowfreeze_minutes_per_case ? (60 / Number(efficiency.flowfreeze_minutes_per_case)).toFixed(1) : '—'}</b></div><div><span>Downstream wallets identified</span><b>{Number(efficiency.downstream_wallets_identified).toLocaleString()}</b></div><div><span>Transactions reviewed · baseline / FlowFreeze</span><b>{Number(efficiency.transactions_reviewed_baseline).toLocaleString()} / {Number(efficiency.transactions_reviewed_flowfreeze).toLocaleString()}</b></div><div><span>Modeled alerts prioritized</span><b>{Number(impact.analyst_productivity.alerts_prioritized).toLocaleString()}</b></div></div></section></div>
    <details className="panel impact-method"><summary>Assumptions, limitations & future validation targets</summary><div><b>Timing assumption:</b> 4 min case intake + 1.5 min per reviewed transaction + 0.75 min per reviewed wallet.</div><ul>{impact.assumptions.map((item) => <li key={item}>{item}</li>)}</ul><ul>{impact.limitations.map((item) => <li key={item}>{item}</li>)}</ul><b>{String(impact.validation_targets.status || '')}</b></details>
  </div>;
}

function ComparisonCard({ label, tone, caseRate, proposed, preserved, affected, wallets, cases }: { label: string; tone: string; caseRate: number; proposed: string; preserved: string; affected: string; wallets: number; cases: number }) {
  return <div className={`comparison-card comparison-${tone}`}><div className="comparison-card-head"><span className="comparison-mark">{tone === 'network' ? <Network size={17} /> : <WalletCards size={17} />}</span><div><b>{label}</b><small>{cases} held-out cases</small></div><span className="proposal-rate">{pct(caseRate)}<small>proposal rate</small></span></div><div className="comparison-value"><span>Estimated tainted value preserved</span><b>{money(preserved)}</b></div><div className="comparison-subrow"><span>Proposed simulated value <b>{money(proposed)}</b></span><span>Legitimate value affected <b>{money(affected)}</b></span><span>Wallets with proposal <b>{wallets}</b></span></div></div>;
}
function ScoreMeter({ label, value, inverse = false }: { label: string; value?: number; inverse?: boolean }) { const num = Number(value); const display = Number.isFinite(num) ? (num * 100).toFixed(1) : '—'; return <div className="score-meter"><div><span>{label}</span><b>{display}{display !== '—' ? '%' : ''}</b></div><div className="score-track"><i className={inverse ? 'inverse' : ''} style={{ width: `${Number.isFinite(num) ? Math.max(0, Math.min(100, num * 100)) : 0}%` }} /></div></div>; }

function AuditPage({ decisions, onOpen }: { decisions: DecisionRecord[]; onOpen: (incident: Incident) => void }) {
  return <div className="page-stack"><section className="panel audit-panel"><div className="panel-head"><div><div className="panel-eyebrow">APPEND-ONLY DECISION LOG</div><h2>Analyst audit history</h2><p>Decision records from the local synthetic SQLite database. No underlying wallet balances are changed.</p></div><span className="micro-tag">{decisions.length} RECORDS LOADED</span></div>{decisions.length ? <div className="table-wrap"><table className="data-table audit-table"><thead><tr><th>Decision</th><th>Case / scenario</th><th>Wallet</th><th>Simulated amount</th><th>Analyst</th><th>Recorded</th><th>Reason</th></tr></thead><tbody>{decisions.map((decision) => <tr key={decision.decision_id}><td><span className={`decision-tag decision-${decision.decision}`}>{decision.decision === 'approve' ? <Check size={12} /> : decision.decision === 'reject' ? <X size={12} /> : <SlidersHorizontal size={12} />}{titleCase(decision.decision)}</span></td><td><button className="audit-case-link" onClick={() => onOpen({ incident_id: decision.incident_id, scenario_id: decision.scenario_id } as Incident)}>{shortId(decision.incident_id)}<small>{shortId(decision.scenario_id)}</small></button></td><td className="mono">{shortId(decision.wallet_id)}</td><td className="amount-cell">{money(decision.proposed_amount_bdt)}</td><td>{decision.actor}</td><td>{dateTime(decision.created_at)}</td><td className="reason-cell" title={decision.reason}>{decision.reason}</td></tr>)}</tbody></table></div> : <div className="audit-empty"><div className="audit-empty-icon"><History size={21} /></div><h3>No decisions recorded yet</h3><p>Once an analyst approves, rejects or modifies a recommendation, the decision will appear here.</p><span>Writes are governed by the backend demo-write configuration.</span></div>}<div className="audit-foot"><ShieldCheck size={14} /> These records document synthetic analyst decisions; they are not regulatory records.</div></section></div>;
}

function DecisionModal({ draft, analyst, onClose, onSubmit }: { draft: NonNullable<DecisionDraft>; analyst: string; onClose: () => void; onSubmit: (decision: 'approve' | 'reject' | 'modify', item: WalletRecommendation, amount: number, reason: string, feedback: FeedbackInput) => void }) {
  const { recommendation } = draft;
  const [decision, setDecision] = useState(draft.decision);
  const max = Number(recommendation.balance_bdt || 0);
  const recommended = Number(recommendation.proposed_simulated_hold_bdt || 0);
  const [amount, setAmount] = useState(Math.min(max, recommended || Math.min(Number(recommendation.potentially_tainted_bdt || 1000), 10000)));
  const rationaleFor = (choice: 'approve' | 'reject' | 'modify') => choice === 'reject' ? 'Recommendation reviewed; no simulated hold approved.' : choice === 'modify' ? 'Modified simulated amount for further analyst review.' : 'Approved for synthetic outcome simulation, subject to analyst review.';
  const [reason, setReason] = useState(rationaleFor(draft.decision));
  const [wasUseful, setWasUseful] = useState<FeedbackInput['was_useful'] | ''>('');
  const [recommendationFeedback, setRecommendationFeedback] = useState<FeedbackInput['recommendation_feedback'] | ''>('');
  const [traceAccuracy, setTraceAccuracy] = useState<FeedbackInput['trace_accuracy'] | ''>('');
  const [confidence, setConfidence] = useState<FeedbackInput['confidence'] | ''>('');
  const [feedbackReason, setFeedbackReason] = useState('');
  const [reasonEdited, setReasonEdited] = useState(false);
  const chooseDecision = (choice: 'approve' | 'reject' | 'modify') => {
    setDecision(choice);
    if (!reasonEdited) setReason(rationaleFor(choice));
  };
  const disabled = reason.trim().length < 3 || !wasUseful || !recommendationFeedback || !traceAccuracy || !confidence || (decision !== 'reject' && (amount <= 0 || amount > max));
  return <div className="modal-backdrop" role="presentation" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="decision-modal" role="dialog" aria-modal="true" aria-labelledby="decision-title"><div className="modal-head"><div><div className="panel-eyebrow">ANALYST DECISION · SYNTHETIC</div><h2 id="decision-title">Review this proposal</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X size={18} /></button></div><div className="modal-wallet"><span className="wallet-ident-icon"><WalletCards size={16} /></span><div><b>{walletName(recommendation.wallet_id)}</b><small>{recommendation.wallet_id}</small></div><div className="modal-taint"><span>Potential taint</span><b>{money(recommendation.potentially_tainted_bdt)}</b></div></div><div className="modal-proposal"><div><span>Policy recommendation</span><b>{money(recommendation.proposed_simulated_hold_bdt)}</b></div><div><span>Wallet replay balance</span><b>{money(recommendation.balance_bdt)}</b></div><div><span>Estimated legitimate impact</span><b>{money(recommendation.estimated_legitimate_value_affected_bdt)}</b></div></div><div className="decision-choice"><span className="form-label">Decision</span><div className="choice-buttons"><button className={decision === 'approve' ? 'choice-active choice-approve' : ''} onClick={() => chooseDecision('approve')}><Check size={14} /> Approve</button><button className={decision === 'modify' ? 'choice-active choice-modify' : ''} onClick={() => chooseDecision('modify')}><SlidersHorizontal size={14} /> Modify</button><button className={decision === 'reject' ? 'choice-active choice-reject' : ''} onClick={() => chooseDecision('reject')}><X size={14} /> Reject</button></div></div>{decision !== 'reject' && <label className="form-label">Simulated amount (BDT)<div className="amount-input modal-amount"><span>৳</span><input type="number" min="0.01" max={max} step="0.01" value={amount} onChange={(event) => setAmount(Math.min(max, Number(event.target.value)))} /></div><small className="field-hint">Prototype-only hypothetical amount. No hold is executed.</small></label>}<label className="form-label">Decision rationale<textarea rows={2} value={reason} onChange={(event) => { setReasonEdited(true); setReason(event.target.value); }} maxLength={1000} /></label><div className="feedback-inputs"><b>Was FlowFreeze useful?</b><div className="feedback-grid"><label>Useful<select required value={wasUseful} onChange={(e) => setWasUseful(e.target.value as FeedbackInput['was_useful'] | '')}><option value="" disabled>Choose</option><option value="yes">Yes</option><option value="partially">Partially</option><option value="no">No</option></select></label><label>Recommendation<select required value={recommendationFeedback} onChange={(e) => setRecommendationFeedback(e.target.value as FeedbackInput['recommendation_feedback'] | '')}><option value="" disabled>Choose</option><option value="helpful">Helpful</option><option value="not_helpful">Not helpful</option></select></label><label>Trace<select required value={traceAccuracy} onChange={(e) => setTraceAccuracy(e.target.value as FeedbackInput['trace_accuracy'] | '')}><option value="" disabled>Choose</option><option value="accurate">Accurate</option><option value="partially_accurate">Partially accurate</option><option value="inaccurate">Inaccurate</option></select></label><label>Confidence<select required value={confidence} onChange={(e) => setConfidence(e.target.value as FeedbackInput['confidence'] | '')}><option value="" disabled>Choose</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label></div><label>Feedback reason<textarea rows={2} value={feedbackReason} maxLength={1000} onChange={(e) => setFeedbackReason(e.target.value)} placeholder="Optional: briefly explain your assessment" /></label></div><div className="decision-impact-note"><ShieldCheck size={15} /><span>Decision and feedback are separately recorded in an append-only synthetic audit log. No wallet action is executed.</span></div><div className="modal-footer"><span>Recorded as <b>{analyst}</b></span><button className="button button-light" onClick={onClose}>Cancel</button><button className={`button ${decision === 'reject' ? 'button-danger' : 'button-primary'}`} onClick={() => onSubmit(decision, recommendation, amount, reason, { was_useful: wasUseful as FeedbackInput['was_useful'], recommendation_feedback: recommendationFeedback as FeedbackInput['recommendation_feedback'], trace_accuracy: traceAccuracy as FeedbackInput['trace_accuracy'], confidence: confidence as FeedbackInput['confidence'], reason: feedbackReason })} disabled={disabled}>{decision === 'reject' ? 'Record rejection' : decision === 'modify' ? 'Record modified proposal' : 'Approve simulation'} <ArrowRight size={15} /></button></div></div></div>;
}

function LoadingInline({ text }: { text: string }) { return <div className="loading-inline"><div className="loading-spinner small-spinner" />{text}</div>; }
function EmptyState({ title, text }: { title: string; text: string }) { return <div className="empty-state"><div className="empty-state-icon"><Info size={18} /></div><b>{title}</b><span>{text}</span></div>; }

export default App;
