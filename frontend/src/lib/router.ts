import { useSyncExternalStore } from 'react'

// Hash routing, extended from the original two-page router. No router library needed.
export type Route =
  | { name: 'home' }
  | { name: 'login' }
  | { name: 'register' }
  | { name: 'overview' }
  | { name: 'returns' }
  | { name: 'return'; id: string }
  | { name: 'reschedule'; id: string }
  | { name: 'activity' }
  | { name: 'orders' }
  | { name: 'order'; id: string }
  | { name: 'analytics' }
  | { name: 'retailers' }

export type Section = 'overview' | 'returns' | 'activity' | 'orders' | 'analytics' | 'retailers'

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent)
  const [head, id, sub] = parts
  switch (head) {
    case undefined:
      return { name: 'home' }
    case 'login': return { name: 'login' }
    case 'register': return { name: 'register' }
    case 'overview':
    case 'dashboard': // original route, kept so old links still work
      return { name: 'overview' }
    case 'returns':
      if (id && sub === 'reschedule') return { name: 'reschedule', id }
      if (id) return { name: 'return', id }
      return { name: 'returns' }
    case 'activity':
      return { name: 'activity' }
    case 'analytics': return { name: 'analytics' }
    case 'retailers': return { name: 'retailers' }
    case 'orders':
      if (id) return { name: 'order', id }
      return { name: 'orders' }
    default:
      return { name: 'home' }
  }
}

export function sectionOf(r: Route): Section | null {
  if (r.name === 'home' || r.name === 'login' || r.name === 'register') return null
  if (r.name === 'return' || r.name === 'reschedule') return 'returns'
  if (r.name === 'order') return 'orders'
  return r.name
}

export const href = {
  home: '#/',
  login: '#/login',
  register: '#/register',
  overview: '#/overview',
  returns: '#/returns',
  return: (id: string) => `#/returns/${encodeURIComponent(id)}`,
  reschedule: (id: string) => `#/returns/${encodeURIComponent(id)}/reschedule`,
  activity: '#/activity',
  orders: '#/orders',
  order: (id: string) => `#/orders/${encodeURIComponent(id)}`,
  analytics: '#/analytics',
  retailers: '#/retailers',
}

const subscribeHash = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

export function useHash(): string {
  return useSyncExternalStore(subscribeHash, () => window.location.hash, () => '')
}
