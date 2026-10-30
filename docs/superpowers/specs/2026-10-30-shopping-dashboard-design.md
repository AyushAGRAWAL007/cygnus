# Cygnus unified shopping dashboard — proposed design

Status: investigation complete; implementation design awaiting approval.

## Verified zero-return investigation

The listening backend on port 8010 was inspected through its process environment,
reading only DATABASE_PATH, APP_ENV, AUTH_TRUSTED_ORIGINS and CORS_ORIGINS.
It uses `C:\Users\KIIT0001\AppData\Local\Temp\cygnus-import-13d2be52-48e9-4b4d-af95-dd572a65b0bf.db`.
The database was opened with SQLite `mode=ro` and `PRAGMA query_only=ON`.
No tokens, credential fields, password hashes or message contents were selected.

| Table / measure | Whole disposable database | Gmail-linked customer |
|---|---:|---:|
| Users | 2 | 1 linked owner |
| Orders | 4 | 0 |
| Order items | 4 | 0 |
| Return cases | 2 | 0 |
| Completed returns | 2 | 0 |
| Open returns | 0 | 0 |
| Events | 12 | 0 |
| Gmail integrations | 1 | 1 |
| Confirmed import history | 0 | 0 |
| Import previews | 0 | 0 |
| Gmail message records | 0 | 0 |
| Simulated refund-issued events | 2 | 0 |
| Confirmed real refunds | 0 recorded | 0 recorded |
| Pending real refunds | No real-refund records | No real-refund records |

Both migrations 001_customer_ownership and 002_order_imports are recorded.
All four orders and both returns are simulated; no orders have NULL owners.
The Gmail integration owner is not the recorded demo_data_owner.
The active browser session was not inspected: the account attribution above
comes from the user_id of the single matching Gmail integration.

Registration atomically claims demo_data_owner once and assigns the four
specific seeded demo order IDs to that first customer. Later customers correctly
do not receive those orders. Return ownership follows orders through joins.
No reassignment is warranted: that would expose another customer's records.

Overview loads listReturns -> GET /api/returns -> returns.list_cases. Its SQL joins
return_cases to orders, filters orders.user_id to the authenticated user, and
does not exclude simulated records. Completed status is resolved / resolved=1.
Frontend open/needs/refund counts are derived from that user's returned cases.
Overview already distinguishes loading and error from ready-empty. The activity
panel also explicitly renders its own errors. The shell omits attention badges
until ready, but that is not the source of the Overview's zero statistics.

Connecting Gmail only stores a connection. Sync is a separate user action.
Sync searches bounded Amazon messages, normalizes recognized observations,
and creates a preview. Confirmation creates authenticated-user-owned orders;
it does not create return cases. Gmail/file provenance attaches to the same
canonical order identity (user, retailer, marketplace, external order ID).
Duplicates do not create another order or another set of product lines.
There are currently no message records, previews or import history to indicate
that this account has imported purchases. No automatic mailbox read is authorized
as part of this investigation; the user should trigger Sync Gmail and confirm.

Follow-up read after baseline tests: the integration status is `disconnected`,
last_sync_at is non-NULL, and Gmail message/import/preview counts remain zero.
Therefore do not claim sync was never attempted: a sync may have returned no
candidates, or a later disconnect may have cleared tracking. No available
retained history proves which occurred. Reconnect through the UI and inspect
the user-triggered sync result before diagnosing real email template coverage.
All four simulated orders were confirmed to belong to demo_data_owner.
Counts were unchanged after verification. Tests used their own disposable
databases, not the application's running disposable database.

Baseline verification before implementation: 215 backend tests passed,
1 opt-in browser test skipped in that run, and 4 subtests passed. The browser
suite was separately enabled and passed its 1 test. Frontend lint and production
build both passed. No migration or product code was changed in this design stage.

The corrective product work is clearer purchase/import empty states, separate
purchase metrics, and explicit real-versus-simulated reporting. It is not changing
zero into a nonzero return count. No purchases or refunds will be invented.

