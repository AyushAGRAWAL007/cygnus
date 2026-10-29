import { ArrowRight, CalendarClock, ChevronRight, Truck } from 'lucide-react'
import { cn, dateTime, day, money, relative } from '../../lib/format'
import { href } from '../../lib/router'
import type { Actor, CaseEvent, Pickup, Refund, RefundStepId, ReturnCase } from '../../lib/types'
import { STAGES, stageIndex } from '../../lib/types'
import { EVIDENCE_COPY } from '../ui/evidenceData'
import { EvidenceGlyph, EvidenceTag, HealthPill, SimTag } from '../ui/Evidence'
import { JourneyTrack } from '../ui/JourneyTrack'
import { LinkButton, ProductThumb } from '../ui/Kit'

const ACTOR_LABEL: Record<Actor, string> = {
  cygnus: 'Cygnus', customer: 'You', system: 'Cygnus demo',
}

/** One row in a list of returns. */
export function ReturnRow({ c }: { c: ReturnCase }) {
  const stage = STAGES[stageIndex(c.stage)]
  return (
    <li>
      <a href={href.return(c.id)} className="group grid grid-cols-[auto_1fr_auto] items-center gap-4 px-4 py-4 transition-colors hover:bg-paper md:grid-cols-[auto_minmax(0,1.4fr)_minmax(0,1fr)_auto] md:px-5">
        <ProductThumb src={c.product.image} alt="" size="md" />
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-xs text-mute">
            <span className="num">{c.id}</span> · <span className="truncate">{c.retailer}</span>
          </p>
          <p className="mt-0.5 truncate font-medium">{c.product.name}</p>
          <p className="mt-1 truncate text-sm text-ink-soft">{c.nextStep.label}</p>
        </div>
        <div className="hidden min-w-0 md:block">
          <JourneyTrack stage={c.stage} health={c.health} />
          <p className="mt-2 text-xs text-mute">{c.health === 'completed' ? 'Complete' : stage.label} · updated {relative(c.updatedAt)}</p>
        </div>
        <div className="flex items-center gap-3">
          <HealthPill health={c.health} />
          <ChevronRight className="size-4 text-mute transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
        </div>
      </a>
    </li>
  )
}

/** The single most important thing about a case: what happens next and who owns it. */
export function NextStepCard({ c }: { c: ReturnCase }) {
  const urgent = c.health === 'needs_attention'
  const missed = c.pickup?.status === 'missed'
  return (
    <section aria-labelledby="next-step" className={cn('rounded-xl border p-5 md:p-6', urgent ? 'border-warn/30 bg-warn-wash/50' : 'border-line bg-paper')}>
      <p id="next-step" className="text-xs font-medium uppercase tracking-[0.14em] text-mute">Next step</p>
      <p className="mt-2 font-display text-3xl leading-tight text-balance">{c.nextStep.label}</p>
      <p className="mt-2 text-sm text-ink-soft text-pretty">{c.nextStep.detail}</p>
      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <div className="flex gap-1.5"><dt className="text-mute">Owner</dt><dd className="font-medium">{ACTOR_LABEL[c.nextStep.owner]}</dd></div>
        {c.nextStep.expectedBy && <div className="flex gap-1.5"><dt className="text-mute">Expected</dt><dd className="font-medium">{day(c.nextStep.expectedBy)}</dd></div>}
      </dl>
      {(missed || c.nextStep.label.includes('new simulated pickup date')) && (
        <LinkButton href={href.reschedule(c.id)} className="mt-5">
          Reschedule pickup <ArrowRight className="size-4" aria-hidden="true" />
        </LinkButton>
      )}
    </section>
  )
}

export function StageRoute({ c }: { c: ReturnCase }) {
  return (
    <section aria-label="Return progress" className="rounded-xl border border-line bg-paper p-5 md:p-6">
      <JourneyTrack stage={c.stage} health={c.health} size="lg" labels />
    </section>
  )
}

const PICKUP_STATUS: Record<Pickup['status'], string> = {
  scheduled: 'Simulated date scheduled', missed: 'Pickup marked missed in demo', reschedule_requested: 'Reschedule recorded in demo', collected: 'Pickup completion recorded in demo',
}

