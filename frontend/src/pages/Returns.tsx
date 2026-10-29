import { Search } from 'lucide-react'
import { useState } from 'react'
import { ReturnRow } from '../components/returns/CaseParts'
import { EmptyState, ErrorState, Loading, PageHeader, Segmented } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { listReturns } from '../lib/api'
import type { ReturnCase } from '../lib/types'

type Filter = 'all' | 'needs' | 'progress' | 'completed'
const match: Record<Filter, (c: ReturnCase) => boolean> = {
  all: () => true,
  needs: (c) => c.health === 'needs_attention' || c.health === 'awaiting_approval',
  progress: (c) => c.health === 'on_track',
  completed: (c) => c.health === 'completed',
}

export default function Returns() {
  const returns = useResource('returns', listReturns)
  const [filter, setFilter] = useState<Filter>('all')
  const [q, setQ] = useState('')

  return (
    <div className="flex flex-col gap-6">
      <PageHeader eyebrow="Returns" title="Every return, and where it stands.">
        Each row shows the next step and who owns it. Open one to see the evidence behind every status.
      </PageHeader>

      {returns.phase === 'loading' && <Loading label="Loading returns" />}
      {returns.phase === 'error' && <ErrorState message={returns.message} onRetry={returns.retry} />}
      {returns.phase === 'ready' && (() => {
        const all = returns.data
        const needle = q.trim().toLowerCase()
        const shown = all.filter(match[filter]).filter((c) =>
          !needle || [c.id, c.orderId, c.retailer, c.product.name].some((s) => s.toLowerCase().includes(needle)),
        )
        return (
          <>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <Segmented
                label="Filter returns"
                value={filter}
                onChange={setFilter}
                options={[
                  { value: 'all', label: 'All', count: all.length },
                  { value: 'needs', label: 'Needs you', count: all.filter(match.needs).length },
                  { value: 'progress', label: 'In progress', count: all.filter(match.progress).length },
                  { value: 'completed', label: 'Completed', count: all.filter(match.completed).length },
                ]}
              />
              <label className="relative block md:w-72">
                <span className="sr-only">Search returns</span>
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-mute" aria-hidden="true" />
                <input
                  type="search"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search item, retailer, or ID"
                  className="h-10 w-full rounded-full border border-line bg-paper pl-9 pr-4 text-sm placeholder:text-mute focus:border-ink focus:outline-none"
                />
              </label>
            </div>
            <div className="overflow-hidden rounded-xl border border-line bg-paper/60">
              {shown.length ? (
                <ul className="divide-y divide-line">{shown.map((c) => <ReturnRow key={c.id} c={c} />)}</ul>
              ) : (
                <EmptyState title={all.length === 0 ? 'No returns yet' : 'No returns match'}>
                  {all.length === 0 ? 'Eligible demo cases can be created from Orders.' : 'Try a different filter or search term.'}
                </EmptyState>
              )}
            </div>
          </>
        )
      })()}
    </div>
  )
}
