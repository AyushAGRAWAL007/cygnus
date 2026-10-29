import { Activity, CheckCircle2, CircleDashed, Database, Package, RefreshCw, Server, Sparkles, XCircle } from 'lucide-react'
import SimulatedBanner from '../components/SimulatedBanner'
import { useDashboardData } from '../hooks/useDashboardData'
import { useHealth } from '../hooks/useHealth'

function Row({ icon, label, ok, detail }: { icon: React.ReactNode; label: string; ok: boolean | null; detail: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-3">
      <span className="flex items-center gap-3 text-sm font-medium">{icon}{label}</span>
      <span className={`flex items-center gap-1.5 text-sm ${ok === null ? 'text-slate-400' : ok ? 'text-emerald-700' : 'text-rose-700'}`}>
        {ok === null ? <CircleDashed size={16} /> : ok ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
        {detail}
      </span>
    </li>
  )
}

export default function Dashboard() {
  const state = useHealth()
  const dashboard = useDashboardData()
  const h = state.phase === 'ready' ? state.health : null
  const loading = state.phase === 'loading'
  const data = dashboard.state.phase === 'ready' ? dashboard.state.data : null
  const activeCases = data?.returns.filter((item) => !item.resolved) ?? []

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-slate-600">System status and the return journey Cygnus will manage.</p>
        </div>
        <button onClick={() => { state.retry(); dashboard.retry() }} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-100">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      <div className="mt-6"><SimulatedBanner /></div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-semibold">System status</h2>
          {state.phase === 'error' && (
            <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
              Cannot reach the backend ({state.message}). Start it with <code>uvicorn app.main:app --reload</code> inside <code>backend/</code>.
            </p>
          )}
          <ul className="mt-2 divide-y divide-slate-100">
            <Row icon={<Server size={18} />} label="Backend (FastAPI)" ok={loading ? null : h ? true : false}
                 detail={loading ? 'Checking…' : h ? `Online, v${h.version}` : 'Offline'} />
            <Row icon={<Database size={18} />} label="Database (SQLite)" ok={h ? h.database === 'ok' : null}
                 detail={h ? (h.database === 'ok' ? 'Connected' : 'Error') : '—'} />
            <Row icon={<Sparkles size={18} />} label="AI (Nebius + NVIDIA)" ok={h ? h.ai.configured : null}
                 detail={h ? (h.ai.configured ? 'Key configured' : 'No API key yet') : '—'} />
          </ul>
          {h && <p className="mt-3 break-all text-xs text-slate-500">Model: {h.ai.model} · Retailer mode: {h.retailer_mode}</p>}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold">Return cases</h2>
              <p className="mt-1 text-sm text-slate-500">Current simulated case status</p>
            </div>
            <span className="rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700">
              {dashboard.state.phase === 'ready' ? `${activeCases.length} open` : '—'}
            </span>
          </div>
          {dashboard.state.phase === 'loading' && <p className="py-8 text-center text-sm text-slate-500">Loading simulated orders and return activity…</p>}
          {dashboard.state.phase === 'error' && (
            <div className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
              Could not load return data: {dashboard.state.message}
              <button onClick={dashboard.retry} className="ml-2 font-semibold underline">Retry</button>
            </div>
          )}
          {data && (
            <>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="flex items-center gap-2 text-xs text-slate-500"><Package size={14} /> Demo orders</p>
                  <p className="mt-1 text-xl font-semibold">{data.orders.length}</p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="flex items-center gap-2 text-xs text-slate-500"><Activity size={14} /> Return cases</p>
                  <p className="mt-1 text-xl font-semibold">{data.returns.length}</p>
                </div>
              </div>
              {data.returns.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-500">No simulated return cases yet.</p>
              ) : (
                <ul className="mt-3 divide-y divide-slate-100">
                  {data.returns.slice(0, 5).map((item) => (
                    <li key={item.id} className="flex items-center justify-between gap-3 py-3">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">{item.id}</span>
                        <span className="block text-xs text-slate-500">{item.order_id} · {item.reason.replaceAll('_', ' ')}</span>
                      </span>
                      <span className="shrink-0 rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">{item.status.replaceAll('_', ' ')}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
          <h2 className="font-semibold">Agent Activity</h2>
          <p className="mt-1 text-sm text-slate-500">Simulated workflow events and their recorded evidence</p>
          {dashboard.state.phase === 'loading' && <p className="py-8 text-center text-sm text-slate-500">Loading activity…</p>}
          {data && data.activity.length === 0 && <p className="py-8 text-center text-sm text-slate-500">No simulated activity recorded yet.</p>}
          {data && data.activity.length > 0 && (
            <ul className="mt-3 divide-y divide-slate-100">
              {data.activity.slice(0, 6).map((event) => (
                <li key={event.id} className="flex flex-wrap items-start justify-between gap-2 py-3">
                  <span>
                    <span className="block text-sm font-medium">{event.message}</span>
                    <span className="block text-xs text-slate-500">{event.case_id} · {event.order_id}</span>
                  </span>
                  <span className="text-xs text-slate-500">{new Date(event.occurred_at).toLocaleString()} · SIMULATED</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  )
}
