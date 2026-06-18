"""Tool registry for ClinicalBridge agents (Module 7).

Tools are the bounded capabilities agents and the orchestrator may use. Two kinds:

1. **Data tools** wrap existing capabilities under named, documented entry points
   (``search_ehr`` over the RAG store, ``load_patient_record`` over the dataset).
2. **Deterministic analysis tools** give the system reliable numeric reasoning that LLMs are weak
   at: ``compute_trend`` / ``summarize_vital_series`` for RPM time-series, and
   ``classify_alert_severity`` — a rule-based severity *floor* the orchestrator uses to cross-check
   (and never under-call) the LLM triage. This is defense-in-depth: the model proposes, deterministic
   rules guard.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Callable

from clinicalbridge import dataio
from clinicalbridge.schemas import RPMAlert, UrgencyLevel, VitalType


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    func: Callable[..., Any]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)


TOOLS: dict[str, Tool] = {}


def register(name: str, description: str) -> Callable[[Callable], Callable]:
    def decorator(fn: Callable) -> Callable:
        TOOLS[name] = Tool(name=name, description=description, func=fn)
        return fn
    return decorator


def get_tool(name: str) -> Tool:
    if name not in TOOLS:
        raise KeyError(f"Unknown tool {name!r}. Available: {sorted(TOOLS)}")
    return TOOLS[name]


def list_tools() -> list[Tool]:
    return list(TOOLS.values())


# ---------------------------------------------------------------------------
# Deterministic analysis tools
# ---------------------------------------------------------------------------


@register("compute_trend", "Compute direction and magnitude of change across a numeric series.")
def compute_trend(values: list[float]) -> dict:
    if not values:
        return {"direction": "unknown", "count": 0, "first": None, "last": None,
                "change": 0.0, "slope": 0.0, "min": None, "max": None, "mean": None, "stdev": 0.0}
    first, last = values[0], values[-1]
    change = round(last - first, 3)
    n = len(values)
    slope = round(change / (n - 1), 4) if n > 1 else 0.0
    stdev = round(statistics.pstdev(values), 3) if n > 1 else 0.0
    tolerance = max(0.5 * stdev, 1e-9)  # ignore noise-level wiggle
    if change > tolerance:
        direction = "rising"
    elif change < -tolerance:
        direction = "falling"
    else:
        direction = "stable"
    return {"direction": direction, "count": n, "first": first, "last": last,
            "change": change, "slope": slope, "min": min(values), "max": max(values),
            "mean": round(statistics.mean(values), 3), "stdev": stdev}


@register("summarize_vital_series", "Summarize one vital's RPM time-series (stats + trend).")
def summarize_vital_series(rpm_record: dict, vital_type: str) -> dict:
    values = [r["value"] for r in rpm_record.get("readings", []) if r["vital_type"] == vital_type]
    return {"vital_type": vital_type, **compute_trend(values)}


_SEVERITY_RANK = {"informational": 0, "routine": 1, "urgent": 2, "critical": 3}
_SEVERITY_TO_URGENCY = {
    "informational": UrgencyLevel.INFORMATIONAL,
    "routine": UrgencyLevel.ROUTINE,
    "urgent": UrgencyLevel.URGENT,
    "critical": UrgencyLevel.CRITICAL,
}


def severity_to_urgency(severity: str) -> UrgencyLevel:
    return _SEVERITY_TO_URGENCY[severity]


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK[severity]


_URGENCY_RANK = {
    UrgencyLevel.INFORMATIONAL: 0, UrgencyLevel.ROUTINE: 1,
    UrgencyLevel.URGENT: 2, UrgencyLevel.CRITICAL: 3,
}


def urgency_rank(level: UrgencyLevel) -> int:
    return _URGENCY_RANK[level]


def max_urgency(*levels: UrgencyLevel) -> UrgencyLevel:
    """Return the most severe urgency (used to enforce the deterministic safety floor)."""
    return max(levels, key=urgency_rank)


@register("classify_alert_severity",
          "Deterministic rule-based severity floor for an RPM alert (a guardrail cross-check).")
def classify_alert_severity(alert: RPMAlert) -> dict:
    """Conservative, rule-based severity from the single reading. Used to ensure the LLM triage is
    never *less* urgent than basic vital-sign safety rules would require."""
    vt = alert.reading.vital_type
    v = alert.reading.value
    t = alert.thresholds

    if vt == VitalType.SPO2:
        sev = ("critical" if v < 85 else "urgent" if v < 90 else "routine" if v < 92 else "informational")
        reason = f"SpO2 {v:g}% (rule thresholds: <85 critical, <90 urgent, <92 routine)."
    elif vt == VitalType.BLOOD_PRESSURE:
        sev = ("critical" if v >= 200 or v <= 80 else "urgent" if v >= 170 else
               "routine" if (t and t.high and v > t.high) else "informational")
        reason = f"Systolic {v:g} mmHg (>=200 critical, >=170 urgent, > threshold routine)."
    elif vt == VitalType.BLOOD_GLUCOSE:
        sev = ("critical" if v > 400 or v < 50 else "urgent" if v > 300 else
               "routine" if (t and t.high and v > t.high) else "informational")
        reason = f"Glucose {v:g} mg/dL (>400/<50 critical, >300 urgent, > threshold routine)."
    elif vt == VitalType.HEART_RATE:
        sev = ("critical" if v > 150 or v < 40 else "urgent" if v > 120 else
               "routine" if (t and t.high and v > t.high) else "informational")
        reason = f"Heart rate {v:g} bpm (>150/<40 critical, >120 urgent, > threshold routine)."
    else:
        crossed = bool(t and ((t.high is not None and v > t.high) or (t.low is not None and v < t.low)))
        sev = "routine" if crossed else "informational"
        reason = f"{vt.value} {v:g} {alert.reading.unit} ({'outside' if crossed else 'within'} thresholds)."

    return {"severity": sev, "urgency": severity_to_urgency(sev).value, "rationale": reason}


# ---------------------------------------------------------------------------
# Data tools (wrap existing capabilities)
# ---------------------------------------------------------------------------


@register("load_patient_record", "Load a patient's full EHR, RPM, or anamnesis record by source.")
def load_patient_record(patient_id: str, source: str) -> dict | None:
    loaders = {"ehr": dataio.load_ehr, "rpm": dataio.load_rpm, "anamnesis": dataio.load_anamnesis}
    if source not in loaders:
        raise ValueError(f"source must be one of {sorted(loaders)}, got {source!r}")
    return loaders[source](patient_id)


@register("search_ehr", "Semantic search over a patient's EHR vector store (patient-scoped).")
def search_ehr(query: str, patient_id: str, k: int = 6) -> list[dict]:
    from clinicalbridge.rag.retriever import EHRRetriever

    docs = EHRRetriever(k=k).search(query, patient_id=patient_id)
    return [{"source_ref": d.metadata.get("source_ref"), "section": d.metadata.get("section"),
             "text": d.page_content} for d in docs]