## Approach and constraints

Extend the existing FastAPI/React/SQLite application, preserve hash routes and
the cream/navy/serif design, and keep OAuth, encryption, sessions and CSRF intact.
A separate shopping store would duplicate ownership/import logic; replacing
the return engine would violate preservation requirements. Neither is proposed.
No dependencies are needed for charts: accessible SVG charts can share textual
data tables and currency selectors. No commit, push or original-database migration.

## Proposed migration 003_shopping_dashboard

An explicit numbered migration depends on 002. It adds nullable, validated
order-level amount and currency/financial completeness metadata, payment status,
and nullable item category, image URL and verified return deadline fields.
Existing records are preserved; unknowns stay NULL. Decimal amounts remain TEXT.
Any legacy item-derived subtotal is labelled a known-items subtotal, never an
authoritative charged order total: shipping, discounts and taxes may be unknown.
Only complete totals explicitly supplied by a tested adapter contribute to
Gross Purchase Amount. The UI reports how many orders have unknown totals.

A refund ledger records owned order ID, stable external reference/source,
amount, currency, pending/confirmed status and confirmation timestamp/evidence
reference. It supports partial refunds and state transitions of one refund
without double counting. Composite ownership foreign keys prevent cross-user
links. Unique external references prevent repeated email/import confirmations
creating another refund. No raw email body is evidence storage. A simulated
refund event does not populate a confirmed real-refund record. No inference of
refund confirmation from a delivered return or promised refund date.

Proposed builder choice for this release: add an authenticated CSRF-protected
refund form and create/update endpoints under /api/shopping/orders/{id}/refunds.
The user records a positive decimal amount, matching order currency, pending or
received status, an effective date, and a bounded source/reference. Confirmation
of receipt is explicit and stores confirmed_at; the UI labels this user-confirmed,
not independently bank-verified. Status transitions preserve a stable refund ID,
with revision audit entries and idempotency keys to avoid retries double-counting.
Cross-owner writes are refused, and simulated-order refunds cannot enter real
spend totals. Received refunds can be corrected only with a recorded revision;
no destructive silent deletion. Do not infer refund amounts from line prices.
The API rejects inconsistent currency, non-finite/negative values, and recorded
refund totals exceeding a known charged total. Where total is unknown, show
that reconciliation is unavailable rather than inventing a limit or total.
This provides an actual entry path without promising automatic refund email
extraction. Tested retailer refund adapters can feed the same ledger later.

A retailer_accounts table can associate multiple source/provider account
references with a user and retailer, without collecting retailer passwords or
duplicating Gmail OAuth secrets. Existing orders remain visible without a
new account link. All new orders require an owner; existing ownership is
preserved without blindly assigning legacy NULL demo rows. Migration tests
check data preservation, foreign keys, integrity, idempotency and atomic rollback.
Preparation script verifies 001, 002 and 003 using the latest compatible schema
validator, and refuses existing output paths. No startup migration.

## API and financial rules

Add authenticated /api/shopping/overview, /api/shopping/orders,
/api/shopping/orders/{id}, /api/shopping/analytics, and /api/shopping/retailers.
Every query starts with authenticated user ownership; unavailable schema returns
an actionable migration error instead of zero. Existing APIs remain compatible.

Overview exposes eight requested measures: Total Orders, Total Items Purchased,
Total Purchase Amount, Net Shopping Spend, Open Returns, Completed Returns,
Refunds Received and Pending Refunds. Real spending excludes simulated records.
Order/item counts explicitly identify real versus demo scopes. Unknown quantities
are excluded from known quantity totals and counted separately, not replaced by 1.
Return counts show real and simulated breakdowns rather than presenting demo
returns as real. Confirmed refunds alone reduce net spend. Pending amounts are
separate. Missing amounts are not converted to zero. Monetary values are summed
with Decimal and returned as decimal strings grouped by ISO currency, never
mixed, FX-converted or summed using binary floating point. Real-return amount
reporting requires explicit ledger evidence; existing simulated workflows survive.
Dates/months derive from recorded order/refund dates, never email arrival as a
substitute for an unknown order date. Undated/unclassified data has an explicit
Unknown bucket. Category spend uses complete line amounts; tax/shipping remain
separately unallocated so chart totals do not claim nonexistent precision.

