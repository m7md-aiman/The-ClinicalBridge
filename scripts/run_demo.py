"""End-to-end ClinicalBridge demo.

Feed a clinical scenario through the full multi-agent pipeline and print the Clinical Context Brief,
the pipeline trace, escalation status, and (optionally) the gold-standard brief for comparison.

Usage:
    python scripts/run_demo.py --list
    python scripts/run_demo.py missed_medication
    python scripts/run_demo.py missed_medication --compare
    python scripts/run_demo.py --all --save
    python scripts/run_demo.py conflicting_data --model anthropic/claude-3.5-sonnet

Prerequisites: dataset generated (scripts/generate_dataset.py) and vector store built
(scripts/build_vectorstore.py). Requires OPENROUTER_API_KEY in .env.
"""

from __future__ import annotations

import argparse
import json
import sys

from clinicalbridge.config import settings
from clinicalbridge.orchestrator import OrchestrationResult, Orchestrator
from clinicalbridge.scenarios import Scenario, build_scenarios, get_scenario, scenario_ids

# Print UTF-8 cleanly on the Windows console (the brief uses ·/— separators).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RULE = "=" * 74
THIN = "-" * 74


def _build_orchestrator(model: str | None) -> Orchestrator:
    if not model:
        return Orchestrator()
    from clinicalbridge.agents.anamnesis import AnamnesisAgent
    from clinicalbridge.agents.ehr import EHRRetrievalAgent
    from clinicalbridge.agents.synthesis import SynthesisAgent
    from clinicalbridge.agents.triage import TriageAgent
    return Orchestrator(
        triage=TriageAgent(model=model), ehr=EHRRetrievalAgent(model=model),
        anamnesis=AnamnesisAgent(model=model), synthesis=SynthesisAgent(model=model),
    )


def format_result(result: OrchestrationResult, scenario: Scenario | None = None) -> str:
    lines = [RULE]
    if scenario:
        lines.append(f"SCENARIO: {scenario.id}  —  {scenario.title}")
        lines.append(f"(gold-standard urgency for reference: {scenario.expected_urgency.value})")
    lines.append(f"ALERT: {result.brief.patient_id} | "
                 f"deterministic severity floor = {result.deterministic_severity['severity']}")
    lines.append(f"FINAL URGENCY: {result.final_urgency.value}   |   ESCALATED: {result.escalated}")
    lines.append(THIN)
    lines.append("PIPELINE TRACE:")
    for e in result.session.events:
        lines.append(f"  · {e['step']:<16} {e['summary']}")
    if result.errors:
        lines.append(THIN)
        lines.append("ERRORS (degraded steps):")
        for err in result.errors:
            lines.append(f"  ! {err}")
    lines.append(THIN)
    lines.append(result.brief.render())
    lines.append(RULE)
    return "\n".join(lines)


def run_one(orch: Orchestrator, scenario: Scenario, *, compare: bool, save: bool) -> OrchestrationResult:
    result = orch.process_alert(scenario.alert)
    print(format_result(result, scenario))
    if compare:
        print("\n>>> GOLD-STANDARD BRIEF (hand-authored reference) >>>\n")
        print(scenario.gold_brief.render())
        print(RULE)
    if save:
        out = settings.project_root / "eval" / "results" / f"{scenario.id}_demo.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
        print(f"[saved] {out}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ClinicalBridge end-to-end demo.")
    parser.add_argument("scenario", nargs="?", help="scenario id (see --list)")
    parser.add_argument("--list", action="store_true", help="list available scenarios and exit")
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--compare", action="store_true", help="also print the gold-standard brief")
    parser.add_argument("--save", action="store_true", help="save full result JSON to eval/results/")
    parser.add_argument("--model", help="override the OpenRouter model for all agents")
    args = parser.parse_args()

    if args.list or (not args.scenario and not args.all):
        print("Available scenarios:")
        for s in build_scenarios():
            print(f"  {s.id:<22} {s.title:<26} [gold: {s.expected_urgency.value}]")
        if not args.list:
            print("\nRun one with:  python scripts/run_demo.py <scenario_id>")
        return

    if not settings.is_configured:
        sys.exit("ERROR: OPENROUTER_API_KEY is not set. Add it to .env and retry.")

    orch = _build_orchestrator(args.model)
    targets = build_scenarios() if args.all else [get_scenario(args.scenario)]
    for scenario in targets:
        run_one(orch, scenario, compare=args.compare, save=args.save)
        print()


if __name__ == "__main__":
    main()
