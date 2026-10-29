import { href } from '../../lib/router'
import { dateTime, relative } from '../../lib/format'
import type { ActivityEvent } from '../../lib/types'
import { EvidenceTag } from '../ui/Evidence'

export default function EventItem({ event, showCase = true }: { event: ActivityEvent; showCase?: boolean }) {
  return (
    <li className="flex gap-4 px-4 py-4 md:px-5">
      <span className="mt-1.5 size-2 shrink-0 rounded-full bg-cobalt" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <EvidenceTag status={event.evidence} source={event.source} />
          {showCase && <a href={href.return(event.caseId)} className="num text-mute underline-offset-2 hover:text-ink hover:underline">{event.caseId}</a>}
          <time className="text-mute" dateTime={event.at}>{relative(event.at)}</time>
        </div>
        <p className="mt-1 font-medium">{event.title}</p>
        {event.detail && <p className="mt-0.5 text-sm text-ink-soft text-pretty">{event.detail}</p>}
        <p className="mt-1 text-[11px] text-mute">{dateTime(event.at)} · SIMULATED EVENT</p>
      </div>
    </li>
  )
}