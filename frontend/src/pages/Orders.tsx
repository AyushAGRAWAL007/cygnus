import { useState } from 'react'
import { Button, EmptyState, ErrorState, Loading, PageHeader } from '../components/ui/Kit'
import ImportHub from '../components/imports/ImportHub'
import { useResource } from '../hooks/useResource'
import { amount, shoppingOrders } from '../lib/shopping'
import { href } from '../lib/router'
import LegacyOrders from './LegacyOrders'

export default function Orders() {
  const [filters, setFilters] = useState({ q: '', retailer: '', date_from: '', date_to: '', status: '', sort: 'newest', currency: '', scope: 'all', page_size: '20' })
  const [page, setPage] = useState(1)
  const [legacyOpen, setLegacyOpen] = useState(false)
  const params = new URLSearchParams(Object.entries({ ...filters, page: String(page) }).filter(([key, value]) => value !== '' && (key !== 'currency' || value.length === 3)))
  const orders = useResource(`shopping-orders:${params}`, () => shoppingOrders(params))
  function change(key: keyof typeof filters, value: string) { setFilters(f => ({ ...f, [key]: value, ...(key === 'currency' && value.length !== 3 ? { sort: 'newest' } : {}) })); setPage(1) }
  return <div className="flex flex-col gap-8">
    <PageHeader eyebrow="All Orders" title="Your purchases, together.">Search recorded purchases and review their sources. Connecting Gmail, syncing messages and confirming an import are separate steps.</PageHeader>
    <ImportHub />
    <form className="grid gap-3 rounded-xl border border-line bg-paper p-5 sm:grid-cols-2 lg:grid-cols-3" onSubmit={e => e.preventDefault()}>
      <label className="text-sm">Search product or order ID<input maxLength={200} aria-label="Search orders" className="shopping-input" value={filters.q} onChange={e => change('q', e.target.value)} /></label>
      <label className="text-sm">Retailer<input aria-label="Retailer" className="shopping-input" list="retailer-options" value={filters.retailer} onChange={e => change('retailer', e.target.value)} /><datalist id="retailer-options">{orders.phase === 'ready' && orders.data.retailers.map(r => <option key={r} value={r} />)}</datalist></label>
      <label className="text-sm">Status<input className="shopping-input" list="status-options" value={filters.status} onChange={e => change('status', e.target.value)} /><datalist id="status-options">{orders.phase === 'ready' && orders.data.statuses.map(s => <option key={s} value={s} />)}</datalist></label>
      <label className="text-sm">From date<input type="date" className="shopping-input" value={filters.date_from} onChange={e => change('date_from', e.target.value)} /></label>
      <label className="text-sm">To date<input type="date" className="shopping-input" value={filters.date_to} onChange={e => change('date_to', e.target.value)} /></label>
      <label className="text-sm">Currency (ISO code)<input aria-label="Currency" className="shopping-input" maxLength={3} value={filters.currency} placeholder="All currencies" onChange={e => change('currency', e.target.value.toUpperCase())} /></label>
      <label className="text-sm">Sort<select aria-label="Sort orders" className="shopping-input" value={filters.sort} onChange={e => change('sort', e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option disabled={filters.currency.length !== 3} value="amount_desc">Highest amount (select currency)</option><option disabled={filters.currency.length !== 3} value="amount_asc">Lowest amount (select currency)</option></select></label>
      <label className="text-sm">Records<select className="shopping-input" value={filters.scope} onChange={e => change('scope', e.target.value)}><option value="all">All records</option><option value="real">Real purchases</option><option value="demo">Demo only</option></select></label>
      <label className="text-sm">Page size<select className="shopping-input" value={filters.page_size} onChange={e => change('page_size', e.target.value)}>{[10,20,50].map(n => <option key={n}>{n}</option>)}</select></label>
    </form>
    {orders.phase === 'loading' && <Loading label="Loading purchases" />}
    {orders.phase === 'error' && <ErrorState message={orders.message} onRetry={orders.retry} />}
    {orders.phase === 'ready' && <>
      <p className="text-sm text-mute">{orders.data.total} matching orders · Unknown amounts sort last.</p>
      {!orders.data.items.length ? <EmptyState title="No matching orders">Sync Gmail or upload a supported file, then confirm the preview. Try clearing filters to see other purchases. Returns appear only when recorded.</EmptyState> : <ul className="grid gap-4 md:grid-cols-2">{orders.data.items.map(order => <li key={order.id} className="min-w-0 rounded-xl border border-line bg-paper p-5"><div className="flex justify-between gap-3"><h2 className="font-medium">{order.retailer}</h2><span className="text-xs text-mute">{order.simulated ? 'Demo' : 'Imported'}</span></div><p className="mt-2 break-all text-xs text-mute">{order.external_order_id ?? order.id} · {order.order_date ?? 'Unknown date'}</p><p className="mt-3 font-display text-2xl">{amount(order.total_amount, order.currency)}</p><p className="text-xs text-mute">Charged total · {order.order_status ?? 'Unknown status'}</p><p className="mt-3 text-sm">{order.items.map(i => i.name).join(', ') || 'Unknown items'}</p><p className="mt-2 text-xs text-mute">{order.quantity} known quantity · {order.unknown_quantities} unknown · Refund: {order.refund_status || 'Unknown'}</p><p className="mt-2 text-xs text-mute">Sources: {order.sources.join(', ') || order.source || 'Unknown'}</p><a className="mt-4 inline-block text-sm text-cobalt underline" href={href.order(order.id)}>View order and refunds</a></li>)}</ul>}
      <div className="flex items-center justify-between gap-3"><Button variant="secondary" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Previous</Button><span className="text-sm">Page {page} of {Math.max(1, Math.ceil(orders.data.total / Number(filters.page_size)))}</span><Button variant="secondary" disabled={page * Number(filters.page_size) >= orders.data.total} onClick={() => setPage(p => p + 1)}>Next</Button></div>
    </>}
    <details className="rounded-xl border border-line p-5" onToggle={e => setLegacyOpen(e.currentTarget.open)}><summary className="cursor-pointer font-medium">Existing order policy checks and simulated return actions</summary>{legacyOpen && <div className="mt-6"><LegacyOrders /></div>}</details>
  </div>
}
