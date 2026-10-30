export type Source = 'simulated' | 'amazon_file' | 'gmail'
export type Evidence = 'recorded' | 'confirmed' | 'pending' | 'unverified' | 'failed' | 'not_started'
export type Stage = 'requested' | 'eligible' | 'pickup' | 'in_transit' | 'received' | 'refunded' | 'credited'
export const STAGES: { id: Stage; label: string; short: string }[] = [
  { id: 'requested', label: 'Return requested', short: 'Requested' },
  { id: 'eligible', label: 'Eligibility checked', short: 'Eligibility' },
  { id: 'pickup', label: 'Simulated pickup', short: 'Pickup' },
  { id: 'in_transit', label: 'Simulated shipment', short: 'In transit' },
  { id: 'received', label: 'Simulated delivery', short: 'Delivered' },
  { id: 'refunded', label: 'Simulated refund issued', short: 'Refund issued' },
  { id: 'credited', label: 'Bank credit not verified', short: 'Credit unverified' },
]
export const stageIndex = (stage: Stage) => STAGES.findIndex((item) => item.id === stage)

export type CaseHealth = 'on_track' | 'needs_attention' | 'awaiting_approval' | 'completed'
export type Actor = 'cygnus' | 'customer' | 'system'

export interface Product {
  sku: string
  name: string
  variant?: string
  image?: string
  price: number | null
  currency?: string | null
}

export interface OrderItem extends Product {
  id: string
  qty: number | null
  returnWindowDays: number | null
  finalSale: boolean
}

export interface Order {
  id: string
  retailer: string
  placedAt: string
  deliveredAt?: string
  total: number | null
  currency?: string | null
  externalOrderId?: string | null
  orderStatus?: string | null
  sources?: string[]
  payment?: string
  returnWindowEndsAt: string
  items: OrderItem[]
  returnId?: string
  source: Source
}

export type PickupStatus = 'scheduled' | 'missed' | 'reschedule_requested' | 'collected'
export interface Pickup {
  courier?: string
  trackingId?: string
  status: PickupStatus
  date?: string
  slot?: string
  address?: string
  attempts?: number
  evidence: Evidence
}

export type RefundStepId = 'requested' | 'approved' | 'processed' | 'credited'
export interface RefundStep {
  id: RefundStepId
  status: Evidence
  at?: string
  note?: string
  reference?: string
}
export interface Refund {
  amount?: number
  method?: string
  steps: RefundStep[]
}

export interface CaseEvent {
  id: string
  at: string
  actor: Actor
  title: string
  detail?: string
  evidence: Evidence
  reference?: string
  source: Source
}

export interface ActivityEvent extends CaseEvent {
  caseId: string
  orderId: string
  type: string
}

export interface NextStep {
  label: string
  detail: string
  owner: Actor
  expectedBy?: string
}

export interface ReturnCase {
  id: string
  backendStatus: 'requested' | 'pickup_scheduled' | 'missed_pickup' | 'availability_collected' | 'picked_up' | 'in_transit' | 'delivered' | 'resolved'
  orderId: string
  availability?: string
  retailer: string
  product: Product
  reason: string
  customerMessage?: string
  stage: Stage
  health: CaseHealth
  openedAt: string
  updatedAt: string
  windowEndsAt: string
  pickup?: Pickup
  refund: Refund
  events: CaseEvent[]
  nextStep: NextStep
  source: Source
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
