import { formatDate, formatMoney } from '../api.js'

export default function EvidencePanel({ trace, taint }) {
  const evidence = [
    ...(trace?.cashouts || []).map((item) => ({ kind: 'Cash-out', id: item.transaction_id, detail: `${item.wallet_id} → cash destination · ${formatMoney(item.amount_bdt)}`, time: item.timestamp, tone: 'cash' })),
    ...(trace?.rapid_forwards || []).map((item) => ({ kind: 'Rapid forwarding', id: item.outgoing_transaction_id, detail: `${item.wallet_id} forwarded in ${item.elapsed_seconds}s`, time: item.sent_at, tone: 'rapid' })),
    ...(trace?.fanout_wallets || []).map((item) => ({ kind: 'Fan-out', id: item.wallet_id, detail: `${item.recipient_wallets.length} distinct recipients`, time: null, tone: 'fanout' })),
  ]
  return <section className="content-card evidence-card"><div className="section-head"><div><div className="eyebrow">OBSERVED SIGNALS</div><h2>Evidence & limits</h2></div><span className="count-badge">{evidence.length}</span></div>
    {evidence.length ? <div className="evidence-list">{evidence.slice(0, 8).map((item, i) => <div className="evidence-item" key={`${item.id}-${i}`}><span className={`evidence-marker ${item.tone}`}>{item.tone === 'cash' ? '৳' : item.tone === 'rapid' ? '↗' : '⌁'}</span><div><b>{item.kind}</b><span>{item.detail}</span><small>{item.id}{item.time ? ` · ${formatDate(item.time)}` : ''}</small></div></div>)}</div> : <div className="no-evidence"><span>✓</span><div><b>No rapid forward or cash-out observed</b><small>Absence in this snapshot does not prove no future movement.</small></div></div>}
    <div className="limits-box"><b>Trace limits</b><span>{trace?.limits?.hop_limit ?? '—'} hops · {trace?.limits?.time_window_minutes ?? '—'} minutes · {trace?.limits?.truncated ? 'Results truncated' : 'Within path limit'}</span><small>Estimated unallocated: {formatMoney(taint?.unattributed_bdt)}</small></div>
  </section>
}
