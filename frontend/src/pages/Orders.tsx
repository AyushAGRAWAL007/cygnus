import { ArrowUpRight, Check, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { SimTag } from '../components/ui/Evidence'
import { Button, EmptyState, ErrorState, Loading, PageHeader, ProductThumb } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { checkReturnEligibility, createReturnFromOrder, listOrders } from '../lib/api'
import type { EligibilityResult, Order, OrderItem } from '../lib/types'
import { cn, daysUntil, money, shortDate } from '../lib/format'
import { href } from '../lib/router'

export default function Orders() {
  const orders = useResource('orders', listOrders)
  const [selected, setSelected] = useState<{ order: Order; item: OrderItem } | null>(null)
  const [reason, setReason] = useState('wrong_size')
  const [eligibility, setEligibility] = useState<EligibilityResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')

  async function check(order: Order, item: OrderItem) {
    setSelected({ order, item })
    setEligibility(null)
    setError('')
    setChecking(true)
    try {
      setEligibility(await checkReturnEligibility({ order_id: order.id, item_id: item.id, reason }))
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not check simulated eligibility')
    } finally {
      setChecking(false)
    }
  }

  async function createCase() {
    if (!selected) return
    setChecking(true)
    setError('')
    try {
      const created = await createReturnFromOrder({ order_id: selected.order.id, item_id: selected.item.id, reason })
      window.location.hash = href.return(created.id)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not create simulated return')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader eyebrow="Orders" title="Orders Cygnus can see.">
        Cygnus reads these to check return windows and policies. Return windows closing within a week are highlighted.
      </PageHeader>

      {orders.phase === 'loading' && <Loading label="Loading orders" />}
      {orders.phase === 'error' && <ErrorState message={orders.message} onRetry={orders.retry} />}
      {orders.phase === 'ready' && orders.data.length === 0 && <EmptyState title="No seeded orders">The backend has no simulated orders to display.</EmptyState>}
      {orders.phase === 'ready' && orders.data.length > 0 && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(17rem,0.8fr)]">
          <ul className="grid gap-4 md:grid-cols-2">
            {orders.data.map((order) => {
              const left = daysUntil(order.returnWindowEndsAt)
              return (
                <li key={order.id} className="flex flex-col gap-4 rounded-xl border border-line bg-paper p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="flex items-center gap-2 text-xs text-mute"><span className="num">{order.id}</span><SimTag /></p>
                      <p className="mt-1 font-medium">{order.retailer}</p>
                    </div>
                    <p className="num font-display text-2xl" title="Sum of seeded item prices; tax and shipping are not available">{money(order.total)}<span className="block text-right font-sans text-[10px] text-mute">items subtotal</span></p>
                  </div>
                  <ul className="flex flex-col gap-3">
                    {order.items.map((item) => (
                      <li key={item.sku} className="flex items-center gap-3">
                        <ProductThumb src={item.image} alt={item.image ? item.name : ''} size="sm" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{item.name}</p>
                          <p className="truncate text-xs text-mute">SKU {item.sku} · Qty {item.qty}</p>
                        </div>
                        <span className="num text-sm">{money(item.price)}</span>
                        <Button variant="secondary" size="sm" onClick={() => void check(order, item)}>Check policy</Button>
                      </li>
                    ))}
                  </ul>
                  <dl className="grid grid-cols-2 gap-3 border-t border-line pt-4 text-xs">
                    <div><dt className="text-mute">Ordered</dt><dd className="num mt-0.5 text-ink">{shortDate(order.placedAt)}</dd></div>
                    <div>
                      <dt className="text-mute">Simulated return window</dt>
                      <dd className={cn('num mt-0.5', left <= 0 ? 'text-mute' : left <= 7 ? 'font-medium text-warn' : 'text-ink')}>
                        {left > 0 ? `${left} days left` : 'Closed'}
                      </dd>
                    </div>
                  </dl>
                  {order.returnId && <a href={href.return(order.returnId)} className="inline-flex w-fit items-center gap-1 text-sm font-medium text-cobalt hover:text-cobalt-deep">View return {order.returnId} <ArrowUpRight className="size-3.5" aria-hidden="true" /></a>}
                </li>
              )
            })}
          </ul>
          <section aria-labelledby="eligibility" className="h-fit rounded-xl border border-line bg-paper p-5">
            <h2 id="eligibility" className="font-medium">Simulated eligibility check</h2>
            {!selected && <p className="mt-2 text-sm text-mute">Choose an order item to check the backend return policy.</p>}
            {selected && (
              <>
                <p className="mt-2 text-sm text-ink-soft">{selected.item.name} · {selected.order.id}</p>
                <label className="mt-4 block text-sm font-medium">Reason
                  <select value={reason} onChange={(event) => { setReason(event.target.value); setEligibility(null) }} className="mt-1 h-10 w-full rounded-lg border border-line-strong bg-paper px-3">
                    <option value="wrong_size">Wrong size</option>
                    <option value="damaged">Damaged</option>
                    <option value="not_as_described">Not as described</option>
                    <option value="changed_mind">Changed my mind</option>
                  </select>
                </label>
                {checking && <p role="status" className="mt-3 flex items-center gap-2 text-sm text-mute"><LoaderCircle className="size-4 animate-spin" />Checking policy…</p>}
                {error && <p role="alert" className="mt-3 rounded-lg bg-bad-wash p-3 text-sm text-bad">{error}</p>}
                {eligibility && (
                  <div className={cn('mt-4 rounded-lg p-3 text-sm', eligibility.eligible ? 'bg-ok-wash text-ok' : 'bg-warn-wash text-warn')}>
                    <p className="font-medium">{eligibility.eligible ? 'Eligible under simulated policy' : 'Not eligible'}</p>
                    {!eligibility.eligible && <ul className="mt-1 list-inside list-disc">{eligibility.reasons.map((item) => <li key={item}>{item}</li>)}</ul>}
                  </div>
                )}
                {eligibility?.eligible && <Button disabled={checking} onClick={() => void createCase()} className="mt-4 w-full"><Check className="size-4" aria-hidden="true" /> Create simulated return</Button>}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
