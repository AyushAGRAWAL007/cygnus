import { Activity, LayoutGrid, Receipt, RotateCcw } from 'lucide-react'
import type { ReactNode } from 'react'
import { useHealth } from '../hooks/useHealth'
import { useResource } from '../hooks/useResource'
import { listReturns } from '../lib/api'
import { cn } from '../lib/format'
import { href, type Section } from '../lib/router'
import { Wordmark } from './brand/Wordmark'
import SimulatedBanner from './SimulatedBanner'
import AccountControl from './AccountControl'

const NAV: { id: Section; label: string; href: string; icon: typeof LayoutGrid }[] = [
  { id: 'overview', label: 'Overview', href: href.overview, icon: LayoutGrid },
  { id: 'orders', label: 'All Orders', href: href.orders, icon: Receipt },
  { id: 'returns', label: 'Returns & Refunds', href: href.returns, icon: RotateCcw },
  { id: 'analytics', label: 'Analytics', href: href.analytics, icon: LayoutGrid },
  { id: 'retailers', label: 'Retailers', href: href.retailers, icon: Receipt },
  { id: 'activity', label: 'Agent Activity', href: href.activity, icon: Activity },
]

function useBadges() {
  const returns = useResource('shell:returns', listReturns)
  const needs = returns.phase === 'ready' ? returns.data.filter((r) => r.health === 'needs_attention' || r.health === 'awaiting_approval').length : 0
  return { returns: needs } as Partial<Record<Section, number>>
}

function BackendStatus() {
  const h = useHealth()
  const online = h.phase === 'ready'
  return (
    <span className="flex items-center gap-2 text-xs text-mute">
      <span aria-hidden="true" className={cn('size-1.5 rounded-full', h.phase === 'loading' ? 'bg-line-strong' : online ? 'bg-ok' : 'bg-warn')} />
      {h.phase === 'loading' ? 'Checking backend' : online ? `Backend online, v${h.health.version}` : 'Backend offline'}
    </span>
  )
}

export default function AppShell({ section, children }: { section: Section; children: ReactNode }) {
  const badges = useBadges()

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="hidden border-r border-line bg-paper/60 lg:sticky lg:top-0 lg:flex lg:h-dvh lg:flex-col lg:px-5 lg:py-6">
        <a href={href.home} aria-label="Cygnus home"><Wordmark /></a>
        <nav aria-label="Workspace" className="mt-10 flex flex-col gap-0.5">
          {NAV.map((n) => {
            const active = n.id === section
            const badge = badges[n.id]
            return (
              <a
                key={n.id}
                href={n.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'group flex h-9 items-center gap-3 rounded-md px-2.5 text-sm transition-colors',
                  active ? 'bg-ink text-paper' : 'text-ink-soft hover:bg-bone hover:text-ink',
                )}
              >
                <n.icon className="size-4" aria-hidden="true" />
                <span className="flex-1">{n.label}</span>
                {!!badge && (
                  <span className={cn('num grid min-w-5 place-items-center rounded-full px-1.5 text-[11px] font-medium', active ? 'bg-paper/15 text-paper' : 'bg-warn-wash text-warn')}>
                    {badge}<span className="sr-only"> need attention</span>
                  </span>
                )}
              </a>
            )
          })}
        </nav>
        <div className="mt-auto flex flex-col gap-4 border-t border-line pt-5">
          <AccountControl />
          <SimulatedBanner />
          <BackendStatus />
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        <header className="sticky top-0 z-20 border-b border-line bg-porcelain/90 backdrop-blur lg:hidden">
          <div className="flex h-14 items-center justify-between px-4">
            <a href={href.home} aria-label="Cygnus home"><Wordmark /></a>
            <AccountControl />
          </div>
          <nav aria-label="Workspace" className="flex gap-1 overflow-x-auto px-3 pb-2">
            {NAV.map((n) => (
              <a
                key={n.id}
                href={n.href}
                aria-current={n.id === section ? 'page' : undefined}
                className={cn('flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3 text-sm', n.id === section ? 'bg-ink text-paper' : 'text-ink-soft')}
              >
                {n.label}
                {!!badges[n.id] && <span className="num text-xs text-warn">{badges[n.id]}</span>}
              </a>
            ))}
          </nav>
        </header>

        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:px-8 lg:py-12">
          <SimulatedBanner className="mb-6 lg:hidden" />
          {children}
        </main>
        <footer className="mx-auto w-full max-w-6xl px-4 pb-8 text-xs text-mute md:px-8">
          Cygnus · Nebius × NVIDIA Global AI Hackathon 2026 · Simulated retailer demo
        </footer>
      </div>
    </div>
  )
}
