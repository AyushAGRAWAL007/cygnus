import { ImageOff, LoaderCircle, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../lib/format'
import { CygnusMark } from '../brand/Wordmark'

export function ProductThumb({ src, alt, size = 'md', className }: { src?: string; alt: string; size?: 'xs' | 'sm' | 'md' | 'fill'; className?: string }) {
  const s = { xs: 'size-8', sm: 'size-11', md: 'size-14', fill: 'w-full' }[size]
  return (
    <span className={cn('block aspect-square shrink-0 overflow-hidden rounded-md bg-bone ring-1 ring-line', s, className)}>
      {src ? <img src={src} alt={alt} loading="lazy" className="size-full object-cover" /> : <span className="grid size-full place-items-center text-mute" aria-label={alt || 'No product image available'}><ImageOff className="size-5" aria-hidden="true" /></span>}
    </span>
  )
}

export function PageHeader({ eyebrow, title, children, actions }: { eyebrow?: ReactNode; title: ReactNode; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-col gap-4 border-b border-line pb-6 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        {eyebrow && <p className="text-xs font-medium uppercase tracking-[0.14em] text-mute">{eyebrow}</p>}
        <h1 className="mt-2 font-display text-4xl leading-[1.05] tracking-tight text-balance md:text-5xl">{title}</h1>
        {children && <div className="mt-3 text-pretty text-ink-soft">{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  )
}

export function SectionTitle({ children, aside, id }: { children: ReactNode; aside?: ReactNode; id?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <h2 id={id} className="text-xs font-medium uppercase tracking-[0.14em] text-mute">{children}</h2>
      {aside}
    </div>
  )
}

type BtnProps = { variant?: 'primary' | 'secondary' | 'ghost'; size?: 'sm' | 'md'; className?: string; children: ReactNode }
const btn = (variant: BtnProps['variant'] = 'primary', size: BtnProps['size'] = 'md') =>
  cn(
    'inline-flex items-center justify-center gap-2 rounded-full font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
    size === 'sm' ? 'h-8 px-3.5 text-sm' : 'h-10 px-5 text-sm',
    variant === 'primary' && 'bg-ink text-paper hover:bg-cobalt-deep',
    variant === 'secondary' && 'border border-line-strong bg-paper text-ink hover:border-ink',
    variant === 'ghost' && 'text-ink-soft hover:bg-bone hover:text-ink',
  )

export function Button({ variant, size, className, children, ...rest }: BtnProps & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" className={cn(btn(variant, size), className)} {...rest}>{children}</button>
}

export function LinkButton({ variant, size, className, children, ...rest }: BtnProps & React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a className={cn(btn(variant, size), className)} {...rest}>{children}</a>
}

export function Loading({ label = 'Loading', rows = 4 }: { label?: string; rows?: number }) {
  return (
    <div role="status" className="flex flex-col gap-3 py-6">
      <span className="flex items-center gap-2 text-sm text-mute">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> {label}
      </span>
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} className="h-12 animate-pulse rounded-md bg-bone/70" style={{ opacity: 1 - i * 0.18 }} />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-lg border border-bad/25 bg-bad-wash/60 p-5">
      <p className="text-sm font-medium text-bad">{"Couldn't load this"}</p>
      <p className="text-sm text-ink-soft">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw className="size-3.5" aria-hidden="true" /> Try again
        </Button>
      )}
    </div>
  )
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <CygnusMark className="size-10 text-line-strong" />
      <p className="font-display text-2xl">{title}</p>
      {children && <p className="max-w-sm text-sm text-mute">{children}</p>}
      {action}
    </div>
  )
}

export function Segmented<T extends string>({ value, onChange, options, label }: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string; count?: number }[]
  label: string
}) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto rounded-full border border-line bg-paper p-1">
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-sm transition-colors',
              active ? 'bg-ink text-paper' : 'text-ink-soft hover:bg-bone hover:text-ink',
            )}
          >
            {o.label}
            {o.count !== undefined && <span className={cn('num text-xs', active ? 'text-paper/70' : 'text-mute')}>{o.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
