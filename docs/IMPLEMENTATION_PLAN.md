# Implementation plan

## Time reality check

Deadline: **Fri 30 Oct 2026, 10:00 AM PDT = 22:30 IST.**
When Part 1 was built, the container clock read about 11:00 IST on 29 Oct, so roughly **35 hours** remained, including sleep. Treat **feature freeze at about 08:00 IST on 30 Oct** and aim to submit with several hours of slack. A polished, smaller product beats a half-working bigger one.

## Part 1: Foundation (done)

- [x] Repo, React + TS + Tailwind frontend, FastAPI backend, SQLite check
- [x] Landing page, dashboard, `/api/health`, frontend-to-backend connection
- [x] Nebius client + `scripts/check_llm.py`
- [x] Compliance research, docs, license
- [ ] **Blocked on you:** Token Factory key + one real inference call (see below)

## Do first (before Part 2), about 20 minutes

1. Join Devpost hackathon (done if you registered) and read the **Overview** and **Resources** tabs.
2. Create a Token Factory account and key. Apply credits (`NEBIUS-DEVPOST-GLOBAL26` per the FAQ, and/or the Builder Program).
3. If your country is missing at signup, ask on the Nebius Discord now. This is the biggest schedule risk.
4. Put the key in `.env`, run `python scripts/check_llm.py`, and paste me the printed model list and result.

## Part 2: Core agent on a simulated store (about 5 h)

- Tables: `orders`, `order_items`, `return_requests`, `pickups`, `case_events`
- `SimulatedRetailer`: seeded demo orders (including the "wrong-size shoes" case), a return policy, a fake courier
- Tools: `find_order`, `get_return_policy`, `check_eligibility`, `create_return`
- Agent loop with Nemotron function calling; `POST /api/chat`
- Frontend: chat panel + case timeline showing each step and its evidence
- **Done when:** the shoes message produces an eligible, initiated return with a labelled `SIMULATED` timeline.

## Part 3: Tracking, failure handling, evidence (about 5 h)

- "Simulate next day" control that advances the fake courier
- Missed-pickup detection → agent asks availability → `reschedule_pickup`
- Return in transit → delivered → refund issued, each confirmed from status data
- Fallbacks: model returns bad output or Nebius errors → clear message, case state stays safe
- Backend tests for tools and the loop (mock the LLM)
- **Done when:** the full 12-step story runs in under 3 minutes on demand.

## Part 4: Ship (about 5 h, reserve more)

- Optional: Tavily call to fetch a real retailer return policy (Tavily bonus prize needs a functional runtime call)
- Deploy: simplest reliable host for the web app plus the backend; a Nebius Serverless Endpoint or Job is encouraged but not required. The Nebius runtime call to Token Factory already satisfies the platform rule.
- Public GitHub repo, MIT license detected, README section on NVIDIA/Nebius use
- Demo video under 3 min, public on YouTube
- Devpost description, track (**Best Apps and Agents**), feedback section
- Test the demo URL in an incognito window; submit with slack

## Cut list if time runs short (drop in this order)

1. Tavily integration
2. Rescheduling UI polish (keep the logic)
3. Extra demo orders beyond the shoes story
4. Fancy animations

**Never cut:** real Nebius call at runtime, hosted demo URL, YouTube video, feedback section, "simulated" labels.

## Exact next step

Do the 20-minute "Do first" list, then tell me: *key works / key blocked*, and paste the `check_llm.py` output. Then say **"Part 2"**.