The order list implements server-side search by product/external ID, retailer,
ISO from/to dates and status filters, deterministic newest/oldest/amount sorting,
page/size pagination and total count. Amount sorting uses a selected currency;
unknown amounts appear last. Date and sort ties use order ID. Bounded page size
and parameterized SQL preserve isolation and avoid unnecessary mailbox reads.
Order detail includes lines, provenance, amounts and completeness, delivery and
payment status, return eligibility/deadline and refunds. Missing images/logos,
payment status and policies use neutral placeholders/Unknown. No remote asset
fetch from email content; optional image URLs must pass an HTTPS allowlist.

## Multi-retailer extraction

Introduce an explicit retailer adapter registry with stable retailer IDs,
tested sender/domain metadata fixtures, extraction capability and support status.
Amazon interchange/file import and conservative Gmail extraction remain supported
at their current documented limits. Add Flipkart, Myntra, Meesho and Ajio registry
entries; unknown formats remain unsupported/review-only, never marketed as
working extraction. Generalize the internal normalized contract to a bounded
retailer identifier and retailer-specific external ID validation, retaining
Amazon's current validation for Amazon records. Identity includes marketplace
where required, preserving existing cross-source deduplication.

Gmail can recognize candidate shopping metadata for the registry through tested
domain boundaries and subjects, retaining only necessary metadata/message IDs.
Full bodies are fetched only for enabled tested extraction adapters. Unsupported
retailers produce an explicit unsupported-format outcome, not a fabricated order.
No new retailer extraction becomes enabled without redacted fixtures and tests.
The Retailers screen distinguishes detected, connected and extraction-supported
states. No scraping, passwords, background auto-import or AI email transmission.

## UI

Navigation: Overview, All Orders, Returns & Refunds, Analytics, Retailers,
Agent Activity. Existing deep links remain valid. Overview retains return
attention/activity and the assistant, with purchase metrics and an import CTA.
Zero orders explains: Gmail is connected separately from syncing and confirming;
returns appear only when recorded. API errors use retry cards and never zeros.

All Orders preserves file/Gmail import controls and existing simulated return
actions, adds filters, sorting, pagination and links to an order detail route.
Analytics charts monthly expenditure/order counts, retailer/category amounts,
largest purchases, confirmed/pending refunds and trends. All show scope, selected
currency, unknown coverage, and accessible empty/error/loading states. No invented
comparisons when a prior month or amount is unavailable. Responsive cards,
scrollable tables and existing design tokens keep desktop/tablet/mobile usable.

## Verification and rollout

Tests cover zero/actual orders, quantity completeness, all return statuses,
real/simulated separation, partial/pending/confirmed refund transitions,
currencies and Decimal arithmetic, cross-customer list/detail/analytics/refund
isolation, multi-retailer identities, duplicate Gmail/file confirmation,
unrecognized senders, unknown fields, pagination/filter/sort, migration rollback,
and auth/CSRF regressions. Browser tests prove empty and API-error states,
navigation, file-confirmation refresh, charts and responsive order detail.
Run complete backend suite, opt-in browser tests, frontend lint and build.

Apply migration 003 only to fresh disposable copies through preparation. Do not
restart the user's backend onto a new database without preserving their existing
disposable data/OAuth connection. Provide an explicit copy-preparation command
with --source pointing to the current disposable database and a new output path;
the original disposable copy and live database remain unchanged. Set DATABASE_PATH
to the new output and restart on 8010, frontend proxy on 5179. Take read-only
aggregate before/after counts and report tests and any unsupported templates.
