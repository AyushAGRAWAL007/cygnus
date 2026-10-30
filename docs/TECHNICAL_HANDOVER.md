# Cygnus Technical Handover

**Audit date:** 2026-10-29  
**Scope:** Current repository source. No application, configuration, dependency, database, or Git-history changes were made for this handover.

## Executive Summary

Cygnus is a React/Vite v0 frontend over a FastAPI backend. Its order and return records are seeded, simulated SQLite data. The backend enforces deterministic eligibility and ordered state transitions; NVIDIA provides read-only explanations grounded in those backend records. No retailer, courier, payment, or bank is connected. The assistant is available only when `APP_ENV` is `development` or `demo`; there is no user authentication or customer-level authorization.

The current branch is `main`. At audit start the only uncommitted source change was the existing `backend/tests/test_nvidia.py` modification. `backend/.env` is ignored, not tracked, and was not opened. The removed `cygnus-j0-main` backup is absent and was not recreated.

## Repository Map

```text
cygnus/
|-- .env.example                   # Placeholder configuration template; no credentials
|-- .gitignore                     # Secrets and generated/local files
|-- README.md                      # Setup, product status, limitations
|-- LICENSE                        # MIT license
|-- backend/
|   |-- requirements.txt           # Pinned Python runtime dependencies
|   |-- app/
|   |   |-- main.py                # FastAPI startup, middleware, request models, all routes
|   |   |-- config.py              # Pydantic Settings and secret/environment loading
|   |   |-- db.py                  # SQLite connection and connectivity check
|   |   |-- returns.py             # Schema initialization, seeds, eligibility, lifecycle, events
|   |   `-- ai/
|   |       |-- nvidia.py          # NVIDIA read-only assistant, context and provider handling
|   |       `-- nebius.py          # Separate Nebius SDK client and diagnostics
|   |-- tests/
|   |   |-- test_health.py         # Health response and Nebius missing-key behavior
|   |   |-- test_returns.py        # Seed, eligibility, transitions and evidence ordering
|   |   `-- test_nvidia.py         # NVIDIA config, mocked provider, context and route safety
|   `-- scripts/check_llm.py       # Nebius model listing and inference diagnostic
|-- frontend/
|   |-- package.json               # React, Vite, Tailwind, TypeScript, lint/build scripts
|   |-- vite.config.ts             # `/api` development proxy to port 8000
|   |-- index.html                 # App metadata, favicon and Google font links
|   |-- public/products/           # Six v0 product PNGs
|   `-- src/
|       |-- main.tsx, App.tsx      # React entry and hash-router dispatch
|       |-- index.css              # v0 porcelain/paper/cobalt design tokens and motion
|       |-- lib/
|       |   |-- api.ts             # Fetch client and backend-to-view-model adapter
|       |   |-- router.ts          # Hash routes and legacy dashboard alias
|       |   |-- types.ts            # Frontend display/data types
|       |   `-- format.ts           # Display formatting and class helper
|       |-- hooks/                  # Health, resource subscriptions and dashboard data
|       |-- components/             # App shell, assistant, brand, evidence and case UI
|       `-- pages/                  # Landing, Overview, Returns, Detail, Reschedule, Activity, Orders
`-- docs/
    |-- ARCHITECTURE.md             # Earlier planned architecture (partly stale)
    |-- HACKATHON_COMPLIANCE.md     # Hackathon checklist/status (partly stale)
    |-- IMPLEMENTATION_PLAN.md      # Earlier phased plan (partly stale)
    |-- LEARNING_GUIDE.md           # Concept guide (partly stale)
    `-- TECHNICAL_HANDOVER.md       # This document
