import { Feather } from 'lucide-react'

export type Route = 'home' | 'dashboard'

export default function Nav({ route }: { route: Route }) {
  const link = (r: Route, label: string, href: string) => (
    <a
      href={href}
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
        route === r ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:text-ink'
      }`}
    >
      {label}
    </a>
  )
  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
        <a href="#/" className="flex items-center gap-2 font-semibold">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-700 text-white">
            <Feather size={18} />
          </span>
          Cygnus
        </a>
        <nav className="flex items-center gap-1">
          {link('home', 'Home', '#/')}
          {link('dashboard', 'Dashboard', '#/dashboard')}
        </nav>
      </div>
    </header>
  )
}
