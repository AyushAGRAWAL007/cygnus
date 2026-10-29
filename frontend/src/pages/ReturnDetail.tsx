import { ArrowLeft } from 'lucide-react'
import SimulationControls from '../components/returns/SimulationControls'
import { NextStepCard, PickupCard, RefundTracker, StageRoute, Timeline } from '../components/returns/CaseParts'
import { EvidenceTag, HealthPill, SimTag } from '../components/ui/Evidence'
import { EVIDENCE_COPY } from '../components/ui/evidenceData'
import { EmptyState, LinkButton, Loading, ProductThumb, SectionTitle } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { getReturn } from '../lib/api'
import { daysUntil, day, money } from '../lib/format'
import { href } from '../lib/router'
import type { Evidence } from '../lib/types'

export default function ReturnDetail({ id }: { id: string }) {
  const res = useResource(`return:${id}`, () => getReturn(id))

  if (res.phase === 'loading') return <Loading label="Loading return" />
  if (res.phase === 'error') {
    return (
      <div className="flex flex-col gap-4">
        <a href={href.returns} className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink"><ArrowLeft className="size-4" aria-hidden="true" /> All returns</a>
        <EmptyState title="Return not found" action={<LinkButton href={href.returns} variant="secondary" size="sm">Back to returns</LinkButton>}>{res.message}</EmptyState>
      </div>
    )
  }

  const c = res.data
  const left = daysUntil(c.windowEndsAt)

  return (
    <div className="flex flex-col gap-8">
      <a href={href.returns} className="inline-flex w-fit items-center gap-1.5 text-sm text-ink-soft hover:text-ink"><ArrowLeft className="size-4" aria-hidden="true" /> All returns</a>

      <header className="flex flex-col gap-5 md:flex-row md:items-start">
        <ProductThumb src={c.product.image} alt={c.product.name} className="size-24 md:size-28" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-mute">
            <span className="num">{c.id}</span>·<span>{c.retailer}</span>·<span className="num">{c.orderId}</span>
            {c.source === 'simulated' && <SimTag />}
          </div>
          <h1 className="mt-2 font-display text-4xl leading-tight text-balance md:text-5xl">{c.product.name}</h1>
          <p className="mt-1 text-sm text-ink-soft">{c.product.variant} · {money(c.product.price)}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
            <HealthPill health={c.health} />
            <span className="text-mute">Reason: <span className="text-ink">{c.reason}</span></span>
            {c.health !== 'completed' && <span className="text-mute">Simulated return window: <span className={left <= 7 ? 'text-warn' : 'text-ink'}>{left > 0 ? `${left} days left` : 'closed'}</span></span>}
          </div>
        </div>
      </header>

      <StageRoute c={c} />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-8">
          <NextStepCard c={c} />
          <SimulationControls c={c} />

          <section aria-labelledby="ledger" className="flex flex-col gap-3">
            <SectionTitle id="ledger">Case ledger</SectionTitle>
            <div className="rounded-xl border border-line bg-paper/60 px-4 md:px-5">
              <Timeline events={c.events} />
            </div>
          </section>
        </div>

        <aside className="flex min-w-0 flex-col gap-4">
          {c.pickup && <PickupCard pickup={c.pickup} source={c.source} />}
          <RefundTracker refund={c.refund} source={c.source} />
          <section aria-labelledby="opened" className="rounded-xl border border-line bg-paper p-5">
            <h2 id="opened" className="text-sm font-medium">Simulated case</h2>
            <p className="mt-2 text-sm text-ink-soft">Created {day(c.openedAt)} from seeded demo order data.</p>
            <p className="mt-1 text-xs text-mute">No customer message or external retailer record is stored for this case.</p>
          </section>
          <section aria-labelledby="legend" className="rounded-xl border border-dashed border-line-strong p-5">
            <h2 id="legend" className="text-sm font-medium">Reading the evidence</h2>
            <ul className="mt-3 flex flex-col gap-2.5">
              {(['confirmed', 'pending', 'unverified', 'failed'] as Evidence[]).map((e) => (
                <li key={e} className="flex flex-col gap-0.5">
                  <EvidenceTag status={e} />
                  <span className="text-xs text-mute">{EVIDENCE_COPY[e].meaning}</span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  )
}