```

Generated/local folders (`backend/.venv`, `frontend/node_modules`, frontend build output, Python caches, SQLite files) are excluded from this tree. The `backend/.env` file is local-only and intentionally omitted.

| Directory | Purpose and dependencies | Classification |
|---|---|---|
| `backend/app/` | FastAPI imports configuration, SQLite helpers, workflow service, and AI clients. | Application code |
| `backend/app/ai/` | NVIDIA chat service and independent Nebius diagnostics; `main.py` calls each for separate routes. | Application code |
| `backend/tests/` | FastAPI `TestClient` tests; workflow/NVIDIA fixtures use temporary SQLite paths and HTTPX `MockTransport`. | Test code |
| `backend/scripts/` | Manual Nebius connectivity diagnostic. | Developer tooling |
| `frontend/src/` | React routes/pages, v0 components, hooks, types, and the API adapter. | Application code |
| `frontend/public/` | Favicon and static product imagery. | Static assets |
| `docs/` | Architecture, learning, compliance, and planning documents. | Documentation |

No Docker, Compose, Terraform/Bicep, Vercel, Netlify, Render, Fly, or GitHub Actions deployment files were found. No ORM, formal database model module, or migration tool was found.

## Backend Architecture

### Startup and configuration

`uvicorn app.main:app --reload --port 8000` is run from `backend/`. `main.py` creates the FastAPI app and installs CORS middleware. Its async lifespan calls `returns.initialize()` before serving requests; there is no custom shutdown work. Routes are declared directly in `main.py`, not split into `APIRouter` modules.

[`backend/app/config.py`](../backend/app/config.py) derives `REPO_ROOT` from its own path and uses `pydantic-settings` `BaseSettings`. It reads root `.env` followed by `backend/.env`; process environment values take precedence. `get_settings()` is cached with `lru_cache`. API keys are `SecretStr`. NVIDIA defaults are the configured NVIDIA API Catalog base URL and model; Nebius has separate settings. `nvidia_configured` and `ai_configured` expose booleans, not key values.

The default `APP_ENV` is `development`. The chat route is allowed for `development` and `demo`, and blocked otherwise. Since no authentication exists, a deployment must set a non-demo environment; that also disables the assistant until authentication is designed.

### Routes

No route has authentication or user-level authorization. CORS permits configured origins, defaulting to localhost Vite origins. The API is intended for the current simulated demo.

| Method and path | Handler / schema | Behavior and data access | Classification |
|---|---|---|---|
| `GET /api/health` | `health()`; no body | Opens SQLite and runs `SELECT 1`; returns status, version, database, Nebius/NVIDIA configured booleans and model IDs, and simulated retailer mode. Never returns keys. | Read-only |
| `GET /api/orders` | `orders()`; no body | Selects seeded orders/items from SQLite. Returns `{items, simulated}`. | Read-only, simulated |
| `GET /api/orders/{order_id}` | `order_detail(order_id)` | Resolves an order through `returns.get_order`; 404 for unknown ID. | Read-only, simulated |
| `GET /api/returns[?order_id=…]` | `return_cases(order_id?)` | Returns cases and each case's stored events. | Read-only, simulated |
| `POST /api/returns/eligibility` | `ReturnRequest {order_id,item_id,reason}` | Uses backend policy; returns `{eligible,reasons,simulated}`. `reason` is accepted but not part of current policy evaluation. | Read-only, simulated |
| `POST /api/returns` | `ReturnRequest`; 201 | Rechecks eligibility, creates a case and `return_requested` event; 409 if ineligible. | Mutating, simulated |
| `GET /api/returns/{case_id}` | `return_detail(case_id)` | Returns one case and ordered events; 404 if missing. | Read-only, simulated |
| `POST /api/returns/{case_id}/pickup/schedule` | `{pickup_date: date}` | Requires `requested`; rejects past dates; appends schedule event. | Mutating, simulated |
| `POST /api/returns/{case_id}/pickup/missed` | No body | Requires `pickup_scheduled`; records a demo missed-pickup event. | Mutating, simulated |
| `POST /api/returns/{case_id}/availability` | `{availability: string}` | Requires `missed_pickup`; stores availability and event. | Mutating, simulated |
| `POST /api/returns/{case_id}/pickup/reschedule` | `{pickup_date: date}` | Requires `availability_collected` and a non-empty availability; appends reschedule event. | Mutating, simulated |
| `POST /api/returns/{case_id}/simulate/advance` | `{to_status: string}` | Enforces next state, writes pickup/shipment/refund evidence; only the final refund event resolves the case. | Mutating, simulated |
| `GET /api/activity` | No body | Reads event rows joined to case/order IDs. | Read-only, simulated |
| `POST /api/ai/chat` | `AssistantChatRequest` → `AssistantChatResponse` | Validates message (1–2,000 chars), optional case/order ID (max 80, pattern restricted), rejects extra fields and simultaneous IDs; builds context server-side; calls NVIDIA. | Read-only AI; demo/development only |
| `GET /api/ai/models` | No body | Calls the Nebius client and lists NVIDIA-prefixed model IDs available through Nebius. 503 if Nebius is unconfigured. | External read call (Nebius) |
| `POST /api/ai/ping` | No body | Makes a Nebius inference call. 503 if unconfigured. | External inference (Nebius) |

Chat response schema is `{answer, model, facts, data_source: "simulated"}`. `AssistantError` is converted to an HTTP error with a controlled code/message. There is no conversation-history API or database persistence.

### Database and initialization

SQLite path defaults to `backend/cygnus.db` and can be overridden with `DATABASE_PATH`. `db.connect()` creates a `sqlite3.Connection`, sets `row_factory=sqlite3.Row`, commits on normal context exit, and closes in `finally`; an exception prevents the commit and closing the connection rolls back pending work. There is no SQLAlchemy/session layer.

[`backend/app/returns.py`](../backend/app/returns.py) `returns.initialize()` creates four tables using `CREATE TABLE IF NOT EXISTS`:

| Table | Important fields and relationship |
|---|---|
| `orders` | `id`, retailer, order date, `simulated` |
| `order_items` | item ID, order ID, product name/SKU, quantity, price, return-window days, final-sale flag |
| `return_cases` | case/order/item IDs, reason, text status, availability, resolved flag, timestamps, `simulated` |
| `case_events` | append-style event type/message, JSON evidence, timestamp, `simulated` |

Schema references declare foreign keys, but connection setup does not enable SQLite `PRAGMA foreign_keys`; enforcement is therefore not guaranteed. There is no migration strategy, schema version, or database model/enum layer. Status is stored as text and constrained by service transition checks.

If `orders` is empty, startup seeds four fictional demo orders/items and one initial case. Seeds are not retailer imports. All workflow state/event writes use `returns.connect()`; reads reconstruct dictionaries from rows. `case_events` is the timeline/evidence source.

### Business rules and lifecycle

Eligibility is implemented in `returns.eligibility()`: an order/item must exist; order age must not exceed the item's return-window days; item must not be final sale; and there must be no unresolved case for that order/item. Age is computed from `date.today()`. Equality at the return-window boundary is allowed because rejection uses `age_days > return_window_days`.

Creation checks eligibility, then inserts the case and request event. The check and insert use separate connections, so concurrent duplicate requests could both pass; no unique constraint or idempotency key prevents that race.

```text
requested -> pickup_scheduled
pickup_scheduled -> missed_pickup -> availability_collected -> pickup_scheduled
pickup_scheduled -> picked_up -> in_transit -> delivered -> resolved
```

Every transition is simulated. The final API request uses `to_status="refund_issued"`; the backend records a `refund_issued` event/evidence and sets case status to `resolved`. That is not proof of money received. There is no real pickup slot, shipment scan, refund processor, or bank evidence. Statuses are checked in service code; request `to_status` itself is an unrestricted string rejected unless it is the next allowed transition.

## AI Architecture

### NVIDIA request path

```text
v0 AssistantPanel
  -> frontend askAssistant() (message + optional case_id/order_id only)
  -> POST /api/ai/chat (Pydantic validation; development/demo gate)
  -> nvidia.build_context() reads returns/orders/events from SQLite
  -> nvidia.answer() calls OpenAI SDK against NVIDIA /v1/chat/completions
  -> first assistant choice is parsed and returned with backend facts
  -> UI labels AI explanation separately from backend-recorded simulated facts
