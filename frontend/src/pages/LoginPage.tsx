import { useState, type FormEvent } from 'react'
import { Boxes, Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import { ErrorState, LoadingState } from '../components/AsyncState'
import { useAuth } from '../context/useAuth'
import { errorMessage } from '../services/api'

export default function LoginPage() {
  const { user, loading, sessionError, signIn, checkSession } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [loginError, setLoginError] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setLoginError('')
    try {
      await signIn(email, password)
    } catch (reason) {
      setLoginError(errorMessage(reason))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <LoadingState label="Checking your session" />
  if (user) return <Navigate to="/" replace />

  return <main className="login-shell">
    <section className="login-panel" aria-labelledby="login-heading">
      <div className="login-brand"><span className="login-brand-mark"><Boxes size={20} /></span><span>Optimized Retail Inventory<br />Management System</span></div>
      <div className="login-heading"><h1 id="login-heading">Welcome Back</h1><p>Sign in to access your inventory dashboard.</p></div>
      {sessionError ? <div className="login-session-error"><ErrorState message={sessionError} retry={() => { void checkSession() }} /></div> : null}
      {loginError ? <div className="login-error" role="alert">{loginError}</div> : null}
      <form className="login-form" onSubmit={(event) => { void submit(event) }}>
        <label htmlFor="login-email">Email</label>
        <input id="login-email" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
        <label htmlFor="login-password">Password</label>
        <div className="login-password-field"><input id="login-password" type={showPassword ? 'text' : 'password'} autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} /><button type="button" className="login-password-toggle" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
        <button className="button button-primary login-submit" type="submit" disabled={submitting}>{submitting ? 'Signing in…' : <><LockKeyhole size={15} /> Sign In</>}</button>
      </form>
      <p className="login-footnote">Authorized users only</p>
    </section>
  </main>
}