import { useSyncExternalStore } from 'react'

// Hash routing, extended from the original two-page router. No router library needed.
export type Route =
  | { name: 'home' }
  | { name: 'overview' }
  | { name: 'returns' }
  | { name: 'return'; id: string }
  | { name: 'reschedule'; id: string }
  | { name: 'activity' }
  | { name: 'orders' }

export type Section = 'overview' | 'returns' | 'activity' | 'orders'

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent)
  const [head, id, sub] = parts
  switch (head) {
    case undefined:
      return { name: 'home' }
    case 'overview':
    case 'dashboard': // original route, kept so old links still work
      return { name: 'overview' }
    case 'returns':
      if (id && sub === 'reschedule') return { name: 'reschedule', id }
      if (id) return { name: 'return', id }
      return { name: 'returns' }
    case 'activity':
      return { name: 'activity' }
    case 'orders':
      return { name: 'orders' }
    default:
      return { name: 'home' }
  }
}

export function sectionOf(r: Route): Section | null {
  if (r.name === 'home') return null
  if (r.name === 'return' || r.name === 'reschedule') return 'returns'
  return r.name
}

export const href = {
  home: '#/',
  overview: '#/overview',
  returns: '#/returns',
  return: (id: string) => `#/returns/${encodeURIComponent(id)}`,
  reschedule: (id: string) => `#/returns/${encodeURIComponent(id)}/reschedule`,
  activity: '#/activity',
  orders: '#/orders',
}

const subscribeHash = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

export function useHash(): string {
  return useSyncExternalStore(subscribeHash, () => window.location.hash, () => '')
}
