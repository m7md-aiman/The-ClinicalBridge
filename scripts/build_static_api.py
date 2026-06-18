"""Generate static JSON snapshots of the read API, so the website works as a pure static deploy
(e.g. on Vercel) with NO backend and NO API key.

Writes web/frontend/public/data/{meta,scenarios,evaluation}.json and results/<id>.json — mirroring
the FastAPI read endpoints. On the static deploy these are served directly (via vercel.json rewrites
and/or the frontend's static fallback). Live "Run" is disabled there (meta.live_available = false).

Offline: reads the committed web cache; no LLM calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))          # for the `web` package
sys.path.insert(0, str(ROOT / "src"))  # for `clinicalbridge`

from clinicalbridge.config import settings  # noqa: E402
from clinicalbridge.scenarios import build_scenarios  # noqa: E402
from web.backend import cache  # noqa: E402

OUT = ROOT / "web" / "frontend" / "public" / "data"


def main() -> None:
    (OUT / "results").mkdir(parents=True, exist_ok=True)

    (OUT / "meta.json").write_text(
        json.dumps({"live_available": False, "model": settings.default_model, "name": "ClinicalBridge"},
                   indent=2), encoding="utf-8")
    (OUT / "scenarios.json").write_text(json.dumps(cache.list_scenarios(), indent=2), encoding="utf-8")
    (OUT / "evaluation.json").write_text(json.dumps(cache.evaluation_report(), indent=2), encoding="utf-8")

    n = 0
    for s in build_scenarios():
        payload = cache.result_payload(s.id)
        if payload:
            (OUT / "results" / f"{s.id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            n += 1

    print(f"[OK] Wrote static API snapshots to {OUT} (meta, scenarios, evaluation, {n} results)")


if __name__ == "__main__":
    main()