```

[`backend/app/ai/nvidia.py`](../backend/app/ai/nvidia.py) creates an `OpenAI` client from `SecretStr`, configured base URL, a 20-second timeout, and zero SDK retries. It sends system instructions plus the question and backend facts; output is bounded to 450 tokens, with NVIDIA-supported `temperature=1.0`, `top_p=0.95`, and `chat_template_kwargs.enable_thinking=false`. No tools are passed, so the model cannot invoke workflow actions.

Context selection is server-side. An order selection retrieves the order/items and deterministic current eligibility result. A case selection retrieves its order, item, current status, up to 12 recent events, and next permitted transition. Raw customer availability text is deliberately withheld; the context only says it exists. No user/account identity is involved. No chat history is retained between page loads.

The service maps missing configuration, auth failures, 429s, timeout, connection/provider failures, and malformed/empty responses to controlled `AssistantError` messages. The route returns no exception traceback. A heuristic phrase check withholds direct generated claims that contradict ineligibility, unresolved status, or missing refund/bank evidence. This is not semantic proof; frontend separately displays backend facts as authoritative.

### Nebius relationship

`nebius.py` is a separate OpenAI SDK client for Token Factory. It uses `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, and `NEBIUS_MODEL_ID`. `/api/ai/models` and `/api/ai/ping` call Nebius; `/api/ai/chat` calls NVIDIA directly. The clients share the SDK protocol but are not interchangeable without configuration/provider changes. Existing Nebius route handlers include provider exception text in HTTP details, a separate area for future error-sanitization review.

