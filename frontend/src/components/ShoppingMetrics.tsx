import { ErrorState, Loading } from './ui/Kit'
import { useResource } from '../hooks/useResource'
import { amount, shoppingOverview } from '../lib/shopping'

export default function ShoppingMetrics() {
  const data = useResource('shopping-overview', shoppingOverview)
  if (data.phase === 'loading') return <Loading label="Loading shopping metrics" />
  if (data.phase === 'error') return <ErrorState message={data.message} onRetry={data.retry} />
  const d = data.data
  const finances = (key: 'gross' | 'net' | 'received' | 'pending') => d.currencies.length ? d.currencies.map(c => amount(c[key], c.currency)).join(' · ') : 'No known amounts'
  const metrics = [['Total Orders', String(d.total_orders)], ['Total Items Purchased', String(d.total_items)], ['Total Purchase Amount', finances('gross')], ['Net Shopping Spend', finances('net')], ['Open Returns', String(d.open_returns)], ['Completed Returns', String(d.completed_returns)], ['Refunds Received', finances('received')], ['Pending Refunds', finances('pending')]]
  return <section aria-label="Real shopping metrics" className="flex flex-col gap-4"><p className="text-sm text-mute">Real purchases only · {d.unknown_totals} orders with unknown totals · {d.unknown_quantities} items with unknown quantities. Amounts stay grouped by currency; net subtracts received refunds only. Unknown totals mean gross and net are incomplete; refunds against unknown totals can make observed net negative.</p><dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metrics.map(([label, value]) => <div key={label} className="rounded-xl border border-line bg-paper p-5"><dt className="text-xs uppercase tracking-wide text-mute">{label}</dt><dd className="mt-3 break-words font-display text-2xl">{value}</dd></div>)}</dl><p className="text-sm text-mute">Demo separately: {d.demo_orders} orders · {d.demo_open_returns} open returns · {d.demo_completed_returns} completed returns. Demo refund events are excluded from real spend.</p>{!d.total_orders && <p className="rounded-xl border border-line p-5 text-sm">No real purchases recorded yet. <a className="text-cobalt underline" href="#/orders">Import purchases</a>: connect Gmail, sync messages, then confirm the preview, or upload a supported file. Returns appear only when recorded.</p>}</section>
}
