import { useState } from 'react'
import EventItem from '../components/activity/EventItem'
import { EmptyState, ErrorState, Loading, PageHeader, SectionTitle, Segmented } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { listActivity } from '../lib/api'

type Filter = 'all' | 'pickup' | 'shipment' | 'customer'
const match = (filter: Filter, event: { type: string; actor: string }) => {
  if (filter === 'pickup') return event.type.includes('pickup')
  if (filter === 'shipment') return event.type.startsWith('shipment') || event.type === 'refund_issued'
  if (filter === 'customer') return event.actor === 'customer'
  return true
}

export default function Activity() {
  const events = useResource('activity', listActivity)
  const [filter, setFilter] = useState<Filter>('all')

  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow="Agent activity" title="Recorded events, with their evidence.">
        This log contains simulated workflow events returned by the backend. It is not a live agent task or external carrier feed.
      </PageHeader>

      {events.phase === 'loading' && <Loading label="Loading simulated activity" />}
      {events.phase === 'error' && <ErrorState message={events.message} onRetry={events.retry} />}
      {events.phase === 'ready' && (() => {
        const shown = events.data.filter((event) => match(filter, event))
        return (
          <section aria-labelledby="log" className="flex flex-col gap-3">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <SectionTitle id="log">Activity log</SectionTitle>
                <Segmented
                  label="Filter activity"
                  value={filter}
                  onChange={setFilter}
                  options={[
                    { value: 'all', label: 'All', count: events.data.length },
                    { value: 'pickup', label: 'Pickup', count: events.data.filter((event) => match('pickup', event)).length },
                    { value: 'shipment', label: 'Shipment/refund', count: events.data.filter((event) => match('shipment', event)).length },
                    { value: 'customer', label: 'Customer input', count: events.data.filter((event) => match('customer', event)).length },
                  ]}
                />
              </div>
              <div className="overflow-hidden rounded-xl border border-line bg-paper/60">
                {shown.length ? (
                  <ul className="divide-y divide-line">{shown.map((event) => <EventItem key={event.id} event={event} />)}</ul>
                ) : (
                  <EmptyState title="No events match">No simulated activity matches this filter.</EmptyState>
                )}
              </div>
            </section>
        )
      })()}
    </div>
  )
}
