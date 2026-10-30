import ShoppingMetrics from '../components/ShoppingMetrics'
import { ArrowRight } from 'lucide-react'
import AssistantPanel from '../components/assistant/AssistantPanel'
import EventItem from '../components/activity/EventItem'
import { ReturnRow } from '../components/returns/CaseParts'
import { EmptyState, ErrorState, Loading, PageHeader, SectionTitle } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { listActivity, listReturns } from '../lib/api'
import { href } from '../lib/router'

function Stat({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="flex flex-col gap-1 border-l border-line pl-4 first:border-l-0 first:pl-0">
      <dt className="text-xs uppercase tracking-[0.12em] text-mute">{label}</dt>
      <dd className="num font-display text-4xl leading-none">{value}</dd>
      <dd className="text-xs text-mute">{note}</dd>
    </div>
  )
}

export default function Overview() {
  const returns = useResource('returns', listReturns)
  const activity = useResource('activity', listActivity)

  if (returns.phase === 'loading') return <div className="flex flex-col gap-8"><ShoppingMetrics /><Loading label="Loading your returns" /></div>
  if (returns.phase === 'error') return <div className="flex flex-col gap-8"><ShoppingMetrics /><ErrorState message={returns.message} onRetry={returns.retry} /></div>

  const all = returns.data
  const needs = all.filter((r) => r.health === 'needs_attention' || r.health === 'awaiting_approval')
  const open = all.filter((r) => r.health !== 'completed')
  const refundsIssued = all.filter((r) => r.refund.steps.some((step) => step.id === 'processed' && step.status === 'recorded')).length
  const recent = activity.phase === 'ready' ? activity.data.slice(0, 4) : []

  return (
    <div className="flex flex-col gap-10">
      <PageHeader eyebrow="Overview" title={needs.length ? <>Cygnus needs you on <em className="text-cobalt">{needs.length}</em> {needs.length === 1 ? 'return' : 'returns'}.</> : 'Your shopping, in view.'}>
        This simulated workflow currently has {open.length} open {open.length === 1 ? 'return' : 'returns'}. It asks for availability before a missed pickup can be rescheduled.
      </PageHeader>

      <ShoppingMetrics />
      <dl aria-label="Simulated workflow metrics" className="grid grid-cols-2 gap-6 md:grid-cols-4">
        <Stat label="Open returns" value={String(open.length)} note={`${all.length - open.length} completed`} />
        <Stat label="Needs you" value={String(needs.length)} note="Pickup availability or rescheduling" />
        <Stat label="Refunds issued" value={String(refundsIssued)} note="Simulated evidence events" />
        <Stat label="Bank credits" value="Not available" note="No bank evidence is connected" />
      </dl>

      <section aria-labelledby="needs" className="flex flex-col gap-3">
        <SectionTitle id="needs">Needs your attention</SectionTitle>
        <div className="overflow-hidden rounded-xl border border-line bg-paper/60">
          {needs.length ? (
            <ul className="divide-y divide-line">{needs.map((c) => <ReturnRow key={c.id} c={c} />)}</ul>
            ) : (
            <EmptyState title="Nothing needs you">Missed pickups needing customer availability will appear here.</EmptyState>
          )}
        </div>
      </section>

      <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="moving" className="flex flex-col gap-3">
          <SectionTitle id="moving" aside={<a href={href.returns} className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-ink">All returns <ArrowRight className="size-3.5" aria-hidden="true" /></a>}>
            In progress
          </SectionTitle>
          <div className="overflow-hidden rounded-xl border border-line bg-paper/60">
            {open.filter((c) => !needs.includes(c)).length > 0 ? (
              <ul className="divide-y divide-line">{open.filter((c) => !needs.includes(c)).map((c) => <ReturnRow key={c.id} c={c} />)}</ul>
            ) : (
              <EmptyState title="No returns in progress">New simulated cases appear here when the backend records them.</EmptyState>
            )}
          </div>
        </section>

        <section aria-labelledby="recent" className="flex flex-col gap-3">
          <SectionTitle id="recent" aside={<a href={href.activity} className="inline-flex items-center gap-1 text-sm text-ink-soft hover:text-ink">All activity <ArrowRight className="size-3.5" aria-hidden="true" /></a>}>
            What the demo recorded
          </SectionTitle>
          <div className="overflow-hidden rounded-xl border border-line bg-paper/60">
            {activity.phase === 'loading' && <div className="px-5"><Loading rows={3} /></div>}
            {activity.phase === 'error' && <div className="p-4"><ErrorState message={activity.message} onRetry={activity.retry} /></div>}
            {activity.phase === 'ready' && recent.length === 0 && <EmptyState title="No recorded events">No simulated workflow events have been recorded yet.</EmptyState>}
            {activity.phase === 'ready' && recent.length > 0 && <ul className="divide-y divide-line">{recent.map((event) => <EventItem key={event.id} event={event} />)}</ul>}
          </div>
        </section>
      </div>
      <AssistantPanel cases={all} />
    </div>
  )
}
