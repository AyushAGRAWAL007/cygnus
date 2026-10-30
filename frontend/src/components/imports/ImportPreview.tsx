import { useState } from 'react'
import { Button } from '../ui/Kit'
import { confirmImport, type ImportPreview as Preview } from '../../lib/imports'
import { money } from '../../lib/format'

export default function ImportPreview({ preview, onClose }: { preview: Preview; onClose: () => void }) {
  const [selected, setSelected] = useState(() => new Set(preview.orders.filter(o => o.order.marketplace && o.order.order_date && o.order.items.length).map(o => o.key)))
  const [acknowledge, setAcknowledge] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(preview.result)
  const needsReview = preview.orders.some(o => selected.has(o.key) && (o.conflict || o.order.review_reasons.length > 0))
  async function confirm() {
    setBusy(true); setError('')
    try { setResult(await confirmImport(preview, [...selected], acknowledge)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Import failed') }
    finally { setBusy(false) }
  }
  return <section aria-labelledby="import-preview-heading" className="min-w-0 rounded-xl border border-cobalt/30 bg-paper p-5 md:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs uppercase tracking-widest text-cobalt">Review before saving</p><h2 id="import-preview-heading" className="mt-1 font-display text-3xl">Your import preview</h2></div>
      <Button variant="ghost" onClick={onClose} disabled={busy}>Close preview</Button>
    </div>
    <dl className="my-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
      {(['orders', 'items', 'valid', 'invalid', 'duplicates', 'review', 'unsupported', 'repeated_records'] as const).map(k => <div key={k} className="rounded-lg bg-bone/50 p-3"><dt className="text-xs capitalize text-mute">{k.replaceAll('_', ' ')}</dt><dd className="num mt-1 text-xl">{preview.counts[k] ?? 0}</dd></div>)}
    </dl>
    <p className="text-sm text-ink-soft">Imports are customer-provided observations, not verified Amazon API records. Unknown prices and return policies stay unknown. Existing orders keep their saved details.</p>
    <ul className="my-4 max-h-[32rem] divide-y divide-line overflow-y-auto">
      {preview.orders.map(({ key, order, duplicate, conflict }) => {
        const blocked = !order.marketplace || !order.order_date || order.items.length === 0
        return <li key={key} className="py-4">
          <label className="flex items-start gap-3">
            <input type="checkbox" checked={selected.has(key)} disabled={blocked || busy || !!result} onChange={e => setSelected(old => { const next = new Set(old); if (e.target.checked) next.add(key); else next.delete(key); return next })} className="mt-1 size-4 shrink-0 accent-cobalt" />
            <span className="min-w-0 flex-1"><span className="block break-all font-medium">{order.external_order_id}</span><span className="text-xs text-mute">{order.marketplace ?? 'Unknown marketplace'} · {order.order_date ?? 'Unknown order date'} · {order.order_status ?? 'Status unknown'}</span></span>
          </label>
          {duplicate && <p className="mt-2 text-sm text-cobalt">Already imported — add provenance and skip creating another order.</p>}
          {conflict && <p className="mt-2 text-sm text-warn">Source details differ. Saved order details will be preserved; this observation will be recorded separately.</p>}
          {blocked && <p className="mt-2 text-sm text-warn">Cannot import until a supported adapter supplies marketplace, order date and product lines.</p>}
          <ul className="mt-2 space-y-1 text-sm">{order.items.map((item, index) => <li key={index} className="flex flex-wrap justify-between gap-2"><span className="min-w-0 break-words">{item.product_name} · Qty {item.quantity ?? 'unknown'}</span><span className="num text-ink-soft">{money(item.unit_price === null ? null : Number(item.unit_price), item.currency)}</span></li>)}</ul>
          {order.review_reasons.length > 0 && <ul className="mt-2 list-inside list-disc text-xs text-warn">{order.review_reasons.map(r => <li key={r}>{r}</li>)}</ul>}
        </li>
      })}
    </ul>
    {(preview.issues.length > 0 || preview.unsupported.length > 0) && <details className="my-4 rounded-lg bg-warn-wash/50 p-3 text-sm"><summary className="cursor-pointer font-medium">Excluded records and unsupported files</summary><ul className="mt-2 space-y-2 break-words">{preview.issues.map((i, n) => <li key={n}>{i.reference}: {i.message}</li>)}{preview.unsupported.map((s, n) => <li key={n}>{s}</li>)}</ul></details>}
    {needsReview && !result && <label className="my-4 flex items-start gap-2 text-sm"><input type="checkbox" checked={acknowledge} onChange={e => setAcknowledge(e.target.checked)} className="mt-1 size-4 shrink-0 accent-cobalt" />I reviewed the unknown and conflicting fields. No return eligibility or payment is verified.</label>}
    {error && <p role="alert" className="my-3 text-sm text-bad">{error}</p>}
    {result ? <p role="status" className="rounded-lg bg-ok-wash p-4 text-sm text-ok">Import complete: {result.imported} new orders, {result.skipped} duplicates skipped, {result.failed} excluded records.</p> : <Button disabled={busy || selected.size === 0 || (needsReview && !acknowledge)} onClick={() => void confirm()}>{busy ? 'Saving orders…' : `Confirm import (${selected.size})`}</Button>}
  </section>
}
