import { cn } from '../../lib/format'
import { STAGES, stageIndex, type CaseHealth, type Stage } from '../../lib/types'
import { Star } from '../brand/Wordmark'

/**
 * A return drawn as a route across seven stars. Past stages are solid, the current stage
 * is a lit star, future stages are open rings joined by a dashed line.
 */
export function JourneyTrack({ stage, health, size = 'sm', labels = false, className }: {
  stage: Stage
  health: CaseHealth
  size?: 'sm' | 'lg'
  labels?: boolean
  className?: string
}) {
  const idx = stageIndex(stage)
  const done = health === 'completed'
  const accent = health === 'needs_attention' ? 'text-warn' : 'text-cobalt'
  const lg = size === 'lg'
  const current = STAGES[idx]

  return (
    <div className={className}>
      <p className="sr-only">
        {done ? 'Return case resolved; bank credit is not verified.' : `Stage ${idx + 1} of ${STAGES.length}: ${current.label}.`}
      </p>
      <ol className="flex items-start" aria-hidden="true">
        {STAGES.map((s, i) => {
          const past = i < idx || (done && i === idx)
          const isCurrent = i === idx && !done
          const last = i === STAGES.length - 1
          return (
            <li key={s.id} className={cn('flex min-w-0 flex-col', !last && 'flex-1')}>
              <div className={cn('flex items-center', lg ? 'h-6' : 'h-4')}>
                <span className={cn('relative grid place-items-center', lg ? 'size-6' : 'size-4')}>
                  {isCurrent ? (
                    <>
                      <span className={cn('halo absolute inset-0 rounded-full bg-current opacity-30', accent)} />
                      <Star className={cn('relative', accent, lg ? 'size-5' : 'size-3.5')} />
                    </>
                  ) : past ? (
                    <span className={cn('rounded-full bg-ink', lg ? 'size-2' : 'size-1.5')} />
                  ) : (
                    <span className={cn('rounded-full border border-line-strong bg-paper', lg ? 'size-2' : 'size-1.5')} />
                  )}
                </span>
                {!last && (
                  <span className={cn('mx-0.5 flex-1', i < idx || done ? 'h-px bg-ink/70' : 'border-t border-dashed border-line-strong')} />
                )}
              </div>
              {labels && (
                <span className={cn(
                  'mt-2 truncate pr-2 text-[11px] leading-tight',
                  isCurrent ? cn('font-medium', health === 'needs_attention' ? 'text-warn' : 'text-ink') : past ? 'text-ink-soft' : 'text-mute',
                )}>
                  {s.short}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
