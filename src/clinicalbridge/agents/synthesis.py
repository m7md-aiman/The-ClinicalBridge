"""Synthesis Agent — the centerpiece.

Input:  the original ``RPMAlert`` + ``TriageDecision`` + ``EHRContext`` + ``AnamnesisSummary``
        (optionally a prior-interaction memory digest and a computed RPM trend note).
Output: a 6-section ``ClinicalContextBrief`` in which every analytical claim cites an allowed
        upstream source.

Modules exercised: M4 (reasoning chain), M6 (multi-source structured synthesis), M8 (citation
discipline / anti-hallucination at the system's final step).
"""

from __future__ import annotations

from datetime import datetime

from clinicalbridge.agents.base import Agent, clean_source_ref
from clinicalbridge.llm import generate_structured
from clinicalbridge.schemas import (
    AnamnesisSummary,
    ClinicalContextBrief,
    EHRContext,
    RPMAlert,
    TriageDecision,
)


def collect_allowed_sources(
    ehr: EHRContext, anamnesis: AnamnesisSummary, *, include_rpm_trend: bool = False
) -> list[str]:
    """The exact set of source ids the synthesis is permitted to cite."""
    refs: set[str] = {"RPM alert"}
    if include_rpm_trend:
        refs.add("RPM trend")
    for p in ehr.problem_list:
        refs.add(p.source_ref)
    for m in ehr.medications:
        refs.add(m.source_ref)
    for l in ehr.lab_results:
        refs.add(l.source_ref)
    for v in ehr.visit_notes:
        refs.add(v.source_ref)
    refs.update(ehr.source_documents)
    for s in anamnesis.reported_symptoms:
        refs.add(s.source_ref)
    refs.update(anamnesis.source_documents)
    return sorted(r for r in (clean_source_ref(x) for x in refs) if r)


def _format_ehr(ehr: EHRContext) -> str:
    lines = [f"EHR CONTEXT (retrieval_confidence={ehr.retrieval_confidence:g}):"]
    for p in ehr.problem_list:
        lines.append(f"  - problem: {p.condition} (ICD-10 {p.icd10_code or 'n/a'}, "
                     f"{p.status or 'status?'}) [{p.source_ref}]")
    for m in ehr.medications:
        lines.append(f"  - medication: {m.name} {m.dose or ''} {m.frequency or ''} "
                     f"({m.status or 'status?'}) [{m.source_ref}]")
    for l in ehr.lab_results:
        trend = f", trend {l.trend.value}" if l.trend else ""
        flag = f", flag {l.flag}" if l.flag else ""
        lines.append(f"  - lab: {l.test_name} = {l.value} {l.unit or ''} "
                     f"({l.date or 'undated'}{trend}{flag}) [{l.source_ref}]")
    for v in ehr.visit_notes:
        lines.append(f"  - note ({v.date or 'undated'}): {v.excerpt} [{v.source_ref}]")
    if ehr.missing_data_flags:
        lines.append(f"  - MISSING (EHR): {'; '.join(ehr.missing_data_flags)}")
    return "\n".join(lines)


def _format_anamnesis(an: AnamnesisSummary) -> str:
    lines = ["ANAMNESIS SUMMARY (patient self-report):"]
    for s in an.reported_symptoms:
        words = f' patient said: "{s.patient_words}"' if s.patient_words else ""
        interp = f" -> {s.clinical_interpretation}" if s.clinical_interpretation else ""
        lines.append(f"  - symptom: {s.symptom}{interp}.{words} [{s.source_ref}]")
    lines.append(f"  - medication adherence: {an.medication_adherence.value}"
                 + (f" ({an.adherence_detail})" if an.adherence_detail else ""))
    if an.lifestyle_factors:
        lines.append(f"  - lifestyle: {'; '.join(an.lifestyle_factors)}")
    if an.family_history:
        lines.append(f"  - family history: {'; '.join(an.family_history)}")
    if an.patient_concerns:
        lines.append(f"  - patient concerns: {'; '.join(an.patient_concerns)}")
    if an.sensitive_flags:
        lines.append(f"  - SENSITIVE (handle with care): {'; '.join(an.sensitive_flags)}")
    if an.missing_data_flags:
        lines.append(f"  - MISSING (anamnesis): {'; '.join(an.missing_data_flags)}")
    return "\n".join(lines)


def invalid_citations(brief: ClinicalContextBrief, allowed: list[str]) -> list[str]:
    """Return any cited source not in the allowed set (a hallucination-detection helper)."""
    allowed_set = set(allowed)
    cited: set[str] = set()
    for st in brief.contextual_analysis + brief.risk_assessment:
        cited.update(st.sources)
    for a in brief.recommended_actions:
        cited.update(a.supporting_evidence)
    return sorted(c for c in cited if c and c not in allowed_set)


class SynthesisAgent(Agent):
    role = "synthesis"
    prompt_id = "synthesis/system"

    def run(
        self,
        alert: RPMAlert,
        triage: TriageDecision,
        ehr: EHRContext,
        anamnesis: AnamnesisSummary,
        *,
        prior_context: str = "",
        rpm_trend_note: str = "",
    ) -> ClinicalContextBrief:
        allowed = collect_allowed_sources(ehr, anamnesis, include_rpm_trend=bool(rpm_trend_note))

        parts = [
            f"ORIGINAL RPM ALERT: {alert.reading.vital_type.value} = {alert.reading.display()} "
            f"(category {alert.device_alert_category}; baseline "
            f"{alert.baseline_value if alert.baseline_value is not None else 'unknown'}; "
            f"notes: {alert.notes or 'none'}) [cite as 'RPM alert']",
            f"\nTRIAGE: urgency={triage.urgency.value}; clinical_question={triage.clinical_question}",
        ]
        if rpm_trend_note:
            parts.append(f"\nRPM TREND (computed): {rpm_trend_note} [cite as 'RPM trend']")
        if prior_context:
            parts.append(f"\nPRIOR INTERACTIONS (memory):\n{prior_context}")
        parts.append("\n" + _format_ehr(ehr))
        parts.append("\n" + _format_anamnesis(anamnesis))
        parts.append("\nALLOWED SOURCES (cite ONLY these, copied exactly):\n  " + "\n  ".join(allowed))
        parts.append("\nProduce the Clinical Context Brief now. Every claim must cite an ALLOWED SOURCE.")
        user = "\n".join(parts)

        brief = generate_structured(
            ClinicalContextBrief, system=self.system_prompt, user=user,
            role=self.role, model=self.model,
        )

        # Guardrails / normalization applied in code.
        brief.patient_id = alert.patient_id
        brief.generated_at = datetime.now()   # system metadata, not the model's to set
        if not brief.urgency:
            brief.urgency = triage.urgency
        for st in brief.contextual_analysis + brief.risk_assessment:
            st.sources = [clean_source_ref(s) for s in st.sources]
        for a in brief.recommended_actions:
            a.supporting_evidence = [clean_source_ref(s) for s in a.supporting_evidence]
        brief.cited_sources = [clean_source_ref(s) for s in brief.cited_sources]
        if not brief.cited_sources:
            used = {s for st in brief.contextual_analysis + brief.risk_assessment for s in st.sources}
            brief.cited_sources = sorted(used)
        return brief
