const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const dayFmt = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
const dayLongFmt = new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
const shortFmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })
const timeFmt = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })

export const money = (n: number | null | undefined, currency: string | null = 'USD') => {
  if (n == null || !Number.isFinite(n)) return 'Unknown amount'
  if (!currency) return `${n.toLocaleString()} (currency unknown)`
  try { return currency === 'USD' ? usd.format(n) : new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(n) }
  catch { return `${n.toLocaleString()} ${currency}` }
}
export const day = (iso: string) => dayFmt.format(new Date(iso))
export const dayLong = (iso: string) => dayLongFmt.format(new Date(iso))
export const shortDate = (iso: string) => shortFmt.format(new Date(iso))
export const time = (iso: string) => timeFmt.format(new Date(iso))
export const dateTime = (iso: string) => `${day(iso)}, ${time(iso)}`

export function relative(iso: string, now = Date.now()): string {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60000)
  const future = minutes < 0
  const m = Math.abs(minutes)
  let text: string
  if (m < 1) return 'just now'
  if (m < 60) text = `${m} min`
  else if (m < 60 * 24) text = `${Math.round(m / 60)}h`
  else text = `${Math.round(m / 1440)}d`
  return future ? `in ${text}` : `${text} ago`
}

export function daysUntil(iso: string, now = Date.now()): number {
  return Math.ceil((new Date(iso).getTime() - now) / 86400000)
}

export const cn = (...classes: (string | false | null | undefined)[]) => classes.filter(Boolean).join(' ')


export function localDate(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