### AI limitations

- No customer authentication exists. Chat is blocked when `APP_ENV` is outside `development`/`demo`; the default is `development`, so deployments must set the environment deliberately.
- All non-AI order/return routes are also unauthenticated. Current records are seeded demo data only; production use requires authorization and tenant-scoped data access.
- Context facts are short string summaries, not citations/typed provenance objects. The returned `facts` list is explicit but the heuristic answer guard can miss nuanced contradictions.
- Original eligibility decision is not stored as a case event; the assistant cannot truthfully reconstruct historical approval/rejection reasons.
- No rate-limit policy, per-user quota, conversation persistence, or prompt-evaluation suite exists.

## Frontend Architecture

React 19, TypeScript 7, Vite 8, Tailwind CSS 4, and lucide-react. `main.tsx` mounts `App`; `router.ts` uses hash routing and maps legacy `#/dashboard` to Overview. No router library or global state framework is used.

| Page/area | Data and state |
|---|---|
| Landing | `listReturns()` preview; v0 marketing/evidence sections and simulated labels |
| Overview | Cases, activity, summary counts, and `AssistantPanel` |
| Returns | `GET /api/returns`, filters/search, empty/error/loading states |
| Return detail | Case, order, event timeline, backend next-step mapping, simulation controls |
| Reschedule | Availability collection then date submission to existing workflow endpoints |
| Agent Activity | Event feed from `GET /api/activity`; no agent task/approval API |
| Orders | Seeded orders, eligibility check, return creation |

`AppShell`, `Nav`, Wordmark, case/evidence components, `Kit`, and `index.css` implement the v0 porcelain/paper, cobalt, Geist/Instrument Serif visual system. Mobile uses a horizontal workspace nav; desktop uses a sidebar. Responsive styling exists, but no mobile viewport test is recorded in this audit.

[`frontend/src/lib/api.ts`](../frontend/src/lib/api.ts) is the sole fetch/data adapter. `VITE_API_BASE_URL` defaults to empty; Vite proxies `/api` to `127.0.0.1:8000` in development. Production must set the public URL appropriately; `VITE_*` values are shipped to browsers and must never contain server credentials. The adapter maps snake_case data into display types and derives some UI fields (for example return-window end date and stage). It maps only selected item IDs to local images and does not invent courier/payment data. v0 simulator code from the removed backup is not present in the active frontend.

## Environment and Developer Workflow

