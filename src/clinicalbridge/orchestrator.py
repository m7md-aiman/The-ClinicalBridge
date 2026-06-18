"""The ClinicalBridge Orchestrator (Module 8).

Coordinates the four agents into one system using the linear-then-convergent pattern:

    Triage  ->  parallel( EHR Retrieval , Anamnesis )  ->  Synthesis  ->  Clinical Context Brief

The orchestrator performs NO clinical reasoning itself. Its job is coordination and safety:

- **Routing & parallelism** — runs the two retrieval agents concurrently (they are independent and
  network-bound), then converges on synthesis.
- **Safety guardrails** — a deterministic severity *floor* (`classify_alert_severity`) ensures the
  final urgency is never less severe than basic vital-sign rules require; Critical alerts are
  **escalated for human attention before synthesis even runs**.
- **Resilience** — every agent call is guarded; on failure the pipeline degrades gracefully with a
  fallback rather than crashing, and the error is recorded.
- **Auditability** — every step is logged to a `SessionMemory` trace; optional `PatientMemory` gives
  cross-run continuity.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from clinicalbridge import dataio
from clinicalbridge.agents.anamnesis import AnamnesisAgent
from clinicalbridge.agents.ehr import EHRRetrievalAgent
from clinicalbridge.agents.synthesis import SynthesisAgent
from clinicalbridge.agents.triage import TriageAgent
from clinicalbridge.memory import PatientMemory, SessionMemory
from clinicalbridge.schemas import (
    AnamnesisSummary,
    ClinicalContextBrief,
    ConfidenceLevel,
    EHRContext,
    RetrievalQuery,
    RPMAlert,
    TriageDecision,
    UrgencyLevel,
    VitalType,
)
from clinicalbridge.tools import (
    classify_alert_severity,
    max_urgency,
    severity_to_urgency,
    summarize_vital_series,
    urgency_rank,
)

# Rapid weight gain is a standard heart-failure decompensation red flag ("report >~2 kg gain").
# Encoded as a deterministic guardrail because a safety rule should not depend on the LLM.
WEIGHT_TREND_URGENT_KG = 2.5


@dataclass
class OrchestrationResult:
    """The full outcome of processing one alert, with intermediate outputs for transparency."""

    alert_id: str
    patient_id: str
    final_urgency: UrgencyLevel
    escalated: bool
    brief: ClinicalContextBrief
    triage: TriageDecision | None
    ehr_context: EHRContext | None
    anamnesis_summary: AnamnesisSummary | None
    deterministic_severity: dict
    errors: list[str] = field(default_factory=list)
    session: SessionMemory | None = None

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "patient_id": self.patient_id,
            "final_urgency": self.final_urgency.value,
            "escalated": self.escalated,
            "deterministic_severity": self.deterministic_severity,
            "errors": self.errors,
            "triage": self.triage.model_dump(mode="json") if self.triage else None,
            "ehr_context": self.ehr_context.model_dump(mode="json") if self.ehr_context else None,
            "anamnesis_summary": self.anamnesis_summary.model_dump(mode="json") if self.anamnesis_summary else None,
            "brief": self.brief.model_dump(mode="json"),
            "session": self.session.to_dict() if self.session else None,
        }


def _guard(fn: Callable, fallback: Callable, step: str) -> tuple[object, str | None]:
    """Run ``fn``; on any exception return ``fallback()`` and an error string. Thread-safe (no
    shared state touched here — logging happens in the caller)."""
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 - graceful degradation is the point
        return fallback(), f"{step}: {exc}"


class Orchestrator:
    def __init__(
        self,
        *,
        triage: TriageAgent | None = None,
        ehr: EHRRetrievalAgent | None = None,
        anamnesis: AnamnesisAgent | None = None,
        synthesis: SynthesisAgent | None = None,
        patient_memory: PatientMemory | None = None,
        enable_memory: bool = False,
        rpm_dir: Path | None = None,
    ) -> None:
        self.triage = triage or TriageAgent()
        self.ehr = ehr or EHRRetrievalAgent()
        self.anamnesis = anamnesis or AnamnesisAgent()
        self.synthesis = synthesis or SynthesisAgent()
        self.enable_memory = enable_memory
        self.patient_memory = patient_memory or (PatientMemory() if enable_memory else None)
        self.rpm_dir = rpm_dir

    # ------------------------------------------------------------------ helpers

    def _trend_severity_floor(self, alert: RPMAlert) -> UrgencyLevel | None:
        """Deterministic decompensation guardrail: a sustained rapid weight rise → at least Urgent.

        This catches the 'silent deterioration' pattern that a single in-threshold reading (and, in
        practice, the LLM) misses. Returns None when no trend rule applies.
        """
        try:
            rpm = dataio.load_rpm(alert.patient_id, rpm_dir=self.rpm_dir)
            if not rpm:
                return None
            if alert.reading.vital_type == VitalType.WEIGHT:
                s = summarize_vital_series(rpm, VitalType.WEIGHT.value)
                if s["count"] >= 7 and s["direction"] == "rising" and s["change"] >= WEIGHT_TREND_URGENT_KG:
                    return UrgencyLevel.URGENT
        except Exception:
            return None
        return None

    def _rpm_trend_note(self, alert: RPMAlert) -> str:
        try:
            rpm = dataio.load_rpm(alert.patient_id, rpm_dir=self.rpm_dir)
            if not rpm:
                return ""
            s = summarize_vital_series(rpm, alert.reading.vital_type.value)
            if not s["count"]:
                return ""
            return (f"{alert.reading.vital_type.value}: {s['count']} readings, trend {s['direction']}, "
                    f"from {s['first']} to {s['last']} (mean {s['mean']}, net change {s['change']}).")
        except Exception:
            return ""

    def _fallback_triage(self, alert: RPMAlert, severity: dict) -> TriageDecision:
        vt = alert.reading.vital_type.value
        return TriageDecision(
            patient_id=alert.patient_id,
            urgency=severity_to_urgency(severity["severity"]),
            clinical_question=f"Review the {vt} alert and gather supporting context.",
            reasoning="Fallback triage (LLM unavailable): using deterministic severity rules.",
            requires_immediate_escalation=(severity["severity"] == "critical"),
            ehr_query=RetrievalQuery(focus_terms=[vt, "relevant diagnoses", "medications"],
                                     rationale="fallback retrieval plan"),
            anamnesis_query=RetrievalQuery(focus_terms=["recent symptoms", "medication adherence"],
                                           rationale="fallback retrieval plan"),
        )

    def _fallback_brief(self, alert: RPMAlert, ehr: EHRContext, anam: AnamnesisSummary,
                        urgency: UrgencyLevel) -> ClinicalContextBrief:
        return ClinicalContextBrief(
            patient_id=alert.patient_id,
            alert_summary=(f"{alert.reading.vital_type.value} = {alert.reading.display()} "
                           f"({alert.device_alert_category}). Automated synthesis was unavailable."),
            urgency=urgency,
            patient_snapshot="(Synthesis unavailable — review the raw agent outputs.)",
            uncertainties_and_gaps=(["The synthesis step failed; this brief is incomplete."]
                                    + ehr.missing_data_flags + anam.missing_data_flags),
            overall_confidence=ConfidenceLevel.LOW,
            cited_sources=["RPM alert"],
        )

    # ------------------------------------------------------------------ main

    def process_alert(
        self, alert: RPMAlert, *, on_event: Callable[[str, str, dict], None] | None = None
    ) -> OrchestrationResult:
        session = SessionMemory(alert.alert_id, alert.patient_id)
        # Optional live streaming hook: mirror every session.log to on_event (e.g. SSE for the web UI).
        if on_event is not None:
            _orig_log = session.log

            def _log(step: str, summary: str, data: dict | None = None) -> None:
                _orig_log(step, summary, data)
                on_event(step, summary, data or {})

            session.log = _log  # type: ignore[method-assign]
        errors: list[str] = []
        session.log("alert_received", f"{alert.reading.vital_type.value}={alert.reading.display()} "
                                      f"({alert.device_alert_category})")

        # 1) Deterministic severity floor (safety cross-check) + trend guardrail.
        severity = classify_alert_severity(alert)
        floor = severity_to_urgency(severity["severity"])
        trend_floor = self._trend_severity_floor(alert)
        if trend_floor and urgency_rank(trend_floor) > urgency_rank(floor):
            floor = trend_floor
            session.log("trend_guardrail",
                        f"worsening trend raised severity floor to {trend_floor.value}")
        session.log("severity_floor",
                    f"rule severity={severity['severity']}, effective floor={floor.value}", severity)

        # 2) Triage (LLM) with fallback to deterministic triage.
        triage, err = _guard(lambda: self.triage.run(alert),
                             lambda: self._fallback_triage(alert, severity), "triage")
        triage: TriageDecision
        if err:
            errors.append(err); session.log("triage", f"FAILED -> fallback: {err}")
        else:
            session.log("triage", f"urgency={triage.urgency.value}: {triage.clinical_question}",
                        {"urgency": triage.urgency.value})

        # 3) Escalation guardrail — decide BEFORE synthesis ("don't wait for the full brief").
        effective = max_urgency(triage.urgency, floor)
        escalated = effective == UrgencyLevel.CRITICAL or triage.requires_immediate_escalation
        if escalated:
            session.log("escalation", "CRITICAL alert flagged for immediate human attention "
                                      "(emitted before synthesis).")

        # 4) Parallel retrieval: EHR + Anamnesis.
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_ehr = ex.submit(
                _guard, lambda: self.ehr.run_from_triage(triage),
                lambda: EHRContext(patient_id=alert.patient_id, retrieval_confidence=0.0,
                                   missing_data_flags=["EHR retrieval failed."]),
                "ehr_retrieval")
            f_anam = ex.submit(
                _guard, lambda: self.anamnesis.run_from_triage(triage),
                lambda: AnamnesisSummary(patient_id=alert.patient_id,
                                         missing_data_flags=["Anamnesis retrieval failed."]),
                "anamnesis")
            ehr_ctx, ehr_err = f_ehr.result()
            anam_sum, anam_err = f_anam.result()
        ehr_ctx: EHRContext
        anam_sum: AnamnesisSummary

        if ehr_err:
            errors.append(ehr_err); session.log("ehr_retrieval", f"FAILED -> fallback: {ehr_err}")
        else:
            session.log("ehr_retrieval", f"{len(ehr_ctx.problem_list)} problems, "
                        f"{len(ehr_ctx.medications)} meds, {len(ehr_ctx.lab_results)} labs "
                        f"(confidence {ehr_ctx.retrieval_confidence:g})")
        if anam_err:
            errors.append(anam_err); session.log("anamnesis", f"FAILED -> fallback: {anam_err}")
        else:
            session.log("anamnesis", f"adherence={anam_sum.medication_adherence.value}, "
                        f"{len(anam_sum.reported_symptoms)} symptoms")

        # 5) Synthesis (convergence).
        prior_context = self.patient_memory.digest(alert.patient_id) if self.patient_memory else ""
        rpm_note = self._rpm_trend_note(alert)
        brief, syn_err = _guard(
            lambda: self.synthesis.run(alert, triage, ehr_ctx, anam_sum,
                                       prior_context=prior_context, rpm_trend_note=rpm_note),
            lambda: self._fallback_brief(alert, ehr_ctx, anam_sum, effective), "synthesis")
        brief: ClinicalContextBrief
        if syn_err:
            errors.append(syn_err); session.log("synthesis", f"FAILED -> fallback: {syn_err}")
        else:
            session.log("synthesis", "Clinical Context Brief produced.")

        # 6) Enforce the safety floor on the final brief's urgency.
        brief.urgency = max_urgency(brief.urgency, effective)
        final_urgency = brief.urgency
        if final_urgency == UrgencyLevel.CRITICAL:
            escalated = True
        session.log("complete", f"final_urgency={final_urgency.value}, escalated={escalated}")

        # 7) Optional cross-run memory.
        if self.patient_memory:
            self.patient_memory.record_interaction(
                alert.patient_id, urgency=final_urgency.value, summary=brief.alert_summary,
                flags=brief.uncertainties_and_gaps[:3], alert_id=alert.alert_id)

        return OrchestrationResult(
            alert_id=alert.alert_id, patient_id=alert.patient_id, final_urgency=final_urgency,
            escalated=escalated, brief=brief, triage=triage, ehr_context=ehr_ctx,
            anamnesis_summary=anam_sum, deterministic_severity=severity, errors=errors,
            session=session,
        )
