import { formatMoney } from '../api.js'

export default function WalletPanel({ wallet, onClear }) {
  return <section className="content-card wallet-panel"><div className="section-head"><div><div className="eyebrow">WALLET CONTEXT</div><h2>Selected wallet</h2></div><button className="icon-button" onClick={onClear} aria-label="Clear selected wallet">×</button></div>
    {!wallet ? <div className="wallet-empty">Select a node or wallet row to inspect the current snapshot.</div> : <>
      <div className="wallet-identity"><div className="wallet-avatar">◉</div><div><b>{wallet.wallet_id}</b><span>{wallet.customer_type || 'Digital wallet'} · synthetic profile</span></div></div>
      <div className="wallet-balance"><span>Current balance</span><b>{formatMoney(wallet.balance_bdt)}</b></div>
      <div className="wallet-stat"><span>Potentially tainted</span><b className="text-amber">{formatMoney(wallet.potentially_tainted_bdt)}</b></div>
      <div className="wallet-stat"><span>Potentially legitimate</span><b>{formatMoney(wallet.potentially_legitimate_bdt)}</b></div>
      <div className="ratio-track"><span style={{ width: `${Math.max(0, Math.min(100, Number(wallet.potentially_tainted_ratio || 0) * 100))}%` }} /></div><div className="ratio-label">{(Number(wallet.potentially_tainted_ratio || 0) * 100).toFixed(1)}% of this balance is estimated as linked</div>
      <div className="wallet-note">Proportional attribution is a bookkeeping estimate. It does not establish ownership or wrongdoing.</div>
    </>}
  </section>
}
