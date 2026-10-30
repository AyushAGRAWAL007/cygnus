import { notifyChange, requestJson } from './api'

export interface Refund { id: string; amount: string; currency: string; status: 'pending' | 'received'; effective_date: string; reference: string; notes: string | null; confirmed_at: string | null }
export interface ShoppingItem { id: string; name: string; quantity: number | null; unit_price: string | null; currency: string | null; category: string | null; image_url: string | null; return_deadline: string | null; return_eligibility: string }
export interface ShoppingOrder { id: string; retailer: string; external_order_id: string | null; order_date: string | null; currency: string | null; order_status: string | null; payment_status: string | null; total_amount: string | null; simulated: boolean; source: string; quantity: number; unknown_quantities: number; known_items_subtotal: string | null; items: ShoppingItem[]; refund_status: string; refunds: Refund[]; sources: string[]; return_cases?: { id: string; status: string }[] }
export interface OverviewData { total_orders: number; total_items: number; unknown_quantities: number; unknown_totals: number; open_returns: number; completed_returns: number; demo_orders: number; demo_open_returns: number; demo_completed_returns: number; currencies: { currency: string; gross: string; received: string; pending: string; net: string }[] }
export interface OrdersData { items: ShoppingOrder[]; total: number; page: number; page_size: number; retailers: string[]; statuses: string[] }
export interface AnalyticsData extends OverviewData { monthly: { month: string; currency: string; amount: string; orders: number }[]; retailers: { retailer: string; currency: string; amount: string; orders: number }[]; categories: { category: string; currency: string; amount: string }[]; order_counts: { month: string; orders: number }[]; top_purchases: ShoppingOrder[] }
export interface RetailersData { items: { id: string; name: string; extraction_supported: boolean; support_note: string; orders: number; detected_messages: number }[]; gmail: { status: string; last_sync_at: string | null; error_code: string | null } }
export interface RefundInput { amount: string; currency: string; status: 'pending' | 'received'; effective_date: string; reference: string; notes: string; confirm_received: boolean }
export const shoppingOverview = () => requestJson<OverviewData>('/api/shopping/overview')
export const shoppingOrders = (params: URLSearchParams) => requestJson<OrdersData>(`/api/shopping/orders?${params}`)
export const shoppingOrder = (id: string) => requestJson<ShoppingOrder>(`/api/shopping/orders/${encodeURIComponent(id)}`)
export const shoppingAnalytics = () => requestJson<AnalyticsData>('/api/shopping/analytics')
export const shoppingRetailers = () => requestJson<RetailersData>('/api/shopping/retailers')
export async function saveRefund(order: string, input: RefundInput, id?: string) {
  const result = await requestJson<Refund>(`/api/shopping/orders/${encodeURIComponent(order)}/refunds${id ? `/${encodeURIComponent(id)}` : ''}`, { method: id ? 'PUT' : 'POST', body: JSON.stringify(input) })
  notifyChange()
  return result
}
export function amount(value: string | null | undefined, currency?: string | null): string { return value == null ? 'Unknown' : `${currency ?? 'Unknown currency'} ${value}` }
export function productImage(value: string | null): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && ['m.media-amazon.com', 'images-na.ssl-images-amazon.com', 'rukminim2.flixcart.com', 'assets.myntassets.com'].includes(url.hostname) && !url.username && !url.password && (!url.port || url.port === '443') ? url.href : undefined
  } catch { return undefined }
}
