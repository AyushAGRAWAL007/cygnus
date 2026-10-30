// The only file that knows how to talk to the backend.
// An "API" here = the agreed set of URLs and JSON shapes the browser and server use.
import type {
  ActivityEvent as ViewActivityEvent,
  CaseEvent as ViewCaseEvent,
  EligibilityResult as ViewEligibilityResult,
  Order as ViewOrder,
  OrderItem as ViewOrderItem,
  ReturnCase as ViewReturnCase,
  ReturnRequest as ViewReturnRequest,
} from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export interface Health {
  status: 'ok' | 'degraded'
  app: string
  version: string
  environment: string
  time: string
  database: 'ok' | 'error'
  ai: { provider: string; configured: boolean; model: string }
  nvidia?: { provider: string; configured: boolean; model: string }
  retailer_mode: 'simulated' | 'live'
}

export interface AssistantReply {
  answer: string
  model: string
  facts: string[]
  data_source: 'simulated' | 'imported'
}

export interface AssistantRequest {
  message: string
  case_id?: string
  order_id?: string
}

export interface OrderItem {
  id: string
  name: string
  sku: string | null
  quantity: number | null
  price: number | null
  unit_price?: string | null
  currency?: string | null
  return_window_days: number | null
  final_sale: boolean
}

export interface Order {
  id: string
  retailer: string
  order_date: string
  simulated: boolean
  items: OrderItem[]
  source?: 'demo' | 'amazon_file' | 'gmail'
  currency?: string | null
  external_order_id?: string | null
  order_status?: string | null
  sources?: string[]
}

export type ReturnStatus =
  | 'requested'
  | 'pickup_scheduled'
  | 'missed_pickup'
  | 'availability_collected'
  | 'picked_up'
  | 'in_transit'
  | 'delivered'
  | 'resolved'

export interface CaseEvent {
  id: number
  type: string
  message: string
  evidence: Record<string, unknown>
  occurred_at: string
  simulated: boolean
}

export interface ReturnCase {
  id: string
  order_id: string
  item_id: string
  reason: string
  status: ReturnStatus
  availability: string | null
  resolved: boolean
  created_at: string
  updated_at: string
  simulated: boolean
  events: CaseEvent[]
}

export interface ActivityEvent extends CaseEvent {
  case_id: string
  order_id: string
}

export interface ListResponse<T> {
  items: T[]
  simulated: boolean
}

export interface EligibilityResult {
  eligible: boolean
  reasons: string[]
  simulated: boolean
}

export interface ReturnRequest {
  order_id: string
  item_id: string
  reason: string
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.method && !['GET', 'HEAD', 'OPTIONS'].includes(init.method.toUpperCase())) {
    headers.set('X-Cygnus-CSRF', '1')
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/api/auth/')) {
      window.dispatchEvent(new Event('cygnus:unauthorized'))
    }
    let message = res.status === 502
      ? 'The gateway could not get a valid response from the backend (502). Check that the backend is running and the frontend proxy uses the same port, then retry.'
      : res.status === 504
        ? 'The backend took too long to respond (504). Check the backend terminal for errors, then retry.'
        : res.status === 503
          ? 'The backend is temporarily unavailable (503). Check its terminal for errors, then retry.'
          : `The request failed (HTTP ${res.status}). Please retry.`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (typeof body.detail?.message === 'string') message = body.detail.message
      else if (Array.isArray(body.detail)) message = body.detail.map((item: { msg?: string }) => item.msg ?? 'Invalid input').join('. ')
      else if (body.detail) message = 'The request could not be completed.'
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new ApiError(message, res.status)
  }
  return res.json() as Promise<T>
}

export function fetchHealth(signal?: AbortSignal): Promise<Health> {
  return requestJson('/api/health', { signal })
}

