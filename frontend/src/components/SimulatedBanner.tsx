import { cn } from '../lib/format'

/** Always-visible reminder that the demo uses a simulated retailer, not real orders or refunds. */
export default function SimulatedBanner({ className }: { className?: string }) {
  return (
    <p className={cn('flex items-center gap-2.5 text-xs text-ink-soft', className)}>
      <span aria-hidden="true" className="hatch inline-block h-3 w-5 shrink-0 rounded-[2px] text-cobalt/60 ring-1 ring-cobalt/30" />
      <span>
        <span className="font-medium text-cobalt-deep">Know the source.</span>{' '}
        SIM marks demo data. Imported purchases are unverified. Pickup and refund actions remain simulated.
      </span>
    </p>
  )
}