| Variable | Purpose | Secret? |
|---|---|---|
| `NVIDIA_API_KEY` | NVIDIA API Catalog bearer credential | Yes; backend only |
| `NVIDIA_MODEL` | NVIDIA model ID | No; defaults to Nemotron 3.5 Lightning 30B A3B |
| `NVIDIA_BASE_URL` | NVIDIA API base | No; defaults to `https://integrate.api.nvidia.com/v1` |
| `NEBIUS_API_KEY` | Separate Nebius Token Factory credential | Yes; backend only |
| `NEBIUS_MODEL_ID`, `NEBIUS_BASE_URL` | Nebius model/base URL | No |
| `APP_ENV`, `CORS_ORIGINS`, `DATABASE_PATH` | App gate, allowed browser origins, SQLite path | No |
| `VITE_API_BASE_URL` | Frontend API origin override | Public; never a secret |

Root `.env.example` is the tracked placeholder template. Root `.gitignore` ignores `.env` and `.env.*` while allowing `.env.example` and `frontend/.env.example`; it also ignores `backend/.venv/`, `node_modules/`, `frontend/dist/`, Python caches, and SQLite files. `backend/.env` is ignored and not tracked. No `backend/.env.example` exists.

README documents Node 20+ and Python 3.11+. From repository root, start separate terminals:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

```powershell
Set-Location frontend
npm install
npm run dev
```

Checks from the corresponding directories: `python -m pytest -q`; `npm run lint`; `npm run build` (includes `tsc -b`). No dependency install/upgrade was performed for this handover. A `npm run dev` invocation in the supplied terminal history exited 1; its cause was not captured in this audit. Vite configuration expects port 5173, which may already be occupied by an existing server.

## Security and Integration Matrix

| Area | Current status | Boundary / risk |
|---|---|---|
| NVIDIA | Implemented; prior A2 reported a successful live connectivity check | Current chat is read-only and demo-gated; generated text still needs human judgment |
| Nebius | Separate diagnostic client/routes | Not used by current chat; error detail sanitization differs |
| Authentication | Not implemented | APIs are unauthenticated; chat only environment-gated. Do not expose demo API as customer-facing production service |
| Order data | Seeded SQLite demo records | No retailer integration or user scoping |
| Amazon / Flipkart | Not implemented | Would require official API access/approval and data-access design |
| Return submission | Simulated backend case creation | No real retailer RMA or return submission |
| Courier/pickup | Simulated transitions and availability/date records | No carrier, pickup-slot, tracking, or dispatch integration |
| Refund/payment | Simulated `refund_issued` event | No processor/bank confirmation; `resolved` does not mean funds credited |
| Evidence storage | SQLite `case_events` JSON evidence, marked simulated | No external source-of-truth evidence |
| Secrets | `SecretStr`, ignored local env, server-side SDK client | Never use `VITE_*`; no secret values were read during this audit |
| Logging | No application logging framework found | Review any future logs/telemetry to avoid message/credential leakage |

## Tests and Current Verification

| Tests | Coverage |
|---|---|
| `backend/tests/test_health.py` | Health and no-key Nebius ping behavior; global `TestClient`, not isolated DB fixture |
| `backend/tests/test_returns.py` | Seeded lists, deterministic eligibility, case creation, missed pickup/reschedule, ordered evidence, resolution guard; fixture uses `tmp_path` SQLite and TestClient lifespan |
| `backend/tests/test_nvidia.py` | Fake settings; HTTPX `MockTransport`; endpoint/model/body/auth-header presence; provider 401/429/5xx, timeout/outage, malformed/empty response; backend context, contradiction fallback, validation, demo gate, health key omission |

During this handover task: full backend suite **32 passed**; frontend `npm run lint` **passed**; frontend `npm run build` **passed** (`tsc -b` and Vite); frontend credential-pattern scan found no matches in 42 text source/build assets; `git diff --check` passed. No live provider/retailer/payment request was made for this documentation task. A prior A2 report records one live NVIDIA connectivity success; that was not repeated here.

