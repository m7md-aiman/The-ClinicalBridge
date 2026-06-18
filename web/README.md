# ClinicalBridge — Showcase Website

A professional, modern web showcase for the ClinicalBridge multi-agent system. It runs the **real
pipeline** behind a thin FastAPI layer and presents three sections:

- **Overview** — the Clinical Context Gap, the architecture, and the safety story.
- **Interactive Demo** — pick a scenario, watch the pipeline trace, read the cited Clinical Context
  Brief, compare against the gold standard, and (optionally) run it live.
- **Evaluation** — the metrics dashboard and the v1 → v2 → guardrail improvement chart.

Stack: **Next.js 16 + React 19 + TypeScript + Tailwind v4 + Framer Motion + Recharts** (frontend),
**FastAPI** (backend over `clinicalbridge.Orchestrator`).

---

## Run it

### Option A — Production (one command serves everything)
The frontend is statically exported and served by FastAPI, so the whole site + API run on one port.
Works **without an API key** (bundled cached runs); a key just enables the live "Run" button.

```bash
# 1. Build the static frontend (once)
npm --prefix web/frontend install        # first time only
npm --prefix web/frontend run build       # outputs web/frontend/out

# 2. Serve site + API together
.venv/Scripts/python -m uvicorn web.backend.app:app --port 8000
# open http://localhost:8000
```

### Option B — Development (hot reload, two servers)
```bash
# Terminal 1 — API
.venv/Scripts/python -m uvicorn web.backend.app:app --reload --port 8000

# Terminal 2 — frontend (auto-detects the :8000 API)
npm --prefix web/frontend run dev
# open http://localhost:3000
```

---

## Data: cached vs live
- **Cached (default):** `web/backend/data/` holds precomputed runs, the evaluation snapshot, and the
  iteration progression. Committed so the site works with no key. Regenerate with:
  ```bash
  .venv/Scripts/python scripts/build_web_cache.py   # needs OPENROUTER_API_KEY + built vector store
  ```
- **Live:** with `OPENROUTER_API_KEY` set, the Demo shows a **Run live** button that streams each
  agent step over SSE and produces a fresh brief.

## API endpoints
`GET /api/meta` · `GET /api/scenarios` · `GET /api/scenarios/{id}` · `GET /api/results/{id}` ·
`GET /api/evaluation` · `GET /api/run/stream?scenario={id}` (SSE, live).

## Tests
```bash
.venv/Scripts/python -m pytest tests/test_web_api.py   # backend (offline, against cache)
```

## Notes
- The website is additive and isolated; it does not change the clinical logic (only an optional
  `on_event` streaming hook on the orchestrator).
- All patient data is fully simulated. This is a capstone proof-of-concept, not a medical device.
