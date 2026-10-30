import { useState, type FormEvent } from 'react'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import Nav from '../components/Nav'
import { LinkButton } from '../components/ui/Kit'
import { useAuth } from '../lib/authContext'
import { href } from '../lib/router'

export default function Auth({ mode }: { mode: 'login' | 'register' }) {
  const auth = useAuth()
  const registering = mode === 'register'
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    if (registering && (!displayName.trim() || password.length < 8)) { setError('Enter your name and a password with at least 8 characters.'); return }
    setBusy(true); setError('')
    try {
      if (registering) await auth.register({ email: email.trim(), password, display_name: displayName.trim() })
      else await auth.login({ email: email.trim(), password })
      setPassword('')
      window.location.hash = href.overview
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not sign in. Please try again.'); setPassword('') }
    finally { setBusy(false) }
  }
  const input = 'mt-2 block h-11 w-full rounded-lg border border-line-strong bg-paper px-3 text-sm focus:border-cobalt focus:outline-none disabled:opacity-60'
  return <><Nav /><main id="main" className="mx-auto w-full max-w-lg px-5 py-12 md:py-20">
    <section className="rise rounded-2xl border border-line bg-paper/80 p-6 shadow-sm md:p-8" aria-labelledby="account-title">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-cobalt">Your Cygnus account</p>
      <h1 id="account-title" className="mt-3 font-display text-4xl">{registering ? 'Make room for less hassle.' : 'Welcome back.'}</h1>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft">{registering ? 'Create an account to get started with Cygnus.' : 'Sign in with your email and password.'} Return and refund actions remain simulated.</p>
      {auth.user ? <div className="mt-6"><p className="mb-4 text-sm text-ink-soft">Signed in as {auth.user.email}.</p><LinkButton href={href.overview}>Open workspace <ArrowRight className="size-4" aria-hidden="true" /></LinkButton></div> : <form onSubmit={(event) => void submit(event)} className="mt-7 flex flex-col gap-5" aria-busy={busy}>
        {registering && <label className="text-sm font-medium" htmlFor="account-name">Name<input id="account-name" name="name" autoComplete="name" required maxLength={80} value={displayName} onChange={(event) => setDisplayName(event.target.value)} disabled={busy} className={input} /></label>}
        <label className="text-sm font-medium" htmlFor="account-email">Email<input id="account-email" name="email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} className={input} /></label>
        <label className="text-sm font-medium" htmlFor="account-password">Password<input id="account-password" name="password" type="password" autoComplete={registering ? 'new-password' : 'current-password'} required minLength={registering ? 8 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} aria-describedby={registering ? 'password-help' : undefined} className={input} />{registering && <span id="password-help" className="mt-2 block text-xs font-normal text-mute">Use 8 to 128 characters. A memorable passphrase works well.</span>}</label>
        {error && <p role="alert" className="rounded-lg border border-bad/20 bg-bad-wash p-3 text-sm text-bad">{error}</p>}
        <button type="submit" disabled={busy || auth.loading} className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-ink px-5 text-sm font-medium text-paper transition-colors hover:bg-cobalt-deep disabled:cursor-not-allowed disabled:opacity-50">{busy && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}{busy ? 'Please wait?' : registering ? 'Create account' : 'Sign in'}</button>
        <p className="text-center text-sm text-ink-soft">{registering ? 'Already have an account?' : 'New to Cygnus?'} <a href={registering ? href.login : href.register} className="font-medium text-cobalt hover:underline">{registering ? 'Sign in' : 'Create an account'}</a></p>
      </form>}
    </section>
  </main></>
}
