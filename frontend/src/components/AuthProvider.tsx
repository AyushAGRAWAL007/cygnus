import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError, fetchCurrentUser, loginAccount, logoutAccount, registerAccount, type AuthUser, type LoginInput, type RegisterInput } from '../lib/api'
import { AuthContext } from '../lib/authContext'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const generation = useRef(0)
  const refresh = useCallback(async () => {
    const current = ++generation.current
    try {
      const account = await fetchCurrentUser()
      if (generation.current === current) { setUser(account); setError('') }
    } catch (failure) {
      if (generation.current === current) {
        setUser(null)
        setError(failure instanceof ApiError && failure.status === 401 ? '' : failure instanceof Error ? failure.message : 'Could not check your session.')
      }
    } finally {
      if (generation.current === current) setLoading(false)
    }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    const current = ++generation.current
    fetchCurrentUser(controller.signal).then((account) => {
      if (!controller.signal.aborted && generation.current === current) { setUser(account); setError('') }
    }).catch((failure: unknown) => {
      if (!controller.signal.aborted && generation.current === current) {
        setUser(null)
        setError(failure instanceof ApiError && failure.status === 401 ? '' : failure instanceof Error ? failure.message : 'Could not check your session.')
      }
    }).finally(() => {
      if (!controller.signal.aborted && generation.current === current) setLoading(false)
    })
    const onFocus = () => { void refresh() }
    const onUnauthorized = () => { generation.current++; setUser(null); setError(''); setLoading(false) }
    window.addEventListener('focus', onFocus)
    window.addEventListener('cygnus:unauthorized', onUnauthorized)
    return () => { controller.abort(); window.removeEventListener('focus', onFocus); window.removeEventListener('cygnus:unauthorized', onUnauthorized) }
  }, [refresh])
  async function login(input: LoginInput) {
    generation.current++
    const account = await loginAccount(input)
    setUser(account); setError(''); setLoading(false)
  }
  async function register(input: RegisterInput) {
    generation.current++
    const account = await registerAccount(input)
    setUser(account); setError(''); setLoading(false)
  }
  async function logout() {
    generation.current++
    try { await logoutAccount() } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 401)) throw failure
    }
    setUser(null); setError(''); setLoading(false)
    window.location.hash = '#/login'
  }
  return <AuthContext.Provider value={{ user, loading, error, login, register, logout, refresh }}>{children}</AuthContext.Provider>
}
