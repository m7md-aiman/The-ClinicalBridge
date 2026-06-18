"""CLI: run the full evaluation across all scenarios and print/save the report.

Usage:
    python scripts/run_eval.py            # run all scenarios, print report, save JSON
    python scripts/run_eval.py --no-save

Runs the real multi-agent pipeline (LLM calls) once per scenario. Requires OPENROUTER_API_KEY,
the generated dataset, and a built vector store.
"""

from __future__ import annotations

import argparse
import json
import sys

from clinicalbridge.config import settings
from clinicalbridge.evaluation.runner import evaluate_all, render_report

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ClinicalBridge evaluation.")
    parser.add_argument("--no-save", action="store_true", help="do not write the JSON report")
    args = parser.parse_args()

    if not settings.is_configured:
        sys.exit("ERROR: OPENROUTER_API_KEY is not set. Add it to .env and retry.")

    print("Running evaluation across all scenarios (this makes live LLM calls)...\n")
    report = evaluate_all()
    print(render_report(report))

    if not args.no_save:
        out = settings.project_root / "eval" / "results" / "evaluation.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\n[saved] {out}")


if __name__ == "__main__":
    main()
