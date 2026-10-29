import { useEffect, useRef, useState } from 'react'
import { subscribe } from '../lib/api'

export type Resource<T> =
  | { phase: 'loading' }
  | { phase: 'ready'; data: T }
  | { phase: 'error'; message: string }

type Stored<T> = { key: string } & Resource<T>

/**
 * Loads data for `key` and reloads silently whenever the data layer reports a change
 * (e.g. after a reschedule). Same shape as useHealth, generalised.
 */
export function useResource<T>(key: string, load: () => Promise<T>): Resource<T> & { retry: () => void } {
  const [state, setState] = useState<Stored<T>>({ key, phase: 'loading' })
  const [version, setVersion] = useState(0)
  const loadRef = useRef(load)

  useEffect(() => {
    loadRef.current = load
  }, [load])

  useEffect(() => subscribe(() => setVersion((v) => v + 1)), [])

  useEffect(() => {
    let alive = true
    loadRef.current()
      .then((data) => alive && setState({ key, phase: 'ready', data }))
      .catch((e: unknown) => alive && setState({ key, phase: 'error', message: e instanceof Error ? e.message : 'Something went wrong' }))
    return () => {
      alive = false
    }
    // `load` is recreated each render; `key` + `version` are the real inputs.
  }, [key, version])

  const retry = () => {
    setState({ key, phase: 'loading' })
    setVersion((v) => v + 1)
  }
  const current: Resource<T> = state.key === key ? state : { phase: 'loading' }
  return { ...current, retry }
}
