# Cygnus

**An AI agent that manages shopping returns and refunds from start to finish.**
Built for the [Nebius × NVIDIA Global AI Hackathon 2026](https://nebiusglobalaihackathon.devpost.com/) (track: *Best Apps and Agents*).

> A customer says: *"I ordered shoes, received the wrong size, and want my money back. Please handle the return."*
> Cygnus understands the problem, checks the policy, starts the return, chases the courier, reschedules missed pickups, and confirms the refund **using real status evidence**.

## Honesty note

Real retailer APIs are not available, so Cygnus runs against a **simulated shopping platform**. Every simulated action is labelled in the UI and the API. Cygnus never claims a real refund or pickup happened.

## Status: Part 1 complete (foundation)

| Works now | Not built yet (see `docs/IMPLEMENTATION_PLAN.md`) |
|---|---|
| React + TypeScript + Tailwind landing page and dashboard | Agent loop and tool calling |
| FastAPI backend with `/api/health` | Simulated retailer + order/return tables |
| Dashboard reads live backend status | Pickup tracking, missed-pickup detection, rescheduling |
| SQLite connectivity check | Deployment and demo video |
| Nebius client + `scripts/check_llm.py` (needs your API key to run) | |

## Stack (mnemonic: **See, Serve, Store, Think**)

| Role | Tech |
|---|---|
| See | React + TypeScript (Vite), Tailwind CSS v4 |
| Serve | Python + FastAPI |
| Store | SQLite |
| Think | NVIDIA Nemotron via Nebius Token Factory (OpenAI-compatible API) |

## Quick start

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

Check: open <http://127.0.0.1:8000/api/health>. You should see `"status":"ok"`. API docs: <http://127.0.0.1:8000/docs>.

**2. Frontend** (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>, click **Dashboard**. Backend and Database should show green.

**3. AI (needs a Nebius key)**

```bash
# from the repo root
cp .env.example .env        # Windows: copy .env.example .env
# edit .env and paste NEBIUS_API_KEY, then:
cd backend
python scripts/check_llm.py
```

Success prints your `nvidia/*` model ids, then `Reply   : Cygnus online` and a latency. Copy the exact model id into `NEBIUS_MODEL_ID` in `.env`.

## Tests and checks

```bash
cd backend  && python -m pytest -q      # expect: 3 passed
cd frontend && npm run lint && npm run build   # expect: 0 warnings, built in <1s
```

## Project layout

```
backend/app/main.py       API routes (health, AI status/ping)
backend/app/config.py     The only place environment variables are read
backend/app/db.py         SQLite connection helper
backend/app/ai/nebius.py  Nebius Token Factory client (server-side only)
backend/scripts/          check_llm.py (validates the AI path)
frontend/src/             React app (pages, hooks, api client)
docs/                     Architecture, compliance, learning guide, plan
```

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how the pieces fit
- [`docs/HACKATHON_COMPLIANCE.md`](docs/HACKATHON_COMPLIANCE.md): verified rules and checklist
- [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md): concepts with Cygnus examples
- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md): remaining work against the deadline

## License

MIT, see [`LICENSE`](LICENSE).
