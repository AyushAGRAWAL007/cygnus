import { useRef, useState } from 'react'
import { Mail, Upload } from 'lucide-react'
import { useResource } from '../../hooks/useResource'
import { notifyChange } from '../../lib/api'
import { connectGmail, disconnectGmail, fetchGmailStatus, fetchImportHistory, syncGmail, uploadAmazon, type ImportPreview as Preview } from '../../lib/imports'
import { shortDate } from '../../lib/format'
import { Button, ErrorState, Loading } from '../ui/Kit'
import ImportPreview from './ImportPreview'

export default function ImportHub() {
  const gmail = useResource('gmail-status', fetchGmailStatus)
  const history = useResource('import-history', fetchImportHistory)
  const picker = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState('')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [dragging, setDragging] = useState(false)
  async function upload(file?: File) {
    if (!file || busy) return
    setError(''); setNotice('')
    if (!file.size || file.size > 10 * 1024 * 1024) { setError('Choose a nonempty file of at most 10 MiB.'); return }
    setBusy('upload'); setProgress(0); setPreview(null)
    try { setPreview(await uploadAmazon(file, setProgress)) }
    catch (e) { setError(e instanceof Error ? e.message : 'Upload failed') }
    finally { setBusy(''); if (picker.current) picker.current.value = '' }
  }
  async function gmailAction(action: 'connect' | 'sync' | 'disconnect') {
    if (busy) return
    setBusy(action); setError(''); setNotice('')
    try {
      if (action === 'connect') {
        const data = await connectGmail()
        window.location.assign(data.authorization_url)
      } else if (action === 'sync') {
        const data = await syncGmail()
        setPreview(data.preview)
        const outcomes = [typeof data.extracted === 'number' ? `${data.extracted} extracted` : '', typeof data.unsupported === 'number' ? `${data.unsupported} unsupported formats` : ''].filter(Boolean).join(' ? ')
        const empty = data.processed === 0 ? ' No new candidate messages were checked on this page. This does not prove that the mailbox has no purchases; messages may fall outside the search window, have been checked already, or use unrecognized senders.' : ''
        setNotice(`${data.processed} messages checked.${outcomes ? ` ${outcomes}.` : ''}${empty} ${data.preview ? 'Review and confirm the preview to save orders. ' : 'No import preview is available. '}${data.has_more ? 'More results are available; sync the next page after reviewing any preview.' : 'This sync page is complete.'}`)
      } else {
        await disconnectGmail(); setPreview(p => p?.source === 'gmail' ? null : p)
        setNotice('Gmail disconnected and Google access revoked. Previously confirmed orders remain in your history.')
      }
      notifyChange()
    } catch (e) { setError(e instanceof Error ? e.message : 'Gmail action failed'); gmail.retry() }
    finally { setBusy('') }
  }
  const connected = gmail.phase === 'ready' && gmail.data.status === 'connected'
  return <div className="flex min-w-0 flex-col gap-5">
    <div className="grid min-w-0 gap-4 lg:grid-cols-2">
      <section aria-labelledby="amazon-import-heading" className="min-w-0 rounded-xl border border-line bg-paper p-5 md:p-6">
        <Upload className="size-5 text-cobalt" aria-hidden="true" /><h2 id="amazon-import-heading" className="mt-3 font-display text-2xl">Import Amazon orders</h2>
        <p className="mt-2 text-sm text-ink-soft">Upload a ZIP, JSON or CSV to review before saving. Amazon.in export layouts vary; only recognized adapters can be parsed. The current interchange adapter is experimental and needs a real redacted export for compatibility verification.</p>
        <div onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files[0]) }} className={`mt-4 flex min-h-32 flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-4 text-center ${dragging ? 'border-cobalt bg-cobalt-wash' : 'border-line-strong bg-bone/20'}`}>
          <p className="text-sm text-mute">Drop one file here · maximum 10 MiB</p>
          <input ref={picker} type="file" accept=".zip,.json,.csv" aria-label="Amazon order file" className="sr-only" onChange={e => void upload(e.target.files?.[0])} disabled={!!busy} />
          <Button variant="secondary" disabled={!!busy} onClick={() => picker.current?.click()}>Choose Amazon file</Button>
        </div>
        {busy === 'upload' && <div role="status" className="mt-3 text-sm text-mute"><p>{progress < 100 ? `Uploading: ${progress}%` : 'Upload complete. Parsing and validating…'}</p><progress aria-label="Upload progress" value={progress} max={100} className="mt-2 w-full accent-cobalt" /></div>}
        <details className="mt-3 text-xs text-mute"><summary className="cursor-pointer">Supported interchange format</summary><p className="mt-2 break-words">JSON: format = cygnus-amazon-v1, orders array. CSV: Order ID, Order Date, Product Name, Quantity, Unit Price, Currency, Marketplace, ASIN. Use ISO dates and decimal unit prices. These are documented Cygnus fields, not a claim about Amazon.in’s export schema.</p></details>
      </section>
      <section aria-labelledby="gmail-heading" className="min-w-0 rounded-xl border border-line bg-paper p-5 md:p-6">
        <Mail className="size-5 text-cobalt" aria-hidden="true" /><h2 id="gmail-heading" className="mt-3 font-display text-2xl">Connect Gmail</h2>
        <p className="mt-2 text-sm text-ink-soft">With your consent, Cygnus searches candidate shopping metadata from Amazon, Flipkart, Myntra, Meesho and Ajio using Gmail read-only access. Only the tested Amazon extraction adapter fetches message bodies; other retailer formats remain metadata-only and unsupported for extraction. Google grants mailbox-wide read permission. Cygnus cannot send, change or delete email.</p>
        <p className="mt-2 text-xs text-mute">Test-user integration; Google public verification is not claimed. Only extracted fields, minimal candidate metadata and message IDs are retained. Gmail data is not sent to the AI provider. Initial search covers the last year; sync runs when you choose it.</p>
        {gmail.phase === 'loading' && <Loading rows={0} label="Checking Gmail connection" />}
        {gmail.phase === 'error' && <div className="mt-3"><ErrorState message={gmail.message} onRetry={gmail.retry} /></div>}
        {gmail.phase === 'ready' && <>
          <div className="my-4 rounded-lg bg-bone/40 p-3 text-sm"><p className="break-all font-medium">{connected ? gmail.data.account_email : gmail.data.status === 'disconnected' ? 'Not connected' : gmail.data.status.replaceAll('_', ' ')}</p><p className="mt-1 text-xs text-mute">Last successful sync: {gmail.data.last_sync_at ? new Date(gmail.data.last_sync_at).toLocaleString() : 'Never'}</p>{gmail.data.error_code && <p className="mt-1 text-xs text-warn">Previous operation needs attention: {gmail.data.error_code.replaceAll('_', ' ')}. Retry or reconnect.</p>}</div>
          <div className="flex flex-wrap gap-2">
            {connected ? <Button disabled={!!busy} onClick={() => void gmailAction('sync')}>{busy === 'sync' ? 'Checking shopping messages…' : gmail.data.has_more ? 'Sync next page' : 'Sync Gmail'}</Button> : gmail.data.status !== 'revocation_pending' && <Button disabled={!!busy} onClick={() => void gmailAction('connect')}>{busy === 'connect' ? 'Opening Google…' : 'Connect Gmail with Google'}</Button>}
            {gmail.data.status !== 'disconnected' && <Button variant="secondary" disabled={!!busy} onClick={() => void gmailAction('disconnect')}>{busy === 'disconnect' ? 'Revoking access…' : gmail.data.status === 'revocation_pending' ? 'Retry disconnect' : 'Disconnect Gmail'}</Button>}
          </div>
        </>}
      </section>
    </div>
    {error && <ErrorState message={error} />}
    {notice && <p role="status" className="rounded-lg bg-cobalt-wash p-4 text-sm text-ink-soft">{notice}</p>}
    {preview && <ImportPreview key={preview.id} preview={preview} onClose={() => setPreview(null)} />}
    <details className="min-w-0 rounded-xl border border-line bg-paper p-5"><summary className="cursor-pointer font-medium">Import history</summary>
      {history.phase === 'loading' && <Loading rows={1} label="Loading import history" />}
      {history.phase === 'error' && <div className="mt-3"><ErrorState message={history.message} onRetry={history.retry} /></div>}
      {history.phase === 'ready' && (history.data.items.length ? <ul className="mt-3 divide-y divide-line">{history.data.items.map(h => <li key={h.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><div><p className="font-medium">{h.source === 'gmail' ? 'Gmail' : 'Amazon file'} · {shortDate(h.created_at)}</p><p className="text-xs text-mute">{h.status.replaceAll('_', ' ')}</p></div><p className="text-xs text-ink-soft">{h.imported_count} imported · {h.skipped_count} duplicates · {h.error_count} failed</p></li>)}</ul> : <p className="mt-3 text-sm text-mute">No confirmed imports yet.</p>)}
    </details>
  </div>
}
