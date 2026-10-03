const short = (value = '') => value.length > 17 ? `${value.slice(-13)}` : value

export default function TransactionGraph({ trace, onWallet, selectedWallet }) {
  const paths = trace?.paths || []
  const nodeIds = [...new Set(paths.flatMap((path) => path.wallet_ids))]
  if (!nodeIds.length && trace?.source_wallet) nodeIds.push(trace.source_wallet)
  if (!nodeIds.length) return <div className="graph-empty">No downstream movement was visible at this snapshot.</div>
  const width = Math.max(560, nodeIds.length * 142 + 44)
  const height = Math.max(244, Math.ceil(nodeIds.length / 4) * 110 + 92)
  const positions = new Map(nodeIds.map((id, i) => [id, { x: 86 + (i % 4) * 142, y: 64 + Math.floor(i / 4) * 110 }]))
  const edges = new Map()
  paths.forEach((path) => path.edges.forEach((edge) => edges.set(edge.transaction_id, edge)))
  return <div className="graph-scroll"><svg className="flow-graph" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Observed synthetic transaction flow graph">
    <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#9bb9ae" /></marker><marker id="arrow-cash" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#e6a653" /></marker></defs>
    {[...edges.values()].map((edge) => {
      const from = positions.get(edge.sender_wallet); const to = positions.get(edge.receiver_wallet)
      if (!from || !to) return null
      const cash = edge.is_cashout
      const labelX = (from.x + to.x) / 2; const labelY = (from.y + to.y) / 2 - 10
      return <g key={edge.transaction_id} className="graph-edge"><line x1={from.x + 28} y1={from.y} x2={to.x - 31} y2={to.y} className={cash ? 'edge-cash' : 'edge-normal'} markerEnd={cash ? 'url(#arrow-cash)' : 'url(#arrow)'} /><text x={labelX} y={labelY} className="edge-amount">৳{Number(edge.amount_bdt).toLocaleString('en-BD')}</text></g>
    })}
    {nodeIds.map((id) => {
      const pos = positions.get(id); const sink = id.toLowerCase().includes('cash') || id === trace.source_wallet && paths.some((p) => p.terminal_cashout)
      return <g key={id} onClick={() => onWallet?.(id)} onKeyDown={(event) => event.key === 'Enter' && onWallet?.(id)} tabIndex="0" role="button" aria-label={`Select wallet ${id}`} className={`graph-node ${id === selectedWallet ? 'node-selected' : ''}`}>
        <circle cx={pos.x} cy={pos.y} r="25" className={sink ? 'node-cash' : id === trace.source_wallet ? 'node-source' : 'node-wallet'} />
        <text x={pos.x} y={pos.y + 4} className="node-icon">{sink ? '৳' : id === trace.source_wallet ? 'R' : 'W'}</text>
        <text x={pos.x} y={pos.y + 43} className="node-label">{short(id)}</text>
        <text x={pos.x} y={pos.y + 58} className="node-type">{sink ? 'CASH DESTINATION' : id === trace.source_wallet ? 'DIRECT RECIPIENT' : 'DOWNSTREAM WALLET'}</text>
      </g>
    })}
    <text x="20" y={height - 18} className="graph-caption">Observed from {trace.limits?.start_time ? new Date(trace.limits.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'report time'} · {trace.limits?.time_window_minutes ?? 30} min window · {trace.limits?.hop_limit ?? 5} hop cap</text>
  </svg></div>
}
