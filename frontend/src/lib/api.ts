// The only file that knows how to talk to the backend.
// An "API" here = the agreed set of URLs and JSON shapes the browser and server use.

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export interface Health {
  status: 'ok' | 'degraded'
  app: string
  version: string
  environment: string
  time: string
  database: 'ok' | 'error'
  ai: { provider: string; configured: boolean; model: string }
  retailer_mode: 'simulated' | 'live'
}

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const res = await fetch(`${BASE}/api/health`, { signal })
  if (!res.ok) throw new Error(`Backend responded ${res.status}`)
  return res.json()
}
