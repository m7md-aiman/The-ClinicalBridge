"""Data contracts for ClinicalBridge (Pydantic v2).

These models are the typed interfaces that flow between agents:

    RPMAlert ──▶ TriageDecision ──▶ {EHRContext, AnamnesisSummary} ──▶ ClinicalContextBrief

Every ``Field(description=...)`` here does double duty: it documents the contract *and* becomes
part of the JSON schema handed to the LLM by ``with_structured_output`` (Phase 3), so these
descriptions are themselves a form of prompt engineering.

Design principles encoded here:
- **Traceability / anti-hallucination** — context-bearing items carry a ``source_ref`` (or a list
  of sources) so every downstream claim can cite where it came from.
- **Explicit uncertainty** — models carry ``missing_data_flags`` / ``uncertainties`` rather than
  letting the LLM silently fill gaps.
- **Clinical safety** — urgency and escalation are first-class, structured fields, not prose.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations (controlled vocabularies)
# ---------------------------------------------------------------------------


class UrgencyLevel(str, Enum):
    """Triage urgency classification for an incoming RPM alert."""

    CRITICAL = "Critical"            # life-threatening; immediate human attention
    URGENT = "Urgent"                # needs same-day clinical review
    ROUTINE = "Routine"             # review within normal workflow
    INFORMATIONAL = "Informational"  # logged for awareness; likely benign


class ConfidenceLevel(str, Enum):
    """Qualitative confidence used for recommendations and overall assessment."""

    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"


class VitalType(str, Enum):
    """Physiological signals captured by RPM devices."""

    BLOOD_PRESSURE = "blood_pressure"   # value=systolic, value_secondary=diastolic
    HEART_RATE = "heart_rate"
    BLOOD_GLUCOSE = "blood_glucose"
    SPO2 = "spo2"
    WEIGHT = "weight"
    TEMPERATURE = "temperature"
    RESPIRATORY_RATE = "respiratory_rate"


class TrendDirection(str, Enum):
    """Direction of a measured series over the relevant window."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    FLUCTUATING = "fluctuating"
    UNKNOWN = "unknown"


class AdherenceStatus(str, Enum):
    """Patient-reported (or inferred) medication adherence status."""

    ADHERENT = "adherent"
    PARTIAL = "partial"
    NON_ADHERENT = "non_adherent"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Input: RPM alert (entry point to the system)
# ---------------------------------------------------------------------------


class VitalReading(BaseModel):
    """A single physiological reading. Paired vitals (e.g. BP) use ``value_secondary``."""

    vital_type: VitalType = Field(description="Which physiological signal was measured.")
    value: float = Field(description="Primary measured value (e.g. systolic for blood pressure).")
    value_secondary: float | None = Field(
        default=None,
        description="Secondary value for paired vitals (e.g. diastolic for blood pressure).",
    )
    unit: str = Field(description="Unit of measure, e.g. 'mmHg', 'bpm', 'mg/dL', '%', 'kg'.")

    def display(self) -> str:
        if self.value_secondary is not None:
            return f"{self.value:g}/{self.value_secondary:g} {self.unit}"
        return f"{self.value:g} {self.unit}"


class RPMThreshold(BaseModel):
    """Patient-specific alerting thresholds for a vital."""

    vital_type: VitalType
    low: float | None = Field(default=None, description="Lower bound; below this alerts.")
    high: float | None = Field(default=None, description="Upper bound; above this alerts.")
    unit: str


class RPMAlert(BaseModel):
    """A structured Remote Patient Monitoring alert — the system's input."""

    alert_id: str = Field(description="Unique identifier for this alert event.")
    patient_id: str = Field(description="Identifier of the patient the alert concerns.")
    timestamp: datetime = Field(description="When the triggering reading was taken.")
    device_type: str = Field(description="Device that produced the reading, e.g. 'BP cuff'.")
    reading: VitalReading = Field(description="The triggering measurement.")
    device_alert_category: str = Field(
        description="Coarse device-level category, e.g. 'BP_HIGH', 'GLUCOSE_HIGH', 'WEIGHT_GAIN'."
    )
    baseline_value: float | None = Field(
        default=None, description="Patient's recent baseline for this vital, if known."
    )
    thresholds: RPMThreshold | None = Field(
        default=None, description="The thresholds that classified this reading as an alert."
    )
    notes: str | None = Field(
        default=None, description="Optional device/context notes (e.g. 'sustained over 3 readings')."
    )


