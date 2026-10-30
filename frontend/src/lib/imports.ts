import { ApiError, notifyChange, requestJson } from './api'

export interface NormalizedItem { product_name: string; product_identifier: string | null; quantity: number | null; unit_price: string | null; currency: string | null }
export interface NormalizedOrder { external_order_id: string; marketplace: string | null; order_date: string | null; currency: string | null; order_status: string | null; items: NormalizedItem[]; review_reasons: string[] }
export interface ImportResult { imported: number; skipped: number; failed: number; status: string }
export interface ImportPreview {
  id: string; source: string; expires_at: string
  counts: Record<string, number>
  orders: { key: string; order: NormalizedOrder; duplicate: boolean; conflict: boolean }[]
  issues: { reference: string; code: string; message: string }[]; unsupported: string[]; result: ImportResult | null
}
export interface ImportHistory { id: string; source: string; status: string; imported_count: number; skipped_count: number; error_count: number; created_at: string }
export interface GmailStatus { status: string; account_email: string | null; last_sync_at: string | null; has_more: boolean; error_code: string | null }

export const fetchImportHistory = () => requestJson<{ items: ImportHistory[] }>('/api/imports/history')
export const fetchGmailStatus = () => requestJson<GmailStatus>('/api/integrations/gmail')
export const connectGmail = () => requestJson<{ authorization_url: string }>('/api/integrations/gmail/authorize', { method: 'POST', body: '{}' })
export const syncGmail = () => requestJson<{ preview: ImportPreview | null; processed: number; extracted?: number; unsupported?: number; has_more: boolean }>('/api/integrations/gmail/sync', { method: 'POST', body: '{}' })
export const disconnectGmail = () => requestJson('/api/integrations/gmail/disconnect', { method: 'POST', body: '{}' })
export async function confirmImport(preview: ImportPreview, orderKeys: string[], acknowledge: boolean) {
  const result = await requestJson<ImportResult>(`/api/imports/${preview.id}/confirm`, { method: 'POST', body: JSON.stringify({ order_keys: orderKeys, acknowledge_review: acknowledge }) })
  notifyChange()
  return result
}

// XHR exposes actual upload progress. Parsing remains indeterminate until the
// server returns; a timer would falsely imply measurable parsing progress.
export function uploadAmazon(file: File, progress: (percent: number) => void): Promise<ImportPreview> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const base = import.meta.env.VITE_API_BASE_URL ?? ''
    xhr.open('POST', `${base}/api/imports/amazon/preview`)
    xhr.withCredentials = true
    xhr.timeout = 60000
    xhr.setRequestHeader('Content-Type', 'application/octet-stream')
    xhr.setRequestHeader('X-Cygnus-CSRF', '1')
    xhr.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100)) }
    xhr.onerror = () => reject(new Error('Upload failed. Check your connection and retry.'))
    xhr.ontimeout = () => reject(new Error('Upload timed out. Please retry.'))
    xhr.onload = () => {
      if (xhr.status === 401) window.dispatchEvent(new Event('cygnus:unauthorized'))
      try {
        const body = JSON.parse(xhr.responseText)
        if (xhr.status >= 200 && xhr.status < 300) resolve(body)
        else reject(new ApiError(typeof body.detail === 'string' ? body.detail : 'Upload could not be parsed.', xhr.status))
      } catch { reject(new Error('The server returned an invalid response.')) }
    }
    xhr.send(file)
  })
}
