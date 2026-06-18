"""Generate the bundled web cache so the showcase site runs with NO API key.

Runs the real pipeline once per scenario and writes:
  web/backend/data/runs/<scenario>.json   — full OrchestrationResult (for the demo + trace)
  web/backend/data/evaluation.json         — evaluation report (for the dashboard)
  web/backend/data/progression.json        — authored v1 -> v2 -> v2+guardrail metrics

Requires OPENROUTER_API_KEY, the generated dataset, and a built vector store. Run once; commit the
output. Re-run to refresh after pipeline/prompt changes.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from clinicalbridge.agents.synthesis import collect_allowed_sources, invalid_citations  # noqa: E402
from clinicalbridge.config import settings  # noqa: E402
from clinicalbridge.evaluation.metrics import score_brief  # noqa: E402
from clinicalbridge.evaluation.runner import aggregate  # noqa: E402
from clinicalbridge.orchestrator import Orchestrator  # noqa: E402
from clinicalbridge.scenarios import build_scenarios  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "web" / "backend" / "data"
RUNS_DIR = DATA_DIR / "runs"

# Authored from docs/prompt_iteration_log.md — the measured improvement story for the dashboard.
PROGRESSION = [
    {"stage": "v1 baseline", "pass_rate": 0.60, "urgency_accuracy": 0.80,
     "mean_must_include_coverage": 0.62, "mean_citation_coverage": 1.0,
     "total_hallucinated_citations": 0, "mean_latency_seconds": 23.2},
    {"stage": "v2 prompts", "pass_rate": 0.80, "urgency_accuracy": 0.80,
     "mean_must_include_coverage": 0.82, "mean_citation_coverage": 1.0,
     "total_hallucinated_citations": 0, "mean_latency_seconds": 25.5},
    {"stage": "v2 + trend guardrail", "pass_rate": 1.00, "urgency_accuracy": 1.00,
     "mean_must_include_coverage": 0.87, "mean_citation_coverage": 1.0,
     "total_hallucinated_citations": 0, "mean_latency_seconds": 18.9},
]


def main() -> None:
    if not settings.is_configured:
        sys.exit("ERROR: OPENROUTER_API_KEY not set. Add it to .env and retry.")
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    orch = Orchestrator()
    scores: list[dict] = []
    print("Building web cache (live pipeline runs)...\n")
    for s in build_scenarios():
        t0 = time.perf_counter()
        res = orch.process_alert(s.alert)
        dt = time.perf_counter() - t0
        (RUNS_DIR / f"{s.id}.json").write_text(json.dumps(res.to_dict(), indent=2), encoding="utf-8")

        allowed = collect_allowed_sources(res.ehr_context, res.anamnesis_summary, include_rpm_trend=True)
        score = score_brief(res.brief, res.final_urgency, s.rubric,
                            allowed_sources=allowed, latency_seconds=dt, errors=len(res.errors))
        score["hallucinated_citations"] = invalid_citations(res.brief, allowed)
        score.update(scenario_id=s.id, title=s.title, patient_id=s.patient_id,
                     expected_urgency=s.expected_urgency.value)
        scores.append(score)
        print(f"  [{'PASS' if score['passed'] else 'FAIL'}] {s.id:<22} "
              f"{res.final_urgency.value:<12} ({dt:.1f}s)")

    report = {"scenarios": scores, "aggregate": aggregate(scores)}
    (DATA_DIR / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (DATA_DIR / "progression.json").write_text(json.dumps(PROGRESSION, indent=2), encoding="utf-8")

    print(f"\n[OK] Cache written to {DATA_DIR}")
    print(f"     runs: {len(scores)} | pass_rate {report['aggregate']['pass_rate']} | "
          f"hallucinations {report['aggregate']['total_hallucinated_citations']}")


if __name__ == "__main__":
    main()