export function PickupCard({ pickup, source }: { pickup: Pickup; source: ReturnCase['source'] }) {
  return (
    <section aria-labelledby="pickup" className="rounded-xl border border-line bg-paper p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 id="pickup" className="flex items-center gap-2 text-sm font-medium"><Truck className="size-4 text-mute" aria-hidden="true" /> Simulated pickup</h2>
        <EvidenceTag status={pickup.status === 'missed' ? 'failed' : pickup.evidence} source={source} />
      </div>
      <p className={cn('mt-3 text-lg font-medium', pickup.status === 'missed' && 'text-bad')}>{PICKUP_STATUS[pickup.status]}</p>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        {pickup.date && <><dt className="text-mute">Date</dt><dd className="flex items-center gap-1.5"><CalendarClock className="size-3.5 text-mute" aria-hidden="true" />{day(pickup.date)}</dd></>}
        <dt className="text-mute">External courier</dt><dd>Not connected</dd>
      </dl>
    </section>
  )
}

const REFUND_LABEL: Record<RefundStepId, string> = {
  requested: 'Refund request status', approved: 'Retailer approval status', processed: 'Simulated refund issuance', credited: 'Bank credit not verified',
}

/**
 * Refund status split into four separate claims. "Processed" is never shown as "credited":
 * only a bank or card record confirms money has arrived.
 */
export function RefundTracker({ refund, source }: { refund: Refund; source: ReturnCase['source'] }) {
  return (
    <section aria-labelledby="refund" className="rounded-xl border border-line bg-paper p-5">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="refund" className="text-sm font-medium">Refund</h2>
        <p className="num font-display text-2xl">{refund.amount === undefined ? 'Not available' : money(refund.amount)}</p>
      </div>
      <p className="text-xs text-mute">Payment method is not available in this demo.</p>
      <ol className="mt-4 flex flex-col">
        {refund.steps.map((s, i) => (
          <li key={s.id} className="relative flex gap-3 pb-4 last:pb-0">
            {i < refund.steps.length - 1 && <span aria-hidden="true" className="absolute left-[3.5px] top-4 h-[calc(100%-0.75rem)] w-px bg-line" />}
            <EvidenceGlyph status={s.status} className="mt-1.5" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className={cn('text-sm', s.status === 'not_started' ? 'text-mute' : 'font-medium')}>{REFUND_LABEL[s.id]}</p>
                <span className="text-[11px] uppercase tracking-[0.08em] text-mute">{EVIDENCE_COPY[s.status].label}</span>
              </div>
              {s.at && <p className="text-xs text-mute">{dateTime(s.at)}</p>}
              {s.note && <p className="mt-1 text-xs text-ink-soft text-pretty">{s.note}</p>}
              {s.reference && <p className="num mt-1 text-xs text-ink-soft">Ref {s.reference}</p>}
            </div>
          </li>
        ))}
      </ol>
      {source === 'simulated' && <p className="mt-4 flex items-center gap-2 border-t border-line pt-3 text-xs text-mute"><SimTag /> No real money moves in this demo.</p>}
    </section>
  )
}

/** The case ledger: every claim, who made it, and what backs it. */
export function Timeline({ events }: { events: CaseEvent[] }) {
  const sorted = [...events].sort((a, b) => b.at.localeCompare(a.at))
  return (
    <ol className="flex flex-col">
      {sorted.map((e, i) => (
        <li key={e.id} className={cn('rise grid grid-cols-[5.5rem_1fr] gap-4 border-t border-line py-4 first:border-t-0 md:grid-cols-[8rem_1fr]')} style={{ animationDelay: `${Math.min(i, 6) * 40}ms` }}>
          <div className="text-xs text-mute">
            <p className="num">{day(e.at)}</p>
            <p className="num">{dateTime(e.at).split(', ').pop()}</p>
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-soft">{ACTOR_LABEL[e.actor]}</span>
              <EvidenceTag status={e.evidence} source={e.source} />
            </div>
            <p className="mt-1 font-medium">{e.title}</p>
            {e.detail && <p className="mt-0.5 text-sm text-ink-soft text-pretty">{e.detail}</p>}
            {e.reference && <p className="num mt-1 text-xs text-mute">Ref {e.reference}</p>}
          </div>
        </li>
      ))}
    </ol>
  )
}
