export default function Login({ onContinue }) {
  return <main className="login-screen">
    <div className="login-ambient ambient-one" /><div className="login-ambient ambient-two" />
    <section className="login-card">
      <div className="brand-lockup login-brand"><div className="brand-mark">F</div><div><b>flowfreeze</b><small>UPAY BD · MFS RISK OPERATIONS</small></div></div>
      <div className="login-kicker"><span /> UPAY BD RISK OPERATIONS</div>
      <h1>Follow the flow.<br /><em>Protect the wallet.</em></h1>
      <p className="login-copy">Review reported transfers, trace downstream wallet movement, and document proportionate controls for a digital financial service.</p>
      <div className="login-boundary"><span>✳</span><div><b>Controlled training environment</b><small>Uses generated MFS data. No customer accounts, payment rails, or live wallet balances are connected.</small></div></div>
      <button className="button button-primary login-action" onClick={onContinue}>Enter risk operations console <span>→</span></button>
      <div className="login-foot">Synthetic access only · no account or password required</div>
    </section>
    <div className="login-caption">FLOWFREEZE <span>×</span> UPAY BD ANALYST CONSOLE</div>
  </main>
}
