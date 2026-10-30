# Unified shopping dashboard implementation plan

Approved spec: ../specs/2026-10-30-shopping-dashboard-design.md (user explicitly approved).
No commits, pushes, live DB writes, secret output or automatic migrations.
Work in current checkout to preserve all uncommitted working integration code.

## Shared API contract

All new endpoints authenticated under /api/shopping. Existing APIs unchanged.
New schema 003_shopping_dashboard, applied explicitly, never at app startup.
orders additions: total_amount TEXT NULL (authoritative charged total only),
payment_status TEXT NULL. Existing orders.currency is used for totals.
order_items additions: category TEXT NULL, image_url TEXT NULL,
return_deadline TEXT NULL. Unknowns stay NULL, no total backfill from line items.
refunds: id, user_id, order_id, amount TEXT, currency, status ('pending','received'),
effective_date, reference, notes, confirmed_at NULL, created_at, updated_at.
Refund idempotency via user/order/reference; revision audit preserved on updates.
Composite owned-order foreign key. retailer_accounts owned multiple-account table.

GET /overview returns:
{total_orders:number,total_items:number,unknown_quantities:number,
unknown_totals:number,open_returns:number,completed_returns:number,
demo_orders:number,demo_open_returns:number,demo_completed_returns:number,
currencies:[{currency:string,gross:string,received:string,pending:string,net:string}]}
Metrics exclude simulated records except explicit demo fields. Monetary values
decimal strings. Refund currencies may appear even if no known gross total.

GET /orders?q=&retailer=&date_from=&date_to=&status=&sort=newest|oldest|amount_desc|amount_asc&currency=&page=1&page_size=20&scope=all|real|demo
returns {items:ShoppingOrder[],total:number,page:number,page_size:number,
retailers:string[],statuses:string[]}. Filters and sort parameterized/bounded.
Amount sorting requires currency. Unknown amounts last, stable ID tie-break.
ShoppingOrder={id,retailer,external_order_id,order_date,currency,order_status,
payment_status,total_amount:string|null,simulated:boolean,source,
quantity:number,unknown_quantities:number,known_items_subtotal:string|null,
items:[{id,name,quantity:number|null,unit_price:string|null,currency:string|null,
category:string|null,image_url:string|null,return_deadline:string|null,
return_eligibility:string}],
refund_status:string,refunds:Refund[],sources:string[]}
GET /orders/{id} returns ShoppingOrder plus return_cases (safe owned cases).
Refund={id,amount,currency,status,effective_date,reference,notes,confirmed_at}.
POST /orders/{id}/refunds accepts {amount:string,currency,status,effective_date,
reference,notes?:string,confirm_received:boolean}; PUT same path /{refund_id}
same fields. Require explicit confirm_received=true for received status.
Responses are Refund. Mutations require existing CSRF middleware and ownership.
GET /analytics returns overview fields plus
monthly:[{month,currency,amount:string,orders:number}],
retailers:[{retailer,currency,amount:string,orders:number}],
categories:[{category,currency,amount:string}],
order_counts:[{month,orders:number}], top_purchases:ShoppingOrder[].
Never sum currencies together; category series are line subtotals, not charges.
GET /retailers returns {items:[{id,name,extraction_supported:boolean,
support_note:string,orders:number,detected_messages:number}],gmail:{status,last_sync_at,error_code}}.
Amazon extraction limited to documented conservative fixtures, all other
retailer formats explicitly unsupported until representative fixtures exist.

## Tasks

- [ ] 1. Recheck active disposable DB and Gmail transition path; validate
  sync->preview->confirm->ownership->cross-source dedup with isolated tests.
- [ ] 2. Backend worker: migration 003, service/routes, Decimal finance,
  pagination/order detail/analytics/refunds/retailers, meaningful tests.
- [ ] 3. Import worker: tested retailer registry, conservative multi-retailer
  metadata discovery, optional authoritative totals/categories in interchange,
  persist only if schema supports fields; preserve compatibility with 002.
- [ ] 4. Frontend worker: API client/types, All Orders/detail with refunds,
  overview metrics, Analytics/Retailers/navigation, preserve old return actions
  and assistant. Empty/error/loading states. Lint/build.
- [ ] 5. Integrate preparation script latest validation + migration tests,
  browser coverage, review changes, run full suite/lint/build/browser tests.
- [ ] 6. Prepare only a NEW copy of current disposable DB, verify counts and
  migration ledger, preserve original and OAuth state, report exact run commands.

## Ledger

- Investigation before implementation: zero Gmail-owner orders/returns; demo
  records belong to first customer. No reassignment. Earlier connection status
  changes have no audit trail; only disconnect code sets disconnected, refresh
  denial sets reauthorization_required. Add safe operational metadata if needed,
  never claim cause without evidence or perform unsolicited mailbox sync.
