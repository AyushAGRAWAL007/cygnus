import { ArrowRight } from 'lucide-react'
import { href } from '../lib/router'
import { Wordmark } from './brand/Wordmark'
import { LinkButton } from './ui/Kit'

/** Top navigation for the public landing page. The workspace uses AppShell instead. */
export default function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-porcelain/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5 md:px-8">
        <a href={href.home} aria-label="Cygnus home"><Wordmark /></a>
        <nav aria-label="Main" className="flex items-center gap-1 text-sm">
          <a href="#how" className="hidden rounded-full px-3 py-2 text-ink-soft hover:text-ink sm:block">How it works</a>
          <a href="#evidence" className="hidden rounded-full px-3 py-2 text-ink-soft hover:text-ink sm:block">Evidence</a>
          <LinkButton href={href.overview} size="sm" className="ml-2">
            Open workspace <ArrowRight className="size-3.5" aria-hidden="true" />
          </LinkButton>
        </nav>
      </div>
    </header>
  )
}
