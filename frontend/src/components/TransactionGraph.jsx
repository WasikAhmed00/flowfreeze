const short = (value = '') => value.length > 17 ? `${value.slice(-13)}` : value

export default function TransactionGraph({ trace, onWallet, selectedWallet }) {
  const paths = trace?.paths || []
  const nodeIds = [...new Set(paths.flatMap((path) => path.wallet_ids))]
  if (!nodeIds.length && trace?.source_wallet) nodeIds.push(trace.source_wallet)
  if (!nodeIds.length) return <div className="graph-empty">No downstream movement was visible at this snapshot.</div>
  const width = Math.max(640, nodeIds.length * 154 + 54)
  const height = Math.max(280, Math.ceil(nodeIds.length / 4) * 124 + 104)
  const positions = new Map(nodeIds.map((id, i) => [id, { x: 102 + (i % 4) * 154, y: 78 + Math.floor(i / 4) * 124 }]))
  const edges = new Map()
  paths.forEach((path) => path.edges.forEach((edge) => edges.set(edge.transaction_id, edge)))
  return <div className="graph-scroll"><svg className="flow-graph" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Observed synthetic transaction flow graph">
    <defs><linearGradient id="graph-surface" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f8fcf8" /><stop offset="1" stopColor="#eef6f2" /></linearGradient><filter id="node-shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="3" stdDeviation="3" floodColor="#1e5b4b" floodOpacity=".14" /></filter><marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0,0 L0,7 L8,3.5 z" fill="#75a391" /></marker><marker id="arrow-cash" markerWidth="9" markerHeight="9" refX="7" refY="3.5" orient="auto"><path d="M0,0 L0,7 L8,3.5 z" fill="#d79438" /></marker></defs>
    <rect x="0" y="0" width={width} height={height} rx="14" className="graph-surface" />
    <text x="22" y="28" className="graph-title">OBSERVED FLOW · SYNTHETIC SNAPSHOT</text>
    {[...edges.values()].map((edge) => {
      const from = positions.get(edge.sender_wallet); const to = positions.get(edge.receiver_wallet)
      if (!from || !to) return null
      const cash = edge.is_cashout
      const startX = from.x + 39; const endX = to.x - 39; const midX = (startX + endX) / 2; const curve = Math.max(18, Math.abs(to.y - from.y) * .34)
      const path = `M ${startX} ${from.y} C ${midX} ${from.y - curve}, ${midX} ${to.y + curve}, ${endX} ${to.y}`
      const labelX = midX; const labelY = (from.y + to.y) / 2 - 8
      return <g key={edge.transaction_id} className="graph-edge"><path d={path} className={cash ? 'edge-cash' : 'edge-normal'} markerEnd={cash ? 'url(#arrow-cash)' : 'url(#arrow)'} /><rect x={labelX - 34} y={labelY - 11} width="68" height="18" rx="9" className={cash ? 'edge-badge edge-badge-cash' : 'edge-badge'} /><text x={labelX} y={labelY + 2} className="edge-amount">৳{Number(edge.amount_bdt).toLocaleString('en-BD')}</text></g>
    })}
    {nodeIds.map((id) => {
      const pos = positions.get(id); const sink = id.toLowerCase().includes('cash') || id === trace.source_wallet && paths.some((p) => p.terminal_cashout)
      return <g key={id} onClick={() => onWallet?.(id)} onKeyDown={(event) => event.key === 'Enter' && onWallet?.(id)} tabIndex="0" role="button" aria-label={`Select wallet ${id}`} className={`graph-node ${id === selectedWallet ? 'node-selected' : ''}`}>
        <rect x={pos.x - 39} y={pos.y - 30} width="78" height="60" rx="14" className={sink ? 'node-cash' : id === trace.source_wallet ? 'node-source' : 'node-wallet'} />
        <circle cx={pos.x} cy={pos.y - 8} r="12" className="node-orb" />
        <text x={pos.x} y={pos.y - 4} className="node-icon">{sink ? '৳' : id === trace.source_wallet ? 'R' : 'W'}</text>
        <text x={pos.x} y={pos.y + 43} className="node-label">{short(id)}</text>
        <text x={pos.x} y={pos.y + 58} className="node-type">{sink ? 'CASH DESTINATION' : id === trace.source_wallet ? 'DIRECT RECIPIENT' : 'DOWNSTREAM WALLET'}</text>
      </g>
    })}
    <text x="22" y={height - 20} className="graph-caption">Observed from {trace.limits?.start_time ? new Date(trace.limits.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'report time'} · {trace.limits?.time_window_minutes ?? 30} min window · {trace.limits?.hop_limit ?? 5} hop cap</text>
  </svg></div>
}
