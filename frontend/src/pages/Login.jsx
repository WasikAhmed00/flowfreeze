import { useState } from 'react'

export default function Login({ onContinue }) {
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('analyst@upay.bd')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const submit = (event) => {
    event.preventDefault()
    setError(''); setMessage('')
    if (!email.trim() || !email.includes('@')) { setError('Enter a valid work email address.'); return }
    if (password.length < 6) { setError('Use at least 6 characters for the demo password.'); return }
    if (mode === 'create' && !name.trim()) { setError('Enter your analyst name to create the demo profile.'); return }
    setMessage(mode === 'create' ? `Profile created for ${name.trim()}. Opening the sandbox…` : 'Secure demo session verified. Opening the sandbox…')
    window.setTimeout(() => onContinue?.(), 350)
  }

  const googleSignIn = () => {
    setError(''); setMessage('Google demo sign-in verified. Opening the sandbox…')
    window.setTimeout(() => onContinue?.(), 350)
  }

  return <main className="login-screen">
    <div className="login-ambient ambient-one" /><div className="login-ambient ambient-two" />
    <section className="login-card">
      <div className="brand-lockup login-brand"><div className="brand-mark">F</div><div><b>flowfreeze</b><small>UPAY BD · MFS RISK OPERATIONS</small></div></div>
      <div className="login-kicker"><span /> UPAY BD RISK OPERATIONS</div>
      <h1>Follow the flow.<br /><em>Protect the wallet.</em></h1>
      <p className="login-copy">Review reported transfers, trace downstream wallet movement, and document proportionate controls for a digital financial service.</p>
      <div className="login-boundary"><span>✳</span><div><b>Controlled training environment</b><small>Uses generated MFS data. No customer accounts, payment rails, or live wallet balances are connected.</small></div></div>
      <div className="auth-tabs" role="tablist" aria-label="Account access"><button className={mode === 'signin' ? 'active' : ''} onClick={() => { setMode('signin'); setError(''); setMessage('') }} role="tab" aria-selected={mode === 'signin'}>Sign in</button><button className={mode === 'create' ? 'active' : ''} onClick={() => { setMode('create'); setError(''); setMessage('') }} role="tab" aria-selected={mode === 'create'}>Create account</button></div>
      <form onSubmit={submit} className="auth-form">
        {mode === 'create' && <label>ANALYST NAME<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Your name" autoComplete="name" /></label>}
        <label>WORK EMAIL<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="analyst@upay.bd" autoComplete="email" /></label>
        <label>PASSWORD<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="6+ characters for demo access" autoComplete={mode === 'create' ? 'new-password' : 'current-password'} /></label>
        {error && <div className="auth-feedback auth-error" role="alert">{error}</div>}
        {message && <div className="auth-feedback auth-success" role="status">{message}</div>}
        <button className="button button-primary login-action" type="submit">{mode === 'create' ? 'Create demo account' : 'Sign in to console'} <span>→</span></button>
      </form>
      <div className="auth-divider"><span>or continue with</span></div>
      <button className="google-button" type="button" onClick={googleSignIn}><span className="google-g">G</span> Continue with Google <span className="google-arrow">→</span></button>
      <button className="demo-link" type="button" onClick={googleSignIn}>Continue as demo analyst</button>
      <div className="login-foot">Synthetic access only · no account or password required</div>
    </section>
    <div className="login-caption">FLOWFREEZE <span>×</span> UPAY BD ANALYST CONSOLE</div>
  </main>
}
