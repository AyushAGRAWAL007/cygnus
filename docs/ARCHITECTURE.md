# Architecture

## Big picture

```
 Customer's browser                     Your server                         Outside world
┌───────────────────┐   /api/*    ┌──────────────────────┐   HTTPS   ┌──────────────────────────┐
│ React + TypeScript│ ──────────► │ FastAPI (Python)     │ ────────► │ Nebius Token Factory     │
│  (see)            │ ◄────────── │  (serve)             │ ◄──────── │  NVIDIA Nemotron (think) │
└───────────────────┘    JSON     │   │                  │           └──────────────────────────┘
                                  │   ├─ SQLite (store)  │
                                  │   └─ Simulated       │           (later, optional)
                                  │      retailer        │ ────────► Tavily search
                                  └──────────────────────┘
```

**Rule 1:** the browser never talks to Nebius. Only the backend does, so the API key stays secret.
**Rule 2:** the model proposes; our code decides. The AI can only trigger actions we expose as tools.

## Components

| Part | Folder | Job |
|---|---|---|
| Frontend | `frontend/` | Landing page, dashboard, later the chat and case timeline |
| API | `backend/app/main.py` | Routes. Thin: validate input, call services, return JSON |
| Config | `backend/app/config.py` | Single source of environment settings and secrets |
| Database | `backend/app/db.py` | SQLite connection. Tables added in Part 2 |
| AI client | `backend/app/ai/nebius.py` | OpenAI-compatible calls to Token Factory |

## Planned design (Parts 2 to 3)

**The agent loop (Observe → Plan → Act → Verify):**
1. *Observe*: read the customer message and the case's current state from SQLite.
2. *Plan*: ask Nemotron which tool to call next (function calling).
3. *Act*: our code runs the tool against the simulated retailer.
4. *Verify*: re-read the resulting status. Only status evidence can mark a step done.
Loop until the case is complete or needs the human.

**Tools the model may call** (each is a plain Python function that returns structured data):
`find_order`, `get_return_policy`, `check_eligibility`, `create_return`, `get_pickup_status`, `reschedule_pickup`, `get_refund_status`, `message_customer`.

**Planned tables:** `orders`, `order_items`, `return_requests`, `pickups`, `case_events` (append-only timeline: what happened, when, who or what did it, and the evidence).

**Simulated retailer:** a module behind an interface (`RetailerAdapter`). A `SimulatedRetailer` implements it now; a real adapter could replace it without changing the agent. A "simulate next day" control moves time forward so missed pickups can be demonstrated on demand.

## Decisions and why

| Decision | Reason |
|---|---|
| Vite proxy for `/api` in dev | No CORS pain, frontend does not hardcode backend address |
| `openai` SDK pointed at Nebius | Token Factory is OpenAI-compatible; less code, familiar API |
| Model id from env, not hardcoded | Ids vary in casing and change; confirm with `/v1/models` |
| SQLite | Zero setup, one file, enough for a demo. Swap later if needed |
| Hash routing, no router library | Two pages only; fewer dependencies |
| No component library | Tailwind alone is enough for two pages; less to learn and ship |
| Append-only `case_events` | Gives the "evidence" the product promises, and a timeline for the demo |

## Security notes

- `.env` is git-ignored; `/api/health` reports only *whether* a key exists.
- `VITE_*` variables are public by design. Never put secrets there.
- Simulated actions carry a `simulated: true` flag end to end (planned), so the UI and logs cannot present them as real.
