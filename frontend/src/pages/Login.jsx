export default function Login({ onContinue }) {
  return <main className="login-screen">
    <div className="login-ambient ambient-one" /><div className="login-ambient ambient-two" />
    <section className="login-card">
      <div className="brand-lockup login-brand"><div className="brand-mark">F</div><div><b>flowfreeze</b><small>UPAY BD · RISK REVIEW</small></div></div>
      <div className="login-kicker"><span /> ANALYST WORKSPACE</div>
      <h1>See the flow.<br /><em>Protect the value.</em></h1>
      <p className="login-copy">Review synthetic MFS incidents, trace downstream movement, and explore proportionate response options.</p>
      <div className="login-boundary"><span>✳</span><div><b>Sandbox environment</b><small>Uses generated demo data. No live customer accounts or payment systems are connected.</small></div></div>
      <button className="button button-primary login-action" onClick={onContinue}>Continue as demo analyst <span>→</span></button>
      <div className="login-foot">Demo access only · no account or password required</div>
    </section>
    <div className="login-caption">FLOWFREEZE <span>×</span> UPAY BD ANALYST CONSOLE</div>
  </main>
}
