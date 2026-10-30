import { useState } from 'react'
import { LoaderCircle, LogOut } from 'lucide-react'
import { useAuth } from '../lib/authContext'
import { href } from '../lib/router'

export default function AccountControl() {
  const auth = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function signOut() {
    setBusy(true); setError('')
    try { await auth.logout() } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not sign out. Try again.') }
    finally { setBusy(false) }
  }
  if (auth.loading) return <span role="status" className="text-xs text-mute">Checking account?</span>
  if (!auth.user) return <a href={href.login} className="text-sm font-medium text-cobalt hover:underline">Sign in</a>
  return <div className="flex min-w-0 flex-wrap items-center gap-2">
    <span className="max-w-36 truncate text-xs text-ink-soft" title={auth.user.email}>{auth.user.display_name}</span>
    <button type="button" disabled={busy} onClick={() => void signOut()} className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-xs text-ink-soft hover:bg-bone disabled:opacity-50">
      {busy ? <LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" /> : <LogOut className="size-3.5" aria-hidden="true" />} Sign out
    </button>
    {error && <p role="alert" className="w-full text-xs text-bad">{error}</p>}
  </div>
}
