import { CheckCircle2, CircleDashed, Database, RefreshCw, Server, Sparkles, XCircle } from 'lucide-react'
import SimulatedBanner from '../components/SimulatedBanner'
import { useHealth } from '../hooks/useHealth'

// The 12 stages of a return. Part 1 only lists them; later parts build them.
const journey = [
  'Understand the customer problem', 'Find or collect order information', 'Check the return policy',
  'Decide the next action', 'Initiate an eligible return', 'Track the courier pickup',
  'Detect missed pickups', 'Ask customer availability', 'Reschedule pickup',
  'Track package and refund', 'Follow up on problems', 'Confirm completion with evidence',
]

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
  const h = state.phase === 'ready' ? state.health : null
  const loading = state.phase === 'loading'

  return (
    <main className="mx-auto max-w-6xl px-5 py-10">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-slate-600">System status and the return journey Cygnus will manage.</p>
        </div>
        <button onClick={state.retry} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium hover:bg-slate-100">
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
          <h2 className="font-semibold">Return journey</h2>
          <p className="mt-1 text-sm text-slate-500">Not built yet. These are the stages planned for later parts.</p>
          <ol className="mt-4 grid gap-2 sm:grid-cols-2">
            {journey.map((s, i) => (
              <li key={s} className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-slate-200 text-xs font-semibold text-slate-600">{i + 1}</span>
                {s}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </main>
  )
}
