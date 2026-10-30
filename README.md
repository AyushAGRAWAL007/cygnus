# Cygnus

**A simulated returns and refunds workflow demo.**
Built for the [Nebius × NVIDIA Global AI Hackathon 2026](https://nebiusglobalaihackathon.devpost.com/) (track: *Best Apps and Agents*).

> A customer says: *"I ordered shoes, received the wrong size, and want my money back. Please handle the return."*
> Cygnus checks seeded order eligibility, records return-case events, and walks through simulated pickup, shipment, and refund status changes.

## Honesty note

There are no retailer, courier, payment-network, or bank integrations. Orders, pickups, shipment events, and refund issuance are simulated and labelled in the UI and API. A resolved case means a simulated refund-issued event was recorded; it does not mean a bank credit was verified. The NVIDIA assistant is read-only and explains backend records; it cannot change workflow state. The existing Nebius client remains available for diagnostics.

## Status: Integrated MVP

| Works now | Not integrated |
|---|---|
| v0 landing page, overview, returns, return detail, reschedule, activity, and orders screens | Autonomous AI agent loop and tool calling |
| SQLite-backed seeded demo orders, return cases, and event history | Real retailer, courier, pickup-slot, payment, or bank integration |
| Eligibility checks and ordered simulated pickup/shipment/refund transitions | Agent tasks, approvals, and bank-credit confirmation |
| API client connected to the FastAPI workflow; `#/dashboard` remains an alias for `#/overview` | Deployment and demo video |
| Read-only NVIDIA assistant on Overview, grounded in selected backend records | Autonomous AI agent loop or AI-triggered return actions |
| Nebius client and `scripts/check_llm.py` diagnostic | |

## Stack (mnemonic: **See, Serve, Store, Think**)

| Role | Tech |
|---|---|
| See | React + TypeScript (Vite), Tailwind CSS v4 |
| Serve | Python + FastAPI |
| Store | SQLite |
| Think | NVIDIA API Catalog Nemotron (read-only assistant); Nebius client retained for diagnostics |

## Quick start

For customer order-import development, see [Order imports and Gmail test setup](docs/ORDER_IMPORTS.md). It explains how to create a disposable migrated database while preserving the live database. Amazon.in export compatibility still needs a redacted consumer sample; Gmail requires your Google OAuth test-project configuration.

You need Node 20+ and Python 3.11+.

**1. Backend** (terminal 1)

```bash
cd backend
python -m venv .venv
# macOS/Linux:   source .venv/bin/activate
# Windows (PowerShell):   .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Before registering or signing in, apply the account migration to the configured database. On first launch, the backend creates the base database; then run this from `backend` (the default database path is shown):

```bash
python migrations/001_customer_ownership.py cygnus.db
```

If `DATABASE_PATH` is configured, pass that database path instead. Back up an existing database first. The migration preserves existing workflow records and can be rerun safely. Authentication returns “Account service is unavailable” until this migration is applied; application startup does not apply it automatically.

Check: open <http://127.0.0.1:8000/api/health>. You should see `"status":"ok"`. API docs: <http://127.0.0.1:8000/docs>. Workflow routes include `/api/orders`, `/api/returns`, `/api/returns/eligibility`, `/api/activity`, and simulated return-case actions under `/api/returns/{case_id}/`.

**2. Frontend** (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, then choose **Overview**, **Returns**, **Orders**, or **Agent activity**. The legacy `#/dashboard` route opens Overview.

**3. NVIDIA assistant**

The backend reads `NVIDIA_API_KEY`, `NVIDIA_MODEL`, and `NVIDIA_BASE_URL` from environment variables, root `.env`, or `backend/.env`. Defaults are `nvidia/nemotron-3.5-lightning-30b-a3b` and `https://integrate.api.nvidia.com/v1`. Keep the key in the backend environment only; never put it in `frontend/.env` or browser code. If NVIDIA configuration is absent or unavailable, return workflows remain usable and the assistant shows an error rather than inventing an answer.

The existing Nebius diagnostic remains available through `backend/scripts/check_llm.py` and uses its separate `NEBIUS_*` settings.

## Tests and checks

```bash
cd backend  && python -m pytest -q      # expect: 29 passed
cd frontend && npm run lint && npm run build
```

## Project layout

```
backend/app/main.py       API routes (health, AI diagnostics, orders, returns, activity)
backend/app/config.py     The only place environment variables are read
backend/app/db.py         SQLite connection helper
backend/app/returns.py    Seed data, eligibility, simulated workflow, and event evidence
backend/app/ai/nvidia.py  Read-only NVIDIA assistant and backend-context safeguards
backend/app/ai/nebius.py  Nebius Token Factory client (server-side only)
backend/scripts/          check_llm.py (validates the AI path)
frontend/src/             v0 React app, styles, assets, and backend API adapter
cygnus-j0-main/            Untouched extracted v0 source backup
docs/                     Architecture, compliance, learning guide, plan
```

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how the pieces fit
- [`docs/HACKATHON_COMPLIANCE.md`](docs/HACKATHON_COMPLIANCE.md): verified rules and checklist
- [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md): concepts with Cygnus examples
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md): remaining work against the deadline

## License

MIT, see [`LICENSE`](LICENSE).
