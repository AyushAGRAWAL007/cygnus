import { useState } from 'react'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import { advanceSimulatedStatus, markSimulatedPickupMissed, scheduleSimulatedPickup } from '../../lib/api'
import { href } from '../../lib/router'
import type { ReturnCase } from '../../lib/types'
import { Button, LinkButton } from '../ui/Kit'

export default function SimulationControls({ c }: { c: ReturnCase }) {
  const [today] = useState(() => new Date().toISOString().slice(0, 10))
  const [pickupDate, setPickupDate] = useState(today)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function perform(action: () => Promise<unknown>) {
    setBusy(true)
    setError('')
    try {
      await action()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Simulated action failed')
    } finally {
      setBusy(false)
    }
  }

  let action: { status: string; label: string } | null = null
  if (c.stage === 'pickup' && c.pickup?.status === 'collected' && c.events.at(-1)?.title.includes('pickup completion')) action = { status: 'in_transit', label: 'Record simulated shipment in transit' }
  if (c.stage === 'in_transit') action = { status: 'delivered', label: 'Record simulated delivery' }
  if (c.stage === 'received') action = { status: 'refund_issued', label: 'Record simulated refund issuance' }

  return (
    <section aria-labelledby="sim-actions" className="rounded-xl border border-dashed border-line-strong bg-paper/60 p-5">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-mute">Demo controls</p>
      <h2 id="sim-actions" className="mt-1 font-medium">Advance the simulated workflow</h2>
      <p className="mt-1 text-sm text-ink-soft">These controls write demo events only. No retailer, courier, shipment, refund, or bank is contacted.</p>
      {c.stage === 'requested' && (
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="text-sm font-medium">Simulated pickup date
            <input type="date" min={today} value={pickupDate} onChange={(event) => setPickupDate(event.target.value)} className="mt-1 block h-10 rounded-lg border border-line-strong bg-paper px-3" />
          </label>
          <Button disabled={busy || !pickupDate} onClick={() => void perform(() => scheduleSimulatedPickup(c.id, pickupDate))}>
            {busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null} Schedule simulated pickup
          </Button>
        </div>
      )}
      {c.pickup?.status === 'scheduled' && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" disabled={busy} onClick={() => void perform(() => markSimulatedPickupMissed(c.id))}>Mark pickup missed (simulated)</Button>
          <Button disabled={busy} onClick={() => void perform(() => advanceSimulatedStatus(c.id, 'picked_up'))}>Record simulated pickup completion</Button>
        </div>
      )}
      {c.pickup?.status === 'missed' && (
        <LinkButton href={href.reschedule(c.id)} className="mt-4">Collect availability and reschedule <ArrowRight className="size-4" aria-hidden="true" /></LinkButton>
      )}
      {c.stage === 'pickup' && c.pickup?.status === 'collected' && !action && (
        <p className="mt-4 text-sm text-mute">Pickup completion is recorded. The next simulated shipment event is available after refresh.</p>
      )}
      {action && <Button disabled={busy} onClick={() => void perform(() => advanceSimulatedStatus(c.id, action!.status))} className="mt-4">{busy ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> : null}{action.label}</Button>}
      {c.health === 'completed' && <p className="mt-4 rounded-lg bg-ok-wash px-3 py-2 text-sm text-ok">Case resolved after a simulated refund-issued event. Bank credit remains unverified.</p>}
      {error && <p role="alert" className="mt-4 rounded-lg bg-bad-wash p-3 text-sm text-bad">{error}</p>}
    </section>
  )
}