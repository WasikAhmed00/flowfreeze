import IncidentDetail from './IncidentDetail.jsx'

export default function Simulator({ incidents, scenarioId, onSelect, onRefresh }) {
  return <>
    <div className="page-heading"><div><div className="eyebrow">WHAT-IF LAB <span className="eyebrow-dot" /> SYNTHETIC ONLY</div><h1>Explore a response</h1><p>Choose a seeded scenario, review the observed flow, and record a simulated supervisor decision.</p></div></div>
    <section className="content-card simulator-picker"><label htmlFor="scenario-picker">DEMO SCENARIO</label><select id="scenario-picker" value={scenarioId} onChange={(event) => onSelect(event.target.value)}>{incidents.map((item) => <option key={item.scenario_id} value={item.scenario_id}>{item.scenario_type.replaceAll('_', ' ')} · {item.scenario_id}</option>)}</select><span>Simulation estimates do not alter balances.</span></section>
    <IncidentDetail scenarioId={scenarioId} incident={incidents.find((item) => item.scenario_id === scenarioId)} onRefresh={onRefresh} />
  </>
}
