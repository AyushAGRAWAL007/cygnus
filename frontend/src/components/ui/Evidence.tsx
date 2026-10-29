import { cn } from '../../lib/format'
import type { CaseHealth, Evidence, Source } from '../../lib/types'
import { EVIDENCE_COPY } from './evidenceData'

export function EvidenceGlyph({ status, className }: { status: Evidence | 'not_started'; className?: string }) {
  const base = 'inline-block shrink-0 rounded-full'
  switch (status) {
    case 'confirmed':
      return <span aria-hidden="true" className={cn(base, 'size-2 bg-ok', className)} />
    case 'recorded':
      return <span aria-hidden="true" className={cn(base, 'size-2 bg-cobalt', className)} />
    case 'pending':
      return <span aria-hidden="true" className={cn(base, 'size-2 border-[1.5px] border-warn', className)} />
    case 'unverified':
      return <span aria-hidden="true" className={cn(base, 'size-2 border-[1.5px] border-dashed border-mute', className)} />
    case 'failed':
      return <span aria-hidden="true" className={cn('inline-block size-2 shrink-0 rotate-45 bg-bad', className)} />
    default:
      return <span aria-hidden="true" className={cn(base, 'size-2 border border-line-strong', className)} />
  }
}

const tone: Record<Evidence, string> = {
  recorded: 'text-cobalt',
  confirmed: 'text-ok',
  pending: 'text-warn',
  unverified: 'text-mute',
  failed: 'text-bad',
  not_started: 'text-mute',
}

/** Evidence status, with an explicit SIM marker when the record came from the simulated retailer. */
export function EvidenceTag({ status, source, className }: { status: Evidence | 'not_started'; source?: Source; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em]', tone[status], className)} title={EVIDENCE_COPY[status].meaning}>
      <EvidenceGlyph status={status} />
      {EVIDENCE_COPY[status].label}
      {source === 'simulated' && <SimTag />}
    </span>
  )
}

export function SimTag({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-[3px] border border-cobalt/30 px-1 py-px text-[10px] font-medium tracking-[0.08em] text-cobalt', className)} title="From the simulated retailer. Not a real-world record.">
      <span aria-hidden="true" className="hatch inline-block size-2 rounded-[1px] text-cobalt/70" />
      SIM
      <span className="sr-only">ulated data</span>
    </span>
  )
}

const HEALTH: Record<CaseHealth, { label: string; cls: string }> = {
  needs_attention: { label: 'Needs you', cls: 'bg-warn-wash text-warn' },
  awaiting_approval: { label: 'Your decision', cls: 'bg-cobalt-wash text-cobalt-deep' },
  on_track: { label: 'On track', cls: 'bg-bone text-ink-soft' },
  completed: { label: 'Completed', cls: 'bg-ok-wash text-ok' },
}

export function HealthPill({ health, className }: { health: CaseHealth; className?: string }) {
  const h = HEALTH[health]
  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap', h.cls, className)}>
      {h.label}
    </span>
  )
}
