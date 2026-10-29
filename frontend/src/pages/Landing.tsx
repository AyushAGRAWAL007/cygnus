import { ArrowRight, CalendarClock, ClipboardCheck, PackageSearch, ShieldCheck } from 'lucide-react'
import SimulatedBanner from '../components/SimulatedBanner'

const steps = [
  { icon: ClipboardCheck, title: 'Understands the problem', body: 'Tell it what went wrong in plain words. It finds the order and checks the return policy.' },
  { icon: PackageSearch, title: 'Starts the return', body: 'If you are eligible, it initiates the return through an authorized integration.' },
  { icon: CalendarClock, title: 'Chases the courier', body: 'Detects a missed pickup, asks when you are home, and reschedules where supported.' },
  { icon: ShieldCheck, title: 'Confirms with evidence', body: 'It only says "refunded" when real status data shows it. No guessing.' },
]

export default function Landing() {
  return (
    <main>
      <section className="bg-gradient-to-b from-brand-50 to-slate-50">
        <div className="mx-auto max-w-6xl px-5 pb-16 pt-16 sm:pt-24">
          <p className="mb-4 inline-block rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-700">
            AI returns and refund agent
          </p>
          <h1 className="max-w-3xl text-4xl font-bold leading-tight sm:text-6xl">
            Wrong size? Say it once. Cygnus handles the rest.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-slate-600">
            Cygnus manages the whole return, from the first message to the money back, and follows up
            when something goes wrong, so you do not have to.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a
              href="#/dashboard"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-5 py-3 font-medium text-white shadow-sm transition hover:bg-brand-900"
            >
              Open dashboard <ArrowRight size={18} />
            </a>
          </div>
          <blockquote className="mt-10 max-w-xl rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-slate-700">
              "I ordered shoes, received the wrong size, and want my money back. Please handle the return."
            </p>
            <footer className="mt-2 text-xs text-slate-500">Example customer message</footer>
          </blockquote>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-14">
        <h2 className="text-2xl font-semibold">What Cygnus does for you</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map(({ icon: Icon, title, body }) => (
            <div key={title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-700">
                <Icon size={20} />
              </span>
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-1 text-sm text-slate-600">{body}</p>
            </div>
          ))}
        </div>
        <div className="mt-8">
          <SimulatedBanner />
        </div>
      </section>
    </main>
  )
}