# ---------------------------------------------------------------------------
# Triage Agent output
# ---------------------------------------------------------------------------


class RetrievalQuery(BaseModel):
    """Structured retrieval instruction the Triage Agent hands to a downstream agent."""

    focus_terms: list[str] = Field(
        description="Key clinical terms to retrieve on, e.g. ['hypertension', 'ACE inhibitor']."
    )
    rationale: str = Field(
        description="Why these terms matter for interpreting the alert (one sentence)."
    )


class TriageDecision(BaseModel):
    """The Triage Agent's classification and retrieval plan for an alert."""

    patient_id: str
    urgency: UrgencyLevel = Field(description="Classified clinical urgency of the alert.")
    clinical_question: str = Field(
        description="One-sentence natural-language statement of the clinical concern to resolve."
    )
    reasoning: str = Field(
        description="Chain-of-thought justification for the urgency classification."
    )
    requires_immediate_escalation: bool = Field(
        default=False,
        description="True only for Critical alerts that warrant human attention before synthesis.",
    )
    ehr_query: RetrievalQuery = Field(description="Retrieval plan for the EHR Retrieval Agent.")
    anamnesis_query: RetrievalQuery = Field(description="Retrieval plan for the Anamnesis Agent.")


# ---------------------------------------------------------------------------
# EHR Retrieval Agent output
# ---------------------------------------------------------------------------


class ProblemListEntry(BaseModel):
    condition: str = Field(description="Diagnosis / problem name.")
    icd10_code: str | None = Field(default=None, description="ICD-10 code if present in the record.")
    status: str | None = Field(default=None, description="e.g. 'active', 'resolved'.")
    onset_date: str | None = Field(default=None, description="Onset/first-noted date if recorded.")
    source_ref: str = Field(description="Source document id/section this came from.")


class MedicationEntry(BaseModel):
    name: str
    dose: str | None = None
    frequency: str | None = None
    status: str | None = Field(default=None, description="e.g. 'active', 'discontinued'.")
    source_ref: str


class LabResult(BaseModel):
    test_name: str
    value: str = Field(description="Result value as recorded (string to preserve qualifiers).")
    unit: str | None = None
    reference_range: str | None = None
    date: str | None = None
    trend: TrendDirection | None = Field(
        default=None, description="Direction across recent results if multiple are available."
    )
    flag: str | None = Field(default=None, description="e.g. 'high', 'low', 'critical' if abnormal.")
    source_ref: str


class VisitNoteExcerpt(BaseModel):
    date: str | None = None
    excerpt: str = Field(description="Relevant verbatim excerpt from a clinician note.")
    source_ref: str


class EHRContext(BaseModel):
    """Structured findings from the patient's longitudinal EHR, with provenance."""

    patient_id: str
    problem_list: list[ProblemListEntry] = Field(default_factory=list)
    medications: list[MedicationEntry] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    visit_notes: list[VisitNoteExcerpt] = Field(default_factory=list)
    retrieval_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="0–1 confidence that retrieval surfaced the relevant EHR content.",
    )
    missing_data_flags: list[str] = Field(
        default_factory=list,
        description="Explicitly note expected-but-absent data instead of inventing it.",
    )
    source_documents: list[str] = Field(
        default_factory=list, description="Identifiers of EHR documents consulted."
    )


# ---------------------------------------------------------------------------
# Anamnesis Agent output
# ---------------------------------------------------------------------------


class ReportedSymptom(BaseModel):
    symptom: str = Field(description="Symptom in clinical terms.")
    onset: str | None = Field(default=None, description="When it started, as reported.")
    progression: str | None = Field(default=None, description="How it has changed over time.")
    patient_words: str | None = Field(
        default=None, description="Original colloquial phrasing, preserved verbatim."
    )
    clinical_interpretation: str | None = Field(
        default=None, description="Translation of the patient's words into clinical meaning."
    )
    source_ref: str


class AnamnesisSummary(BaseModel):
    """Structured interpretation of the patient's self-reported history, with provenance."""

    patient_id: str
    reported_symptoms: list[ReportedSymptom] = Field(default_factory=list)
    medication_adherence: AdherenceStatus = Field(default=AdherenceStatus.UNKNOWN)
    adherence_detail: str | None = Field(
        default=None, description="Specifics of adherence (e.g. 'stopped ACE inhibitor due to cough')."
    )
    lifestyle_factors: list[str] = Field(
        default_factory=list, description="Diet, activity, sleep, stress factors relevant to alert."
    )
    family_history: list[str] = Field(default_factory=list)
    patient_concerns: list[str] = Field(
        default_factory=list, description="Questions or worries the patient expressed."
    )
    sensitive_flags: list[str] = Field(
        default_factory=list,
        description="Mental-health / substance-use disclosures to handle with care and neutrality.",
    )
    missing_data_flags: list[str] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Synthesis Agent output: the Clinical Context Brief (CCB)
