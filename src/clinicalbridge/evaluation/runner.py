"""Run the full pipeline across scenarios and produce an evaluation report (Module 5)."""

from __future__ import annotations

import time
from statistics import mean

from clinicalbridge.agents.synthesis import collect_allowed_sources
from clinicalbridge.evaluation.metrics import score_brief
from clinicalbridge.orchestrator import Orchestrator
from clinicalbridge.scenarios import Scenario, build_scenarios


def evaluate_scenario(orch: Orchestrator, scenario: Scenario) -> dict:
    t0 = time.perf_counter()
    result = orch.process_alert(scenario.alert)
    latency = time.perf_counter() - t0

    allowed = collect_allowed_sources(
        result.ehr_context, result.anamnesis_summary, include_rpm_trend=True
    )
    score = score_brief(
        result.brief, result.final_urgency, scenario.rubric,
        allowed_sources=allowed, latency_seconds=latency, errors=len(result.errors),
    )
    score["scenario_id"] = scenario.id
    score["title"] = scenario.title
    score["patient_id"] = scenario.patient_id
    score["expected_urgency"] = scenario.expected_urgency.value
    return score


def aggregate(scores: list[dict]) -> dict:
    n = len(scores) or 1
    return {
        "scenarios": len(scores),
        "pass_rate": round(sum(s["passed"] for s in scores) / n, 3),
        "urgency_accuracy": round(sum(s["urgency_ok"] for s in scores) / n, 3),
        "mean_must_include_coverage": round(mean(s["must_include_coverage"] for s in scores), 3),
        "mean_citation_coverage": round(mean(s["citation_coverage"] for s in scores), 3),
        "total_hallucinated_citations": sum(s["hallucination_count"] for s in scores),
        "total_must_avoid_violations": sum(len(s["must_avoid_violations"]) for s in scores),
        "mean_latency_seconds": round(mean(s["latency_seconds"] for s in scores), 2),
        "total_errors": sum(s["errors"] for s in scores),
    }


def evaluate_all(orch: Orchestrator | None = None, scenarios: list[Scenario] | None = None) -> dict:
    orch = orch or Orchestrator()
    scenarios = scenarios or build_scenarios()
    scores = [evaluate_scenario(orch, s) for s in scenarios]
    return {"scenarios": scores, "aggregate": aggregate(scores)}


def render_report(report: dict) -> str:
    lines = ["=" * 78, "ClinicalBridge — Evaluation Report", "=" * 78, ""]
    header = f"{'scenario':<22}{'final':<13}{'expected':<13}{'urg':<5}{'incl':<6}{'cite':<6}{'hall':<5}{'pass'}"
    lines.append(header)
    lines.append("-" * 78)
    for s in report["scenarios"]:
        lines.append(
            f"{s['scenario_id']:<22}{s['final_urgency']:<13}{s['expected_urgency']:<13}"
            f"{('OK' if s['urgency_ok'] else 'X'):<5}"
            f"{s['must_include_coverage']:<6}{s['citation_coverage']:<6}"
            f"{s['hallucination_count']:<5}{'PASS' if s['passed'] else 'FAIL'}"
        )
    agg = report["aggregate"]
    lines += ["-" * 78, "", "AGGREGATE", "-" * 40]
    for k, v in agg.items():
        lines.append(f"  {k:<32} {v}")
    lines.append("=" * 78)

    # Surface notable per-scenario issues.
    notes = []
    for s in report["scenarios"]:
        problems = []
        if not s["urgency_ok"]:
            problems.append(f"urgency {s['final_urgency']} not in {s['acceptable_urgencies']}")
        if s["must_include_missing"]:
            problems.append(f"missing terms {s['must_include_missing']}")
        if s["hallucinated_citations"]:
            problems.append(f"hallucinated {s['hallucinated_citations']}")
        if s["must_avoid_violations"]:
            problems.append(f"avoid-violations {s['must_avoid_violations']}")
        if problems:
            notes.append(f"  - {s['scenario_id']}: " + "; ".join(problems))
    if notes:
        lines += ["", "NOTES (per-scenario gaps):", *notes, "=" * 78]
    return "\n".join(lines)
