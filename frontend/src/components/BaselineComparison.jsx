import { formatMoney } from '../api.js'

export default function BaselineComparison({ trace, taint }) {
  const direct = taint?.wallets?.find((wallet) => wallet.wallet_id === trace?.source_wallet)
  const directOnly = Number(direct?.potentially_tainted_bdt || 0)
  const network = Number(taint?.remaining_potentially_tainted_bdt || 0)
  const downstream = Math.max(0, network - directOnly)
  return <section className="content-card baseline-card">
    <div className="baseline-head"><div><div className="eyebrow">COVERAGE COMPARISON</div><h2>Direct recipient vs. traced network</h2></div><span className="method-pill">Same snapshot</span></div>
    <div className="baseline-columns">
      <div className="baseline-column"><span>DIRECT-RECIPIENT-ONLY VIEW</span><b>{formatMoney(directOnly)}</b><small>{direct?.wallet_id || 'Direct recipient not present in wallet summary'}</small></div>
      <div className="baseline-arrow">→</div>
      <div className="baseline-column network-column"><span>FLOWFREEZE NETWORK ESTIMATE</span><b>{formatMoney(network)}</b><small>{trace?.downstream_wallet_ids?.length || 0} downstream wallets · plus direct recipient</small></div>
      <div className="baseline-delta"><span>ADDITIONAL DOWNSTREAM ATTRIBUTION</span><b>+{formatMoney(downstream)}</b></div>
    </div>
    <p>This compares proportional attribution coverage at the same analysis time. It is not a tested value-preserved outcome comparison or an ML performance result.</p>
  </section>
}
