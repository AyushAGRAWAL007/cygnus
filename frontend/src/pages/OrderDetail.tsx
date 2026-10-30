import { useState } from 'react'
import { Button, ErrorState, Loading, PageHeader, ProductThumb } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { amount, productImage, saveRefund, shoppingOrder, type Refund, type RefundInput } from '../lib/shopping'
import { href } from '../lib/router'

function RefundForm({ orderId, currency, refund, onSaved }: { orderId: string; currency: string | null; refund?: Refund; onSaved: () => void }) {
  const [input, setInput] = useState<RefundInput>({ amount: refund?.amount ?? '', currency: refund?.currency ?? currency ?? '', status: refund?.status ?? 'pending', effective_date: refund?.effective_date ?? '', reference: refund?.reference ?? '', notes: refund?.notes ?? '', confirm_received: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  return <form className="grid gap-4 rounded-xl border border-line bg-paper p-5 sm:grid-cols-2" onSubmit={async e => { e.preventDefault(); setBusy(true); setError(''); try { await saveRefund(orderId, input, refund?.id); onSaved() } catch (e) { setError(e instanceof Error ? e.message : 'Could not save refund') } finally { setBusy(false) } }}>
    <h3 className="font-medium sm:col-span-2">{refund ? 'Edit refund record' : 'Record a refund'}</h3>
    <label className="text-sm">Amount<input aria-label="Refund amount" required inputMode="decimal" pattern="[0-9]+([.][0-9]{1,6})?" className="shopping-input" value={input.amount} onChange={e => setInput({ ...input, amount: e.target.value })} /></label>
    <label className="text-sm">Currency<input aria-label="Refund currency" required pattern="[A-Z]{3}" maxLength={3} className="shopping-input" value={input.currency} onChange={e => setInput({ ...input, currency: e.target.value.toUpperCase() })} /></label>
    <label className="text-sm">Status<select aria-label="Refund status" className="shopping-input" value={input.status} onChange={e => setInput({ ...input, status: e.target.value as RefundInput['status'], confirm_received: false })}><option value="pending">Pending</option><option value="received">Received</option></select></label>
    <label className="text-sm">Effective date<input aria-label="Refund date" required type="date" className="shopping-input" value={input.effective_date} onChange={e => setInput({ ...input, effective_date: e.target.value })} /></label>
    <label className="text-sm">Reference<input aria-label="Refund reference" required maxLength={200} className="shopping-input" value={input.reference} onChange={e => setInput({ ...input, reference: e.target.value })} /></label>
    <label className="text-sm">Notes<textarea aria-label="Refund notes" maxLength={2000} className="shopping-input" value={input.notes} onChange={e => setInput({ ...input, notes: e.target.value })} /></label>
    {input.status === 'received' && <label className="flex items-start gap-2 text-sm sm:col-span-2"><input required type="checkbox" checked={input.confirm_received} onChange={e => setInput({ ...input, confirm_received: e.target.checked })} />I confirm that I received this refund. This is my confirmation, not independent bank verification.</label>}
    {error && <div className="sm:col-span-2"><ErrorState message={error} /></div>}
    <Button type="submit" disabled={busy || (input.status === 'received' && !input.confirm_received)}>{busy ? 'Saving…' : 'Save refund record'}</Button>
  </form>
}

export default function OrderDetail({ id }: { id: string }) {
  const order = useResource(`shopping-order:${id}`, () => shoppingOrder(id))
  const [editing, setEditing] = useState<Refund | 'new' | null>(null)
  if (order.phase === 'loading') return <Loading label="Loading order" />
  if (order.phase === 'error') return <ErrorState message={order.message} onRetry={order.retry} />
  const o = order.data
  return <div className="flex flex-col gap-8"><a href={href.orders} className="text-sm text-cobalt">? All Orders</a><PageHeader eyebrow={o.simulated ? 'Demo order' : 'Recorded purchase'} title={o.retailer}>{o.external_order_id ?? o.id} · {o.order_date ?? 'Unknown date'}</PageHeader>
    <dl className="grid gap-4 rounded-xl border border-line bg-paper p-5 sm:grid-cols-3">{[['Charged total', amount(o.total_amount, o.currency)], ['Known-items subtotal', amount(o.known_items_subtotal, o.currency)], ['Delivery / order status', o.order_status ?? 'Unknown'], ['Payment status', o.payment_status ?? 'Unknown'], ['Sources', o.sources.join(', ') || o.source || 'Unknown'], ['Quantity coverage', `${o.quantity} known · ${o.unknown_quantities} unknown`]].map(([label, value]) => <div key={label}><dt className="text-xs text-mute">{label}</dt><dd className="mt-1 break-words">{value}</dd></div>)}</dl>
    <section><h2 className="mb-4 font-display text-2xl">Items</h2><ul className="grid gap-4">{o.items.map(item => <li key={item.id} className="flex gap-4 rounded-xl border border-line bg-paper p-5"><ProductThumb src={productImage(item.image_url)} alt={item.name || "Product image unavailable"} /><div className="min-w-0"><h3 className="break-words font-medium">{item.name || 'Unknown item'}</h3><p className="mt-2 text-sm">Quantity: {item.quantity ?? 'Unknown'} · Unit price: {amount(item.unit_price, item.currency)}</p><p className="text-sm text-mute">Category: {item.category ?? 'Unknown'} · Return deadline: {item.return_deadline ?? 'Unknown'}</p><p className="text-sm text-mute">Return eligibility: {item.return_eligibility || 'Unknown'}</p></div></li>)}</ul></section>
    {!!o.return_cases?.length && <section><h2 className="font-display text-2xl">Return cases</h2>{o.return_cases.map(c => <a className="mt-3 block text-sm text-cobalt underline" key={c.id} href={href.return(c.id)}>{c.id} · {c.status}</a>)}</section>}
    <section className="flex flex-col gap-4"><h2 className="font-display text-2xl">Refund records</h2><p className="text-sm text-mute">Received amounts are user-confirmed. Pending refunds do not reduce net spend. {o.total_amount === null ? 'The charged total is unknown, so reconciliation is unavailable.' : 'Refunds reconcile against the recorded charged total.'} {o.simulated && 'Demo records are excluded from real spend.'}</p>{!o.refunds.length && <p className="text-sm">No refunds recorded.</p>}{o.refunds.map(r => <div key={r.id} className="rounded-xl border border-line bg-paper p-5"><p className="font-medium">{amount(r.amount, r.currency)} · {r.status}</p><p className="mt-1 break-words text-sm text-mute">{r.effective_date} · {r.reference} · {r.confirmed_at ? 'User-confirmed receipt' : 'Receipt not confirmed'}</p>{r.notes && <p className="mt-2 break-words text-sm">{r.notes}</p>}<Button variant="secondary" size="sm" className="mt-3" onClick={() => setEditing(r)}>Edit refund</Button></div>)}<Button className="self-start" onClick={() => setEditing('new')}>Add refund record</Button>{editing && <RefundForm key={editing === 'new' ? 'new' : editing.id} orderId={o.id} currency={o.currency} refund={editing === 'new' ? undefined : editing} onSaved={() => { setEditing(null); order.retry() }} />}</section>
  </div>
}
