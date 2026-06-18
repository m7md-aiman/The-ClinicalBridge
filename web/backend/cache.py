"""Cache loading + scoring helpers for the ClinicalBridge web backend.

Read endpoints serve **bundled, precomputed** pipeline runs so the site works with NO API key.
The cache is produced by ``scripts/build_web_cache.py`` and committed under ``web/backend/data/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from clinicalbridge.agents.synthesis import collect_allowed_sources, invalid_citations
from clinicalbridge.config import settings
from clinicalbridge.evaluation.metrics import score_brief
from clinicalbridge.scenarios import Scenario, build_scenarios, get_scenario
from clinicalbridge.schemas import ClinicalContextBrief, UrgencyLevel

DATA_DIR = Path(__file__).parent / "data"
RUNS_DIR = DATA_DIR / "runs"


def live_available() -> bool:
    """True when an OpenRouter key is configured, so the UI can offer a live run."""
    return settings.is_configured


def scenario_summary(s: Scenario) -> dict:
    """Compact scenario card payload for the demo picker."""
    return {
        "id": s.id,
        "title": s.title,
        "lesson": s.description,
        "expected_urgency": s.expected_urgency.value,
        "patient_id": s.patient_id,
        "alert": s.alert.model_dump(mode="json"),
        "alert_display": s.alert.reading.display(),
        "alert_category": s.alert.device_alert_category,
    }


def scenario_detail(scenario_id: str) -> dict:
    s = get_scenario(scenario_id)
    return {
        **scenario_summary(s),
        "rubric": s.rubric,
        "gold_brief": s.gold_brief.model_dump(mode="json"),
        "gold_brief_markdown": s.gold_brief.render(),
    }


def list_scenarios() -> list[dict]:
    return [scenario_summary(s) for s in build_scenarios()]


def cached_run(scenario_id: str) -> dict | None:
    """Load a precomputed OrchestrationResult-as-dict for a scenario, or None if absent."""
    path = RUNS_DIR / f"{scenario_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def score_result_dict(result: dict, scenario: Scenario) -> dict:
    """Score a result dict (cached or live) against the scenario rubric for the UI."""
    brief = ClinicalContextBrief.model_validate(result["brief"])
    final_urgency = UrgencyLevel(result["final_urgency"])
    allowed = None
    if result.get("ehr_context") and result.get("anamnesis_summary"):
        from clinicalbridge.schemas import AnamnesisSummary, EHRContext
        ehr = EHRContext.model_validate(result["ehr_context"])
        anam = AnamnesisSummary.model_validate(result["anamnesis_summary"])
        allowed = collect_allowed_sources(ehr, anam, include_rpm_trend=True)
    score = score_brief(brief, final_urgency, scenario.rubric, allowed_sources=allowed,
                        errors=len(result.get("errors", [])))
    if allowed is not None:
        score["hallucinated_citations"] = invalid_citations(brief, allowed)
    return score


def result_payload(scenario_id: str) -> dict | None:
    """Cached run + its score + the gold brief, ready for the demo page."""
    run = cached_run(scenario_id)
    if run is None:
        return None
    s = get_scenario(scenario_id)
    return {
        "scenario": scenario_summary(s),
        "result": run,
        "score": score_result_dict(run, s),
        "gold_brief": s.gold_brief.model_dump(mode="json"),
        "gold_brief_markdown": s.gold_brief.render(),
        "cached": True,
    }


def evaluation_report() -> dict:
    """The evaluation snapshot + the authored v1->v2->guardrail progression."""
    out: dict = {"report": None, "progression": None}
    ev = DATA_DIR / "evaluation.json"
    if ev.exists():
        out["report"] = json.loads(ev.read_text(encoding="utf-8"))
    prog = DATA_DIR / "progression.json"
    if prog.exists():
        out["progression"] = json.loads(prog.read_text(encoding="utf-8"))
    return out