# ---------------------------------------------------------------------------


class CitedStatement(BaseModel):
    """An analytical statement bound to its supporting sources (anti-hallucination)."""

    statement: str = Field(description="A single analytical claim.")
    sources: list[str] = Field(
        description="Source references supporting the claim (EHR doc ids, anamnesis refs, or 'RPM alert')."
    )


class RecommendedAction(BaseModel):
    action: str = Field(description="A concrete suggested next step for the clinician.")
    confidence: ConfidenceLevel = Field(description="Confidence in this recommendation.")
    supporting_evidence: list[str] = Field(
        default_factory=list, description="Sources/findings that justify the action."
    )


class ClinicalContextBrief(BaseModel):
    """The final product: a 6-section, cited brief a clinician reads in under 60 seconds."""

    patient_id: str
    generated_at: datetime = Field(default_factory=datetime.now)

    # 1. Alert Summary — what triggered the alert and its classified urgency.
    alert_summary: str
    urgency: UrgencyLevel

    # 2. Patient Snapshot — key demographics, active conditions, current treatment plan.
    patient_snapshot: str

    # 3. Contextual Analysis — how the alert relates to history, trends, and self-report.
    contextual_analysis: list[CitedStatement] = Field(default_factory=list)

    # 4. Risk Assessment — potential clinical implications and differential considerations.
    risk_assessment: list[CitedStatement] = Field(default_factory=list)

    # 5. Recommended Actions — next steps with confidence levels and supporting evidence.
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)

    # 6. Uncertainties & Gaps — missing data, conflicts, areas needing clinician judgment.
    uncertainties_and_gaps: list[str] = Field(default_factory=list)

    overall_confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MODERATE)
    cited_sources: list[str] = Field(
        default_factory=list, description="De-duplicated list of all sources cited in the brief."
    )

    def render(self) -> str:
        """Render the brief as readable markdown for the clinician / demo output."""
        lines: list[str] = []
        lines.append(f"# Clinical Context Brief — Patient {self.patient_id}")
        lines.append(f"_Generated {self.generated_at:%Y-%m-%d %H:%M} · "
                     f"Urgency: **{self.urgency.value}** · "
                     f"Overall confidence: **{self.overall_confidence.value}**_\n")

        lines.append("## 1. Alert Summary")
        lines.append(self.alert_summary + "\n")

        lines.append("## 2. Patient Snapshot")
        lines.append(self.patient_snapshot + "\n")

        lines.append("## 3. Contextual Analysis")
        for s in self.contextual_analysis:
            lines.append(f"- {s.statement}  \n  _sources: {', '.join(s.sources) or 'none'}_")
        lines.append("")

        lines.append("## 4. Risk Assessment")
        for s in self.risk_assessment:
            lines.append(f"- {s.statement}  \n  _sources: {', '.join(s.sources) or 'none'}_")
        lines.append("")

        lines.append("## 5. Recommended Actions")
        for a in self.recommended_actions:
            ev = f" _(evidence: {', '.join(a.supporting_evidence)})_" if a.supporting_evidence else ""
            lines.append(f"- [{a.confidence.value}] {a.action}{ev}")
        lines.append("")

        lines.append("## 6. Uncertainties & Gaps")
        if self.uncertainties_and_gaps:
            for u in self.uncertainties_and_gaps:
                lines.append(f"- {u}")
        else:
            lines.append("- None flagged.")
        lines.append("")

        if self.cited_sources:
            lines.append(f"_Sources consulted: {', '.join(self.cited_sources)}_")
        return "\n".join(lines)


__all__ = [
    "UrgencyLevel", "ConfidenceLevel", "VitalType", "TrendDirection", "AdherenceStatus",
    "VitalReading", "RPMThreshold", "RPMAlert",
    "RetrievalQuery", "TriageDecision",
    "ProblemListEntry", "MedicationEntry", "LabResult", "VisitNoteExcerpt", "EHRContext",
    "ReportedSymptom", "AnamnesisSummary",
    "CitedStatement", "RecommendedAction", "ClinicalContextBrief",
]
