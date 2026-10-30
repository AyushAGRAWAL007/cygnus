import { ArrowRight, CalendarClock, ListChecks, ShieldCheck } from 'lucide-react'
import Nav from '../components/Nav'
import SimulatedBanner from '../components/SimulatedBanner'
import { Wordmark } from '../components/brand/Wordmark'
import { EvidenceTag, HealthPill, SimTag } from '../components/ui/Evidence'
import { JourneyTrack } from '../components/ui/JourneyTrack'
import { LinkButton, ProductThumb } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { listReturns } from '../lib/api'
import { href } from '../lib/router'
import { useAuth } from '../lib/authContext'
import type { ReturnCase } from '../lib/types'

const steps = [
  { icon: ListChecks, title: 'Check the return', body: 'Choose a seeded order and check its return window and final-sale policy with the backend.' },
  { icon: CalendarClock, title: 'Run the demo', body: 'Record a simulated pickup, handle a missed pickup, and enter availability before rescheduling.' },
  { icon: ShieldCheck, title: 'Review the evidence', body: 'Each status is a simulated backend event. Refund issuance does not confirm a bank credit.' },
]

function HeroPreview({ c }: { c?: ReturnCase }) {
  if (!c) {
    return (
      <div className="rise rounded-2xl border border-line bg-paper p-6 shadow-[0_30px_60px_-30px_rgba(12,17,48,0.25)]">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-cobalt">Simulated case preview</p>
        <p className="mt-3 font-display text-2xl">No backend case is available to preview.</p>
        <p className="mt-2 text-sm text-ink-soft">The source of truth for this preview is the connected Cygnus API.</p>
      </div>
    )
  }
  return (
    <div className="rise relative rounded-2xl border border-line bg-paper p-5 shadow-[0_30px_60px_-30px_rgba(12,17,48,0.25)] md:p-6" style={{ animationDelay: '120ms' }}>
      <div className="flex items-center gap-3">
        <ProductThumb src={c.product.image} alt={c.product.image ? c.product.name : ''} size="md" />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-xs text-mute"><span className="num">{c.id}</span> · {c.retailer} <SimTag /></p>
          <p className="truncate font-medium">{c.product.name}</p>
        </div>
        <HealthPill health={c.health} />
      </div>
      <JourneyTrack stage={c.stage} health={c.health} labels className="mt-6" />
      <div className="mt-6 rounded-lg bg-warn-wash/60 p-4">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-mute">Next step</p>
        <p className="mt-1 font-display text-2xl leading-tight">{c.nextStep.label}</p>
      </div>
      <ul className="mt-4 flex flex-col divide-y divide-line text-sm">
        {[...c.events].reverse().slice(0, 3).map((event) => (
          <li key={event.id} className="flex items-center justify-between gap-3 py-2.5">
            <span className="truncate">{event.title}</span>
            <EvidenceTag status={event.evidence} source="simulated" />
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Landing() {
  const auth = useAuth()
  const cases = useResource(`landing:returns:${auth.user?.id ?? 'public'}`, () => auth.user ? listReturns() : Promise.resolve([]))
  const featured = cases.phase === 'ready' ? cases.data[0] : undefined

  return (
    <>
      <Nav />
      <main id="main">
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-14 md:px-8 lg:grid-cols-[1.1fr_1fr] lg:pt-24">
          <div className="rise">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-cobalt">A simulated returns workspace</p>
            <h1 className="mt-4 font-display text-5xl leading-[1.02] tracking-tight text-balance md:text-7xl">
              Returns, handled. <em className="text-mute">Progress, explained.</em>
            </h1>
            <p className="mt-6 max-w-lg text-lg text-ink-soft text-pretty">
              Explore seeded orders and a simulated return from eligibility to refund issuance. No retailer, courier, payment network, or bank is connected.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <LinkButton href={href.overview}>Open the workspace <ArrowRight className="size-4" aria-hidden="true" /></LinkButton>
              {featured && <LinkButton href={href.return(featured.id)} variant="secondary">See a simulated case</LinkButton>}
            </div>
            {cases.phase === 'error' && <p role="alert" className="mt-4 text-sm text-bad">Could not load a case preview: {cases.message}</p>}
            <SimulatedBanner className="mt-8 max-w-md" />
          </div>
          <HeroPreview c={featured} />
        </section>

        <section id="how" className="border-y border-line bg-paper/60">
          <div className="mx-auto max-w-6xl px-5 py-20 md:px-8">
            <h2 className="max-w-xl font-display text-4xl leading-tight text-balance md:text-5xl">A return with a visible record at every step.</h2>
            <ol className="mt-12 grid gap-10 md:grid-cols-3">
              {steps.map((step, index) => (
                <li key={step.title} className="flex flex-col gap-3 border-t border-ink pt-5">
                  <span className="flex items-center justify-between">
                    <span className="num font-display text-3xl text-mute">{String(index + 1).padStart(2, '0')}</span>
                    <step.icon className="size-5 text-cobalt" aria-hidden="true" />
                  </span>
                  <h3 className="text-lg font-medium">{step.title}</h3>
                  <p className="text-ink-soft text-pretty">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="evidence" className="mx-auto grid max-w-6xl gap-12 px-5 py-20 md:px-8 lg:grid-cols-2">
          <div>
            <h2 className="font-display text-4xl leading-tight text-balance md:text-5xl">“Issued” is not “credited.”</h2>
            <p className="mt-4 max-w-md text-ink-soft text-pretty">The backend records simulated refund issuance only. It has no bank or card evidence, so this demo never marks funds as credited.</p>
          </div>
          <ul className="flex flex-col divide-y divide-line rounded-xl border border-line bg-paper">
            {[
              { label: 'Eligibility', status: 'recorded' as const, note: 'Simulated policy decision' },
              { label: 'Pickup and shipment', status: 'recorded' as const, note: 'Simulated status events' },
              { label: 'Refund issuance', status: 'recorded' as const, note: 'Simulated event in case history' },
              { label: 'Bank credit', status: 'not_started' as const, note: 'No bank evidence is connected' },
            ].map((item) => (
              <li key={item.label} className="flex items-center justify-between gap-4 px-5 py-4">
                <div><p className="font-medium">{item.label}</p><p className="text-sm text-mute">{item.note}</p></div>
                <EvidenceTag status={item.status} source="simulated" />
              </li>
            ))}
          </ul>
        </section>
      </main>
      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-8 text-xs text-mute md:flex-row md:items-center md:justify-between md:px-8">
          <Wordmark className="scale-90 origin-left" />
          <span>Nebius × NVIDIA Global AI Hackathon 2026 · Simulated retailer demo</span>
        </div>
      </footer>
    </>
  )
}
