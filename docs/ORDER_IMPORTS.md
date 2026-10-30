# Customer order imports: implementation and test-user setup

## Status and compatibility boundary

Cygnus now has a shared normalized order-import engine, bounded file readers,
preview/confirmation, owned import history, multi-source provenance, Google
OAuth and manual bounded Gmail synchronization. Migration 002 is required.
It has **not** been applied to `backend/cygnus.db`. The application does not
apply either migration automatically.

An Amazon.in consumer export has not been supplied. Research on 2026-10-30
did not establish a published authoritative consumer export schema. The
Amazon.in [data-request page](https://www.amazon.in/hz/privacy-central/data-requests/preview.html)
and help endpoints could not be fetched by the research tool. No India export
layout, CSV header set, JSON shape, nested relationship schema or universal
filename is claimed as verified. Seller Central/Business reports are not used.

**The current adapters support a documented synthetic Cygnus interchange
contract, not a verified Amazon.in archive.** Real archives with unknown files
receive unsupported-format reports; adding genuine compatibility requires a
redacted consumer sample with directory structure, metadata/schema files and
column names intact. Never send Amazon credentials. Cygnus does not scrape
Amazon or request an Amazon password.

Gmail makes actual Google OAuth/Gmail REST requests when configured. Automated
tests use synthetic messages and mocked Google responses. Live consent with a
Google test account has not been performed. Email parsing is deliberately
conservative: Amazon order IDs and relevance metadata are recognized, but
automatic product extraction currently requires explicit labeled fields in
the template below. Other templates become review-only observations, never
invented product lists or prices.

## Safe local setup in PowerShell

From the repository root, create a **new disposable copy**. This command refuses
the live path and any existing output path. It opens the source read-only,
copies it using SQLite backup, and applies migrations only to the new copy.

```powershell
cd C:\Users\KIIT0001\OneDrive\Desktop\cygnus
$importDb = Join-Path $env:TEMP ("cygnus-import-dev-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".db")
.\backend\.venv\Scripts\python.exe backend\scripts\prepare_import_database.py --output $importDb
$env:DATABASE_PATH = $importDb
$env:APP_ENV = 'development'
$env:AUTH_TRUSTED_ORIGINS = 'http://localhost:5179'
$env:CORS_ORIGINS = 'http://localhost:5179'
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8010 --no-access-log
```

In a separate PowerShell terminal:

```powershell
cd C:\Users\KIIT0001\OneDrive\Desktop\cygnus\frontend
$env:CYGNUS_DEV_API_TARGET = 'http://127.0.0.1:8010'
npm.cmd run dev -- --host 127.0.0.1 --port 5179 --strictPort
```

Open `http://localhost:5179`, register a test account, then open Orders. Data in
this disposable copy may include existing accounts; use only test accounts.
Preparation verifies both migration ledger entries and the current import schema.
It accepts legacy, migration-001, and fully migrated sources without changing them.
If a backend is already running, stop it and restart it in the terminal where
`DATABASE_PATH` was set. Preparing a new database does not change the database
used by an existing backend process. A missing-migration-002 message after a
successful preparation usually means that process is using a different database.
Imported orders are kept separate from SIM-marked seeded orders. This setup
does not authorize migrating the original database.

## Supported synthetic file contract

UTF-8 JSON (optional BOM), maximum 10 MiB:

Ready-to-upload **synthetic** examples are in
`backend/tests/fixtures/amazon/synthetic-orders.json` and
`backend/tests/fixtures/amazon/synthetic-orders.csv`. They are interchangeable
test records and must not be described as actual customer purchases.

```json
{
  "format": "cygnus-amazon-v1",
  "orders": [{
    "order_id": "123-1234567-1234567",
    "marketplace": "amazon.in",
    "order_date": "2026-10-01",
    "currency": "INR",
    "order_status": "Delivered",
    "items": [{
      "product_name": "Synthetic test kettle",
      "asin": "B012345678",
      "external_item_id": "line-1",
      "quantity": 1,
      "unit_price": "1299.50",
      "shipment_id": "shipment-1",
      "delivery_date": "2026-10-04"
    }]
  }]
}
```

Optional item details: `shipment_id`, `shipment_status`, `delivery_date`,
`product_details`. These recognized structured fields are retained; unrelated
address/payment/contact data is not retained. Original-file SHA-256 and
entry/record references provide provenance without retaining the archive.

CSV uses one product row per line. Required headers are `Order ID`, `Order Date`,
`Product Name`. Optional headers are `Quantity`, `Unit Price`, `Currency`,
`Marketplace`, `ASIN`, `Order Status`, `Item ID`, `Shipment ID`, `Delivery Date`.
Unknown headers are refused, not guessed. Order metadata must agree across
rows. Exact repeated rows are ambiguous without a source item identity and
are refused instead of doubling quantities or deleting a genuine product.

Dates must be ISO dates or ISO timestamps; the original calendar date is kept.
Slash-separated dates are refused because day/month interpretation is ambiguous.
Prices are exact decimal unit prices without currency symbols or thousands
separators. Currency must be explicit. Missing quantity, amount or currency is
NULL and requires acknowledgment. Marketplace/date/product lines are required
for confirmation. Cancelled/returned status remains source-reported and does
not authorize a Cygnus return/refund. Conflicting rows exclude the whole order.

ZIP may contain these recognized files in nested directories. No file is ever
extracted. Bounds: 200 entries, 10 MiB per entry, 30 MiB total expanded bytes,
100:1 maximum compression ratio, 5,000 order records across the archive.
Absolute/traversal/drive paths, duplicate paths, symlinks, encrypted entries,
nested archives, bad CRC/ZIP data and unsafe expansion are rejected. Unknown
metadata/schema files are reported as unsupported; they are not interpreted.

## Schema and import behavior

Migration 002 extends existing orders and import history; it rebuilds only
`order_items` to make unknown legacy values nullable, preserving IDs and
relationships. Exact decimal amounts are authoritative in `unit_price TEXT`;
the legacy numeric `price` remains for API compatibility. Currency is stored
on both order and item. No return windows are inferred for real purchases.

Canonical identity is `(user_id, retailer, marketplace, external_order_id)`.
Thus an Amazon file and Gmail can reference one order. `orders.source` records
the first import, while `order_source_references` records all confirmed source
observations. Composite foreign keys enforce order/customer ownership.
Later observations cannot overwrite existing order/product values; preview
reports conflicts and acknowledgment adds provenance only. Automatic product
merging across incomplete shipment messages is intentionally avoided.

Preview payloads expire after 30 minutes and are pruned during later preview
creation for that customer. Confirmation rechecks ownership, expiry and
duplicates under `BEGIN IMMEDIATE`. Repeating confirmation returns its saved
result; a second upload skips existing orders. Invalid records remain excluded
with visible counts. Partial selection is explicit. Confirmed history is kept.

The upload API is `POST /api/imports/amazon/preview` with raw bytes and
`Content-Type: application/octet-stream`; no multipart dependency is needed.
It still requires the trusted Origin, custom CSRF header and session. Other
mutations remain JSON-only. Upload/confirm/connect/sync endpoints are throttled
using the existing per-process limiter. Other import/integration mutation
bodies are capped at 128 KiB. A reverse proxy should enforce matching request
and timeout limits for a public deployment.

## Google test-project configuration

For local Gmail OAuth, use `http://localhost:5179` consistently, including sign-in.
The Connect button sends a same-origin JSON POST to `/api/integrations/gmail/authorize`
with `X-Cygnus-CSRF: 1` and the session cookie. Vite forwards it to port 8010
without changing the browser's Origin header. The backend checks that exact
origin, CSRF header, and content type before authentication and OAuth setup.
Its development cookie is host-only, HttpOnly, SameSite=Lax, and not Secure;
the proxy's backend address does not change the browser's cookie host.
Do not switch to `127.0.0.1:5179` after signing in: it has a different origin
and cookie host. Rejected requests now identify which CSRF check failed.
An absent or expired session with otherwise valid headers returns 401 instead.
Restart the backend after environment changes; process environment variables
override `.env` files and settings are cached for that backend process.

1. Create a dedicated Google Cloud test project and enable Gmail API.
2. Configure Google Auth Platform branding, support/developer contact, and
   external audience with publishing status **Testing**. Add the intended
   Google accounts as test users. Do not imply public verification.
3. Configure only `https://www.googleapis.com/auth/gmail.readonly` in Data Access.
   `gmail.metadata` cannot read message bodies; send/modify/delete scopes are
   unnecessary and are not requested.
4. Create a Web application OAuth client. Register the exact redirect URI
   `http://localhost:5179/api/integrations/gmail/callback` for the setup above.
   Use HTTPS and the exact trusted application origin in production.
5. Put these values in backend environment variables or the ignored backend
   `.env` file, never frontend variables or committed files:

```text
GOOGLE_CLIENT_ID=<your test client ID>
GOOGLE_CLIENT_SECRET=<your test client secret>
GOOGLE_REDIRECT_URI=http://localhost:5179/api/integrations/gmail/callback
INTEGRATION_ENCRYPTION_KEY=<your persistent Fernet key>
```

Generate a key locally (the command prints a new secret; store it securely):

```powershell
.\backend\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use a deployment secret manager for production. The encryption key must be
separate from the database and stable across restarts. Missing/invalid keys
fail securely; no plaintext fallback exists. Key rotation requires decrypting
and reencrypting credentials using both keys during an explicitly planned
maintenance operation; this implementation does not silently rotate keys.

The backend uses authorization code + S256 PKCE, ten-minute one-use hashed
state bound to customer/session/integration generation, a fixed redirect,
offline access and consent. Tokens are Fernet-encrypted at rest and never
returned to the browser. The callback strips query values from the ASGI scope
before application access logging; still disable proxy/access logging of
callback query strings, request bodies and Authorization headers. The example
uses `--no-access-log` as an extra safeguard. Disable HTTP wire debug logs.

Google categorizes `gmail.readonly` as **restricted**. A public app generally
requires applicable brand/restricted-scope verification; server-side storage
or transmission can require a security assessment. Google's testing limitations
apply, including short refresh-token lifetimes (typically seven days for this
external testing-mode scope). The project has no claim of verification,
assessment completion, or production approval. Review the official policy
before public launch:

- [Scope classification](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Refresh-token limits](https://developers.google.com/identity/protocols/oauth2)
- [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy)

## Gmail parsing, synchronization and retention

Connect opens Google's consent screen. Only a successful code exchange and
Gmail profile lookup produces Connected status. Sync is manual, not scheduled,
push-based or real time. Initial search covers relevant Amazon messages from
the last year, at most 50 search results per page. Metadata is checked before
fetching bodies. Allowed sender domains are explicit supported Amazon
marketplaces (and supported shipment-tracking subdomains); this is a relevance
filter, not proof of email authenticity or a verified retailer API record.

Body extraction accepts bounded UTF-8 text/plain and HTML converted to text,
with script/style/head text excluded. HTML is never rendered. Multipart
alternatives select a single representation. Recognized product lines use:

```text
Order #123-1234567-1234567
Order date: 2026-10-01
Item: Synthetic test kettle
Quantity: 1
Unit price: INR 1299.50
ASIN: B012345678
```

Unknown templates, ambiguous multiple order IDs, invalid data and excessive
body/part/item bounds do not become partially imported orders. Supported order
ID observations with missing fields are preview-only until an adapter can
supply the necessary facts. Source timestamps are message arrival timestamps,
never substituted for the purchase date. Shipment/cancellation/refund subjects
are source-reported status observations, not verified logistics/payment events.

Initial pagination stores an anchor taken before fetching. Incremental calls
use `history.list` and message-ID deduplication. Expired history produces a
bounded search recovery; the last-year boundary means it is not a complete
historical mailbox import. History pages are bounded to 50 history records and
200 unique messages per operation; exceptionally large pages are refused with
the cursor preserved. GET requests retry transient errors up to three total
attempts. Failed parsing is recorded with a safe code; network failures do not
advance the cursor. No mailbox-write API is called.

Only extracted structured order observations, message IDs, source timestamps,
connected account and synchronization metadata are retained. Raw messages and
bodies are discarded after parsing. Pending structured observations are kept
for at most 30 days (cleanup runs during sync) so an abandoned/expired preview
can be rebuilt without fetching bodies again. Confirmation clears the pending
copy; minimal message IDs remain for deduplication. At the pending cap a
recovery preview is offered instead of fetching more mail. Confirmed order
observations remain as provenance. Disconnect deletes tokens, message tracking,
pending observations, OAuth attempts and Gmail previews, while preserving
previously confirmed customer orders and history.

Disconnect disables local sync before contacting Google's revocation endpoint.
If revocation fails, encrypted credentials remain only for a retry and status
is Revocation pending. Sync cannot continue. The customer may also revoke access
in Google Account permissions. Callback/disconnect generation checks protect
newer connections from stale callbacks/finalizers.

## Existing workflow and AI boundary

Imports appear on Orders with source badges, exact currency, known item values,
and unverified eligibility. Real purchases cannot enter the demo pickup/refund
workflow. The backend requires checking Amazon for real policy/return actions.
File-import records can be selected for the existing read-only NVIDIA assistant;
facts are labeled imported/unverified and scoped to their customer. Existing
provider error handling, prompt defenses and development/demo gate remain.

Gmail-derived records are blocked from external AI context, including an order
originally imported from a file that later gains Gmail provenance. Sharing
restricted-scope data with NVIDIA/Nebius needs an approved, compliant user
disclosure/consent policy before enablement. The UI states this boundary.

## Verification commands

```powershell
cd C:\Users\KIIT0001\OneDrive\Desktop\cygnus\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
$env:CYGNUS_BROWSER_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests/browser -q
Remove-Item Env:CYGNUS_BROWSER_TESTS
cd ..\frontend
npm.cmd run lint
npm.cmd run build
```

Browser tests launch only their own temporary database and local servers on
8017/5177, run headless Edge, and stop those servers. They check ZIP upload,
preview-before-write, confirmation, duplicate reupload, malformed-file feedback,
missing Google configuration, source/currency display, and overflow at
1440/1280/768/390px. They do not automate a real Google consent screen.
