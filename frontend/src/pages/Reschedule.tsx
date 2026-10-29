import { ArrowLeft, CalendarClock, Check, LoaderCircle } from 'lucide-react'
import { useState } from 'react'
import { EmptyState, ErrorState, LinkButton, Loading, ProductThumb } from '../components/ui/Kit'
import { useResource } from '../hooks/useResource'
import { getReturn, recordCustomerAvailability, rescheduleSimulatedPickup } from '../lib/api'
import { cn } from '../lib/format'
import { href } from '../lib/router'

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-4 border-t border-line pt-6">
      <legend className="float-left flex items-baseline gap-3 p-0">
        <span className="num font-display text-2xl text-mute">{String(n).padStart(2, '0')}</span>
        <span className="font-medium">{title}</span>
      </legend>
      <div className="clear-both">{children}</div>
    </fieldset>
  )
}

export default function Reschedule({ id }: { id: string }) {
  const res = useResource(`return:${id}`, () => getReturn(id))
  const [today] = useState(() => new Date().toISOString().slice(0, 10))
  const [availability, setAvailability] = useState('')
  const [pickupDate, setPickupDate] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  if (res.phase === 'loading') return <Loading label="Loading pickup details" />
  if (res.phase === 'error') return <ErrorState message={res.message} onRetry={res.retry} />
  const c = res.data

  if (c.backendStatus !== 'missed_pickup' && c.backendStatus !== 'availability_collected') {
    return (
      <EmptyState title="Nothing to reschedule" action={<LinkButton href={href.return(c.id)} variant="secondary" size="sm">Back to the return</LinkButton>}>
        This simulated case has no missed pickup waiting for a new date.
      </EmptyState>
    )
  }

  const hasAvailability = c.backendStatus === 'availability_collected'
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      if (hasAvailability) {
        await rescheduleSimulatedPickup(c.id, pickupDate)
        setSent(true)
      } else {
        await recordCustomerAvailability(c.id, availability.trim())
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not update this simulated pickup.')
    } finally {
      setSubmitting(false)
    }
  }

  if (sent) {
    return (
      <div className="mx-auto flex max-w-xl flex-col items-start gap-5 py-6">
        <span className="grid size-12 place-items-center rounded-full bg-ok-wash text-ok"><Check className="size-6" aria-hidden="true" /></span>
        <div aria-live="polite">
          <h1 className="font-display text-4xl leading-tight text-balance">Simulated reschedule recorded.</h1>
          <p className="mt-2 text-ink-soft text-pretty">The backend saved the new date and customer availability. No courier was contacted, and no pickup is confirmed.</p>
        </div>
        <LinkButton href={href.return(c.id)}>Back to the return</LinkButton>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <a href={href.return(c.id)} className="inline-flex w-fit items-center gap-1.5 text-sm text-ink-soft hover:text-ink"><ArrowLeft className="size-4" aria-hidden="true" /> {c.id}</a>
      <header className="flex flex-col gap-4 border-b border-line pb-6 md:flex-row md:items-end md:justify-between">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-warn">Simulated missed pickup</p>
          <h1 className="mt-2 font-display text-4xl leading-tight text-balance md:text-5xl">{hasAvailability ? 'Choose a new pickup date.' : 'When are you available?'}</h1>
          <p className="mt-3 text-ink-soft text-pretty">{hasAvailability ? 'Your availability is saved in this demo. Select a date to record the reschedule.' : 'Record availability before choosing a new simulated pickup date.'}</p>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-line bg-paper p-3">
          <ProductThumb src={c.product.image} alt={c.product.image ? c.product.name : ''} size="sm" />
          <div className="min-w-0 text-sm"><p className="truncate font-medium">{c.product.name}</p><p className="truncate text-xs text-mute">{c.orderId} · SIM</p></div>
        </div>
      </header>

      <form onSubmit={submit} className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <Step n={1} title="Customer availability">
            {hasAvailability ? (
              <p className="flex items-center gap-2 text-sm text-ok"><Check className="size-4" aria-hidden="true" /> Recorded availability: {c.availability || 'saved'}.</p>
            ) : (
              <label className="block text-sm font-medium">When are you usually available?
                <input required minLength={3} maxLength={200} value={availability} onChange={(event) => setAvailability(event.target.value)} placeholder="Weekdays after 5 PM" className="mt-1 block h-11 w-full rounded-lg border border-line bg-paper px-4 text-sm placeholder:text-mute focus:border-ink focus:outline-none" />
              </label>
            )}
          </Step>
          {hasAvailability && (
            <Step n={2} title="Choose a new simulated date">
              <label className="block max-w-sm text-sm font-medium">Pickup date
                <span className="relative mt-1 block"><CalendarClock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-mute" aria-hidden="true" /><input required type="date" min={today} value={pickupDate} onChange={(event) => setPickupDate(event.target.value)} className="h-11 w-full rounded-lg border border-line bg-paper pl-10 pr-3 text-sm focus:border-ink focus:outline-none" /></span>
              </label>
            </Step>
          )}
          {error && <p role="alert" className="rounded-lg bg-bad-wash p-3 text-sm text-bad">{error}</p>}
        </div>
        <aside className="lg:sticky lg:top-8 lg:self-start">
          <div className="flex flex-col gap-4 rounded-xl border border-line bg-paper p-5">
            <p className="text-xs font-medium uppercase tracking-[0.14em] text-mute">Simulated request</p>
            <p className="flex items-center gap-2 text-sm text-ink-soft"><span className={cn('size-2 rounded-full', hasAvailability ? 'bg-ok' : 'bg-warn')} />{hasAvailability ? 'Availability recorded; no courier is contacted.' : 'Waiting for customer availability.'}</p>
            <p className="text-xs text-mute">This form updates demo data only. No pickup slots or courier service are connected.</p>
            <button type="submit" disabled={submitting || (hasAvailability ? !pickupDate : availability.trim().length < 3)} className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-ink px-5 text-sm font-medium text-paper hover:bg-cobalt-deep disabled:cursor-not-allowed disabled:opacity-50">
              {submitting && <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />}
              {hasAvailability ? 'Record simulated reschedule' : 'Save simulated availability'}
            </button>
            <LinkButton href={href.return(c.id)} variant="secondary" size="sm">Back to return</LinkButton>
          </div>
        </aside>
      </form>
    </div>
  )
}