export function askAssistant(input: AssistantRequest): Promise<AssistantReply> {
  return requestJson('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function fetchOrders(signal?: AbortSignal): Promise<ListResponse<Order>> {
  return requestJson('/api/orders', { signal })
}

export function fetchReturns(signal?: AbortSignal): Promise<ListResponse<ReturnCase>> {
  return requestJson('/api/returns', { signal })
}

export function fetchActivity(signal?: AbortSignal): Promise<ListResponse<ActivityEvent>> {
  return requestJson('/api/activity', { signal })
}

export function fetchReturn(caseId: string, signal?: AbortSignal): Promise<ReturnCase> {
  return requestJson(`/api/returns/${encodeURIComponent(caseId)}`, { signal })
}

export function checkEligibility(input: ReturnRequest): Promise<EligibilityResult> {
  return requestJson('/api/returns/eligibility', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function createReturn(input: ReturnRequest): Promise<ReturnCase> {
  return requestJson('/api/returns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export function schedulePickup(caseId: string, pickupDate: string): Promise<ReturnCase> {
  return requestJson(`/api/returns/${encodeURIComponent(caseId)}/pickup/schedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pickup_date: pickupDate }),
  })
}

export function markPickupMissed(caseId: string): Promise<ReturnCase> {
  return requestJson(`/api/returns/${encodeURIComponent(caseId)}/pickup/missed`, { method: 'POST' })
}

export function submitAvailability(caseId: string, availability: string): Promise<ReturnCase> {
  return requestJson(`/api/returns/${encodeURIComponent(caseId)}/availability`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ availability }),
  })
}

export function reschedulePickup(caseId: string, pickupDate: string): Promise<ReturnCase> {
  return requestJson(`/api/returns/${encodeURIComponent(caseId)}/pickup/reschedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pickup_date: pickupDate }),
  })
}

export function advanceSimulation(caseId: string, toStatus: string): Promise<ReturnCase> {
  return requestJson(`/api/returns/${encodeURIComponent(caseId)}/simulate/advance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to_status: toStatus }),
  })
}

const simulatedSource = 'simulated' as const
const changeListeners = new Set<() => void>()

export function subscribe(listener: () => void) {
  changeListeners.add(listener)
  return () => {
    changeListeners.delete(listener)
  }
}

export function notifyChange() {
  changeListeners.forEach((listener) => listener())
}

function imageFor(itemId: string): string | undefined {
  if (itemId === 'item-shoes-001') return '/products/runner.png'
  if (itemId === 'item-coat-002') return '/products/jacket.png'
  if (itemId === 'item-final-004') return '/products/headphones.png'
  return undefined
}

function toViewItem(item: OrderItem): ViewOrderItem {
  return {
    id: item.id,
    sku: item.sku ?? 'Unknown identifier',
    name: item.name,
    variant: item.sku ?? undefined,
    image: imageFor(item.id),
    price: item.price,
    currency: item.currency,
    qty: item.quantity,
    returnWindowDays: item.return_window_days,
    finalSale: item.final_sale,
  }
}

function toViewOrder(order: Order, cases: ReturnCase[]): ViewOrder {
  const items = order.items.map(toViewItem)
  const latestCase = cases.find((item) => item.order_id === order.id)
  const returnWindowDays = Math.max(0, ...order.items.map((item) => item.return_window_days ?? 0))
  const returnWindowEnd = new Date(`${order.order_date}T00:00:00`)
  returnWindowEnd.setDate(returnWindowEnd.getDate() + returnWindowDays)
  return {
    id: order.id,
    retailer: order.retailer,
    placedAt: order.order_date,
    total: items.every(i => i.price !== null && i.qty !== null && (!i.currency || i.currency === order.currency)) ? items.reduce((sum, item) => sum + item.price! * item.qty!, 0) : null,
    currency: order.currency,
    externalOrderId: order.external_order_id,
    orderStatus: order.order_status,
    sources: order.sources,
    returnWindowEndsAt: order.simulated ? returnWindowEnd.toISOString() : '',
    items,
    returnId: latestCase?.id,
    source: order.simulated ? simulatedSource : order.source === 'gmail' ? 'gmail' : 'amazon_file',
  }
}

function toViewEvent(event: CaseEvent): ViewCaseEvent {
  const titles: Record<string, string> = {
    return_requested: 'Simulated return requested',
    pickup_scheduled: 'Simulated pickup scheduled',
    pickup_missed: 'Simulated pickup marked missed',
    availability_collected: 'Customer availability recorded',
    pickup_rescheduled: 'Simulated pickup rescheduled',
    pickup_completed: 'Simulated pickup completion recorded',
    shipment_in_transit: 'Simulated shipment marked in transit',
    shipment_delivered: 'Simulated delivery recorded',
    refund_issued: 'Simulated refund issued',
  }
  const customerAction = event.type === 'return_requested' || event.type === 'availability_collected'
  return {
    id: String(event.id),
    at: event.occurred_at,
    actor: customerAction ? 'customer' : 'system',
    title: titles[event.type] ?? event.message,
    detail: event.message,
    evidence: 'recorded',
    source: simulatedSource,
  }
}

function viewStage(status: ReturnCase['status']): ViewReturnCase['stage'] {
  if (status === 'in_transit') return 'in_transit'
  if (status === 'delivered') return 'received'
  if (status === 'resolved') return 'refunded'
  if (status === 'requested') return 'requested'
  return 'pickup'
}

function viewNextStep(status: ReturnCase['status']): ViewReturnCase['nextStep'] {
  const steps: Record<ReturnCase['status'], ViewReturnCase['nextStep']> = {
    requested: { label: 'Schedule a simulated pickup', detail: 'Choose a date in the return detail.', owner: 'customer' },
    pickup_scheduled: { label: 'Record the simulated pickup outcome', detail: 'This demo can record pickup completion or a missed pickup.', owner: 'system' },
    missed_pickup: { label: 'Share availability and choose a new date', detail: 'A new simulated pickup date requires customer availability.', owner: 'customer' },
    availability_collected: { label: 'Choose a new simulated pickup date', detail: 'Availability is recorded; select another date to continue.', owner: 'customer' },
    picked_up: { label: 'Record simulated shipment in transit', detail: 'No carrier tracking integration is connected.', owner: 'system' },
    in_transit: { label: 'Record simulated delivery', detail: 'Shipment status advances only through a demo event.', owner: 'system' },
    delivered: { label: 'Record simulated refund issuance', detail: 'This does not verify a bank or card credit.', owner: 'system' },
    resolved: { label: 'Simulated refund issuance recorded', detail: 'Bank credit is not verified by this demo.', owner: 'system' },
  }
  return steps[status]
}

function toViewReturn(apiCase: ReturnCase, order: Order): ViewReturnCase {
  const item = order.items.find((candidate) => candidate.id === apiCase.item_id)
  if (!item) throw new Error(`Item ${apiCase.item_id} was not found on order ${order.id}`)
  const events = apiCase.events.map(toViewEvent)
  const pickupEvents = apiCase.events.filter((event) =>
    ['pickup_scheduled', 'pickup_rescheduled', 'pickup_missed', 'pickup_completed'].includes(event.type),
  )
  const latestScheduledPickup = pickupEvents.filter((event) => typeof event.evidence.pickup_date === 'string').at(-1)
  const pickupDate = latestScheduledPickup?.evidence.pickup_date
  let pickup: ViewReturnCase['pickup']
  if (pickupEvents.length) {
    const status = apiCase.status === 'missed_pickup' || apiCase.status === 'availability_collected'
      ? 'missed'
      : apiCase.status === 'pickup_scheduled'
        ? 'scheduled'
        : 'collected'
    pickup = {
      status,
      date: typeof pickupDate === 'string' ? pickupDate : undefined,
      evidence: 'recorded',
    }
  }
  const refundEvent = apiCase.events.find((event) => event.type === 'refund_issued')
  const refundAmount = refundEvent?.evidence.amount
  const refundSteps: ViewReturnCase['refund']['steps'] = [
    { id: 'requested', status: 'not_started' },
    { id: 'approved', status: 'not_started' },
    {
      id: 'processed',
      status: refundEvent ? 'recorded' : 'not_started',
      at: refundEvent?.occurred_at,
      note: refundEvent ? 'Simulated refund issuance event recorded; bank credit is not verified.' : undefined,
    },
    { id: 'credited', status: 'not_started', note: 'No bank or card credit evidence is available.' },
  ]
  const returnWindowEnd = new Date(`${order.order_date}T00:00:00`)
  returnWindowEnd.setDate(returnWindowEnd.getDate() + (item.return_window_days ?? 0))
  return {
    id: apiCase.id,
    backendStatus: apiCase.status,
    orderId: apiCase.order_id,
    availability: apiCase.availability ?? undefined,
    retailer: order.retailer,
    product: toViewItem(item),
    reason: apiCase.reason.replaceAll('_', ' '),
    stage: viewStage(apiCase.status),
    health: apiCase.resolved
      ? 'completed'
      : apiCase.status === 'missed_pickup' || apiCase.status === 'availability_collected'
        ? 'needs_attention'
        : 'on_track',
    openedAt: apiCase.created_at,
    updatedAt: apiCase.updated_at,
    windowEndsAt: returnWindowEnd.toISOString(),
    pickup,
    refund: { amount: typeof refundAmount === 'number' ? refundAmount : undefined, steps: refundSteps },
    events,
    nextStep: viewNextStep(apiCase.status),
    source: simulatedSource,
  }
}

async function loadViewData() {
  const [orders, cases] = await Promise.all([fetchOrders(), fetchReturns()])
  return { orders: orders.items, cases: cases.items }
}

export async function listOrders(): Promise<ViewOrder[]> {
  const { orders, cases } = await loadViewData()
  return orders.map((order) => toViewOrder(order, cases))
}

export async function listReturns(): Promise<ViewReturnCase[]> {
  const { orders, cases } = await loadViewData()
  const orderById = new Map(orders.map((order) => [order.id, order]))
  return cases.map((item) => {
    const order = orderById.get(item.order_id)
    if (!order) throw new Error(`Order ${item.order_id} was not found`)
    return toViewReturn(item, order)
  })
}

export async function getReturn(id: string): Promise<ViewReturnCase> {
  const [apiCase, orders] = await Promise.all([fetchReturn(id), fetchOrders()])
  const order = orders.items.find((item) => item.id === apiCase.order_id)
  if (!order) throw new Error(`Order ${apiCase.order_id} was not found`)
  return toViewReturn(apiCase, order)
}

export async function listActivity(): Promise<ViewActivityEvent[]> {
  const activity = await fetchActivity()
  return activity.items.map((event) => ({
    ...toViewEvent(event),
    caseId: event.case_id,
    orderId: event.order_id,
    type: event.type,
  }))
}

export async function checkReturnEligibility(input: ViewReturnRequest): Promise<ViewEligibilityResult> {
  return requestJson('/api/returns/eligibility', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}

export async function createReturnFromOrder(input: ViewReturnRequest): Promise<ViewReturnCase> {
  const created = await createReturn(input)
  notifyChange()
  return getReturn(created.id)
}

async function mutateView<T>(operation: Promise<T>): Promise<T> {
  const result = await operation
  notifyChange()
  return result
}

export const scheduleSimulatedPickup = (caseId: string, pickupDate: string) =>
  mutateView(schedulePickup(caseId, pickupDate))
export const markSimulatedPickupMissed = (caseId: string) =>
  mutateView(markPickupMissed(caseId))
export const recordCustomerAvailability = (caseId: string, availability: string) =>
  mutateView(submitAvailability(caseId, availability))
export const rescheduleSimulatedPickup = (caseId: string, pickupDate: string) =>
  mutateView(reschedulePickup(caseId, pickupDate))
export const advanceSimulatedStatus = (caseId: string, status: string) =>
  mutateView(advanceSimulation(caseId, status))


export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

export interface AuthUser { id: string; email: string; display_name: string; email_verified: boolean }
export interface LoginInput { email: string; password: string }
export interface RegisterInput extends LoginInput { display_name: string }
export const fetchCurrentUser = (signal?: AbortSignal) => requestJson<AuthUser>('/api/auth/me', { signal })
export const loginAccount = (input: LoginInput) => requestJson<AuthUser>('/api/auth/login', { method: 'POST', body: JSON.stringify(input) })
export const registerAccount = (input: RegisterInput) => requestJson<AuthUser>('/api/auth/register', { method: 'POST', body: JSON.stringify(input) })
export const logoutAccount = () => requestJson<{ message: string }>('/api/auth/logout', { method: 'POST', body: '{}' })
