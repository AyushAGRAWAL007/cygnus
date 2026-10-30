import { useState } from 'react'
import { LoaderCircle, MessageCircle, RefreshCw, Send } from 'lucide-react'
import { askAssistant, listOrders, type AssistantReply, type AssistantRequest } from '../../lib/api'
import type { ReturnCase } from '../../lib/types'
import { useResource } from '../../hooks/useResource'
import { useHealth } from '../../hooks/useHealth'
import { ErrorState } from '../ui/Kit'

interface Turn {
  id: number
  question: string
  reply: AssistantReply
}

export default function AssistantPanel({ cases }: { cases: ReturnCase[] }) {
  const orders = useResource('assistant:orders', listOrders)
  const health = useHealth()
  const [context, setContext] = useState('')
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [pendingRequest, setPendingRequest] = useState<AssistantRequest | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const aiUnavailable = health.phase === 'ready' && (!health.health.nvidia || !health.health.nvidia.configured)

  async function send(request: AssistantRequest) {
    if (aiUnavailable) return
    setPendingRequest(request)
    setBusy(true)
    setError('')
    try {
      const reply = await askAssistant(request)
      setTurns((current) => [...current, { id: Date.now(), question: request.message, reply }])
      setPendingRequest(null)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'The AI assistant could not respond.')
    } finally {
      setBusy(false)
    }
  }

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const question = message.trim()
    if (!question || busy) return
    const request: AssistantRequest = { message: question }
    if (context.startsWith('case:')) request.case_id = context.slice('case:'.length)
    if (context.startsWith('order:')) request.order_id = context.slice('order:'.length)
    setMessage('')
    void send(request)
  }

  return (
    <section aria-labelledby="assistant-title" className="flex flex-col gap-4">
      <header className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-cobalt-wash text-cobalt"><MessageCircle className="size-4" aria-hidden="true" /></span>
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-mute">NVIDIA AI · Read only</p>
          <h2 id="assistant-title" className="mt-1 font-display text-3xl">Ask Cygnus</h2>
          <p className="mt-1 max-w-2xl text-sm text-ink-soft">Get an explanation grounded in backend records. The assistant cannot change return state; simulated facts are not real retailer or bank confirmations.</p>
        </div>
      </header>

      <div className="overflow-hidden rounded-xl border border-line bg-paper/60">
        <div aria-live="polite" className="flex max-h-[28rem] min-h-36 flex-col gap-4 overflow-y-auto p-4 md:p-5">
          {turns.length === 0 && !busy && (
            <div className="m-auto max-w-md py-5 text-center">
              <p className="font-display text-xl">Ask about eligibility, a case status, recorded events, or the next permitted step.</p>
              <p className="mt-2 text-xs text-mute">Select an order or case for specific facts. No data is sent until you submit a question.</p>
            </div>
          )}
          {aiUnavailable && <p role="status" className="rounded-lg border border-warn/30 bg-warn-wash/60 p-3 text-sm text-ink-soft">NVIDIA AI is unavailable because its server-side key is not configured. Orders and return management remain available.</p>}
          {turns.map((turn) => (
            <article key={turn.id} className="flex flex-col gap-3">
              <p className="ml-auto max-w-[90%] rounded-xl rounded-br-sm bg-ink px-4 py-3 text-sm text-paper">{turn.question}</p>
              <div className="max-w-[95%] rounded-xl rounded-bl-sm border border-line bg-paper p-4">
                <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-cobalt">AI-generated explanation · {turn.reply.model}</p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink">{turn.reply.answer}</p>
                <div className="mt-4 border-t border-line pt-3">
                  <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-mute">{turn.reply.data_source === 'imported' ? 'Imported facts · unverified' : 'Backend-recorded simulated facts'}</p>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-ink-soft">
                    {turn.reply.facts.map((fact, index) => <li key={`${turn.id}-${index}`}>{fact}</li>)}
                  </ul>
                </div>
              </div>
            </article>
          ))}
          {busy && <p role="status" className="flex items-center gap-2 text-sm text-mute"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" /> Asking NVIDIA AI…</p>}
          {error && (
            <div role="alert" className="rounded-lg border border-bad/25 bg-bad-wash/60 p-4">
              <ErrorState message={error} />
              {pendingRequest && <button onClick={() => void send(pendingRequest)} className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-bad underline"><RefreshCw className="size-3.5" aria-hidden="true" /> Retry message</button>}
            </div>
          )}
        </div>

        <form onSubmit={submit} className="border-t border-line bg-paper p-3 md:p-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <label htmlFor="assistant-context" className="text-xs font-medium text-mute">Context record</label>
            <select id="assistant-context" value={context} onChange={(event) => setContext(event.target.value)} className="h-9 min-w-48 rounded-lg border border-line-strong bg-paper px-3 text-xs text-ink">
              <option value="">General policy / no record</option>
              {cases.length > 0 && <optgroup label="Return cases">{cases.map((item) => <option key={item.id} value={`case:${item.id}`}>{item.id} · {item.product.name}</option>)}</optgroup>}
              {orders.phase === 'ready' && orders.data.length > 0 && <optgroup label="Orders">{orders.data.map((item) => <option key={item.id} value={`order:${item.id}`}>{item.id} · {item.retailer}</option>)}</optgroup>}
            </select>
            {orders.phase === 'loading' && <span className="text-xs text-mute">Loading order choices…</span>}
            {orders.phase === 'error' && <button type="button" onClick={orders.retry} className="text-xs text-bad underline">Could not load orders; retry</button>}
          </div>
          <div className="flex items-end gap-2">
            <label className="sr-only" htmlFor="assistant-message">Message Cygnus AI</label>
            <textarea id="assistant-message" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={2000} rows={2} placeholder="Ask a question about this simulated return…" className="min-h-11 min-w-0 flex-1 resize-y rounded-lg border border-line-strong bg-white px-3 py-2 text-sm placeholder:text-mute focus:border-cobalt focus:outline-none" />
            <button type="submit" disabled={busy || aiUnavailable || !message.trim()} title={aiUnavailable ? 'NVIDIA AI is unavailable' : 'Send message'} className="grid size-10 shrink-0 place-items-center rounded-full bg-ink text-paper hover:bg-cobalt-deep disabled:cursor-not-allowed disabled:opacity-50"><Send className="size-4" aria-hidden="true" /></button>
          </div>
          <p className="mt-2 text-[11px] text-mute">Maximum 2,000 characters · Responses are suggestions; backend facts and workflow rules are authoritative.</p>
        </form>
      </div>
    </section>
  )
}
