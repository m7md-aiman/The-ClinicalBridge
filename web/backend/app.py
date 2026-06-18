"""FastAPI backend for the ClinicalBridge showcase website.

A thin API over the existing multi-agent pipeline:
- read endpoints serve bundled, precomputed runs (no API key needed);
- the live endpoints run the real pipeline and stream steps via SSE (when a key is configured).

Run (dev):   uvicorn web.backend.app:app --reload --port 8000
Run (prod):  build the frontend to web/frontend/out, then uvicorn web.backend.app:app  (serves both)
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from clinicalbridge.config import settings
from clinicalbridge.scenarios import get_scenario
from web.backend import cache
from web.backend.streaming import run_event_stream

app = FastAPI(title="ClinicalBridge API", version="1.0.0")

# Dev: the Next dev server (localhost:3000) calls this API on :8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/meta")
def meta() -> dict:
    return {
        "live_available": cache.live_available(),
        "model": settings.default_model,
        "name": "ClinicalBridge",
    }


@app.get("/api/scenarios")
def scenarios() -> list[dict]:
    return cache.list_scenarios()


@app.get("/api/scenarios/{scenario_id}")
def scenario(scenario_id: str) -> dict:
    try:
        return cache.scenario_detail(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario {scenario_id!r}")


@app.get("/api/results/{scenario_id}")
def result(scenario_id: str) -> dict:
    payload = cache.result_payload(scenario_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cached run for {scenario_id!r}. Build it: python scripts/build_web_cache.py",
        )
    return payload


@app.get("/api/evaluation")
def evaluation() -> dict:
    return cache.evaluation_report()


@app.get("/api/run/stream")
async def run_stream(scenario: str) -> EventSourceResponse:
    """Live pipeline run for a scenario, streamed as SSE step events."""
    if not cache.live_available():
        raise HTTPException(status_code=503, detail="Live runs unavailable: OPENROUTER_API_KEY not set.")
    try:
        s = get_scenario(scenario)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario {scenario!r}")
    return EventSourceResponse(run_event_stream(s.alert))


# --- Production: serve the exported Next.js site (if present) -----------------
_FRONTEND_OUT = Path(__file__).resolve().parents[1] / "frontend" / "out"
if _FRONTEND_OUT.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_OUT), html=True), name="site")
