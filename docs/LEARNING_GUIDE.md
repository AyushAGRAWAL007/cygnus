# Learning guide (revision notes)

Each concept: **one line → Cygnus example → try it**. Read in order; it takes about 15 minutes.

## Memory hook: **See, Serve, Store, Think**

| Word | Tech | Cygnus example |
|---|---|---|
| **See** | React | The Dashboard page the customer looks at |
| **Serve** | FastAPI | The server that answers "is the backend healthy?" |
| **Store** | SQLite | Where each return's progress is saved |
| **Think** | Nemotron (via Nebius) | Reads "wrong size, want refund" and picks the next step |

---

## 1. React = the part the customer sees

*Builds screens out of small reusable pieces (components) that redraw when data changes.*

**Example:** `frontend/src/pages/Dashboard.tsx` shows three status rows. When the backend answers, the "Backend" row flips from *Checking…* to *Online*. You never edit the page by hand; React redraws it because the data (state) changed.

**Try it:** run the frontend, open Dashboard, then stop the backend and click **Refresh**. The row turns red.

**TypeScript** = JavaScript with labels on data. In `src/lib/api.ts`, `interface Health` says what the backend's answer looks like. If you mistype `h.databse`, the editor flags it before the app runs.

## 2. FastAPI = the server that processes requests

*A Python program that waits for requests and runs a function for each URL.*

**Example:** in `backend/app/main.py`, `@app.get("/api/health")` means "when someone asks for `/api/health`, run `health()` and send back its result as JSON."

**Try it:** open <http://127.0.0.1:8000/docs>. FastAPI generates a clickable test page for every route for free.

## 3. API = an agreed channel between two parts

*A list of URLs plus the exact shape of data each one accepts and returns.*

**Example:** the browser sends `GET /api/health`; the server replies `{"status":"ok","database":"ok",...}`. Both sides agreed on those names, so they can be built separately.

**Mnemonic:** API = **A**greed **P**ostal **I**nterface: an address (URL) and a labelled envelope (JSON).

## 4. Database = where progress is remembered

*Without it, a restart forgets every return.*

**Example (Part 2):** a table `return_requests` with one row per return: `order_id`, `status`, `pickup_date`. Missed pickup detected → update `status`, add a row to `case_events`. SQLite keeps all of this in one file, `backend/cygnus.db`.

## 5. Environment variables = settings kept outside the code

*Secrets and per-machine settings live in `.env`, never in source files.*

**Example:** `NEBIUS_API_KEY` goes in `.env`. `config.py` reads it. `/api/health` only says `"configured": true`. The key never reaches the browser or git.

**Rule:** anything starting with `VITE_` is shipped to the browser, so it is public. Never put a key there.

## 6. Proxy = a forwarder

**Example:** the browser asks Vite (port 5173) for `/api/health`. Vite forwards it to FastAPI (port 8000). The React code just writes `/api/health`, with no address to remember.

## 7. AI agent = software that plans and acts toward a goal

*A chatbot answers. An agent also **does** permitted things.*

**Worked example (Part 2):**
1. Customer: "Wrong size shoes, refund please."
2. Model decides: call `find_order`. Our code runs it, returns order #1042.
3. Model decides: call `check_eligibility`. Result: eligible, 30-day window, 12 days used.
4. Model decides: call `create_return`. Our code creates it (simulated, labelled).
5. Later: pickup missed → model decides: call `message_customer`, asking for a time.

**Mnemonic: OPAV** = **O**bserve → **P**lan → **A**ct → **V**erify. Verify matters most: "refunded" is only said when status data proves it.

**Safety principle:** the model only *chooses* from tools we wrote. It cannot do anything we did not expose.

## 8. OpenAI-compatible API = a common language for LLM servers

*Nebius Token Factory accepts the same request format as OpenAI, so we use the `openai` Python library and just change `base_url`.*

**Example:** `backend/app/ai/nebius.py`:
```python
OpenAI(api_key=..., base_url="https://api.tokenfactory.nebius.com/v1/")
client.chat.completions.create(model="nvidia/...", messages=[...])
```
Same code shape as any chat-model tutorial; the `model` string picks Nemotron.

---

## Exercises (10 minutes)

1. Add a field `"hello": "world"` to `health()` in `main.py`. Reload `/api/health`. (FastAPI auto-reloads.)
2. Add `hello: string` to `interface Health` and display it on the Dashboard. (Types → UI chain.)
3. Run `python scripts/check_llm.py` without a key, then with one. Compare the outputs.
