import { useEffect, useState } from 'react'
import { fetchHealth, type Health } from '../lib/api'

type State =
  | { phase: 'loading' }
  | { phase: 'ready'; health: Health }
  | { phase: 'error'; message: string }

/** Asks the backend "are you alive?" once on mount and reports the answer. */
export function useHealth(): State & { retry: () => void } {
  const [state, setState] = useState<State>({ phase: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchHealth(ctrl.signal)
      .then((health) => setState({ phase: 'ready', health }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return
        setState({ phase: 'error', message: e instanceof Error ? e.message : 'Unknown error' })
      })
    return () => ctrl.abort()
  }, [attempt])

  const retry = () => {
    setState({ phase: 'loading' }) // set from the click, not inside the effect
    setAttempt((n) => n + 1)
  }
  return { ...state, retry }
}
