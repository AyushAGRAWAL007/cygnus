import { cn } from '../../lib/format'

/** The Northern Cross asterism of Cygnus: Deneb (top, accented), Sadr, Albireo, and the two wing stars. */
export function CygnusMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <g stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.5">
        <line x1="16" y1="4.5" x2="16" y2="13" />
        <line x1="16" y1="13" x2="15" y2="28" />
        <line x1="5" y1="17" x2="16" y2="13" />
        <line x1="16" y1="13" x2="27" y2="9" />
      </g>
      <circle cx="16" cy="13" r="1.6" fill="currentColor" />
      <circle cx="15" cy="28" r="1.4" fill="currentColor" />
      <circle cx="5" cy="17" r="1.4" fill="currentColor" />
      <circle cx="27" cy="9" r="1.4" fill="currentColor" />
      <circle cx="16" cy="4.5" r="2.4" fill="var(--color-cobalt)" />
    </svg>
  )
}

export function Wordmark({ className, tone = 'ink' }: { className?: string; tone?: 'ink' | 'paper' }) {
  return (
    <span className={cn('inline-flex items-center gap-2', tone === 'paper' ? 'text-paper' : 'text-ink', className)}>
      <CygnusMark className="size-7" />
      <span className="font-display text-[1.65rem] leading-none tracking-tight">Cygnus</span>
    </span>
  )
}

/** Four-point star used to mark the current stage on a return route. */
export function Star({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <path d="M12 0 13.6 10.4 24 12 13.6 13.6 12 24 10.4 13.6 0 12 10.4 10.4Z" fill="currentColor" />
    </svg>
  )
}
