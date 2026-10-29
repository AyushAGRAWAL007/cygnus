import { useEffect, useRef, useState } from 'react'

export type ResourceState<T> =
  | { phase: 'loading' }
  | { phase: 'ready'; data: T }
  | { phase: 'error'; message: string }

export function useApiResource<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [state, setState] = useState<ResourceState<T>>({ phase: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const loadRef = useRef(load)

  useEffect(() => {
    loadRef.current = load
  }, [load])

  useEffect(() => {
    const controller = new AbortController()
    loadRef.current(controller.signal)
      .then((data) => setState({ phase: 'ready', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setState({ phase: 'error', message: error instanceof Error ? error.message : 'Unknown error' })
      })
    return () => controller.abort()
  }, [attempt, key])

  return {
    state,
    retry: () => {
      setState({ phase: 'loading' })
      setAttempt((value) => value + 1)
    },
  }
}