Pylance diagnostics during the audit reported unresolved FastAPI imports in its selected editor environment and two inferred-type issues in `nvidia.py` (`eligibility` may be `None`, and the SDK content union's `text` member). The configured `backend/.venv` test run and Python syntax checks pass; no mypy/pyright command is configured in the project. Align the editor interpreter and review those type diagnostics separately.

## DO NOT BREAK

1. Keep `config.py` as the single settings source; preserve root-then-backend env-file precedence, process-env override, and `SecretStr` key fields.
2. Never place NVIDIA/Nebius credentials in frontend code, `VITE_*`, API responses, logs, tests, or docs.
3. Keep the frontend’s `/api` contracts and the snake_case-to-view-model adapter synchronized with FastAPI responses.
4. Keep SQLite records/events as workflow truth. AI is read-only; it must not create or advance a case.
5. Preserve status guards: eligibility is deterministic; transition order is enforced in `returns.py`; resolve only after the `refund_issued` evidence event.
6. Preserve simulation labels. Refund-issued is not bank-credit evidence; no real retailer, courier, payment, or bank is connected.
7. Preserve hash routes, `#/dashboard` alias, v0 responsive shell, typography, and colors.
8. Keep tests isolated: workflow/AI route fixtures use temporary DB paths; provider tests use `MockTransport` and fake credentials.
9. Preserve uncommitted changes. At handover start, only `backend/tests/test_nvidia.py` was modified; do not reset, stage, or rewrite its history.

## Prioritized Technical Backlog

| Priority | Work and value | Files/dependencies | Risks and verification | External approval |
|---|---|---|---|---|
| P0 security | Add authentication/authorization and tenant-scoped order/case access before non-demo deployment | `main.py`, config, frontend session strategy | Prevent cross-user disclosure; test unauthorized and cross-tenant access | Identity provider/operations approval may be needed |
| P1 data integrity | Persist the original eligibility decision and policy version as an event | `returns.py`, schema/versioning plan, tests, adapter | Requires migration and compatibility plan; test old/new DBs and historical explanations | No, but product-policy approval needed |
| P1 integrity | Make duplicate-case creation atomic; enable/verify SQLite FK constraints | `db.py`, `returns.py`, DB tests | Avoid duplicate concurrent cases and orphan records; concurrency/integrity tests | No |
| P1 AI safety | Replace simple text-pattern contradiction checks with structured answer claims or deterministic templates | `nvidia.py`, schemas, prompt tests | Must not let model override status; adversarial/fuzz tests and manual review | No |
| P2 reliability | Add request throttling, usage limits, and bounded operational telemetry | API middleware/service configuration | Cost/abuse risk; verify no secrets or PII in logs | NVIDIA account quota/policy may apply |
| P2 UX | Test narrow mobile layouts, keyboard flow, and empty/loading/error variants | frontend pages/components | Avoid regressions to v0 design; browser/responsive tests | No |
| P2 documentation | Reconcile older architecture, learning, implementation, compliance docs and README test count | `docs/*.md`, `README.md` | Avoid documenting plans as implemented; source review | No |
| P3 integrations | Evaluate retailer/courier/payment adapters only after MVP authorization and evidence contracts | New adapters, config, schemas, tests | Real-world state changes and sensitive data require threat model and rollback plan | Yes: each provider's API approval/credentials/terms |

## Documentation Drift and Uncertainty

- Several existing docs still describe the earlier Part 1/2 plan, Nebius as the only AI path, or tables/routes as future work; current source is newer.
- `README.md` still gives an expected backend test count that differs from the observed 32.
- There is no deployed configuration or production hosting manifest in the repository.
- No authentication model exists, so all route tables above explicitly state unauthenticated access.
- Mobile responsiveness is implemented in styles but was not tested at a mobile viewport during this audit.

## Git State

- **Before writing:** branch `main`; modified `backend/tests/test_nvidia.py`; no other changed files reported.
- **After writing:** same existing test modification plus untracked `docs/TECHNICAL_HANDOVER.md`; no staged files.
- `backend/.env` is ignored and not tracked; no history entry for that path was found. The removed `cygnus-j0-main` directory remains absent.
- `git diff --check` passed after writing. Windows line-ending notices may be emitted by Git for existing files.