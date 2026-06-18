"""Anamnesis Agent.

Input:  patient_id + the Triage Agent's ``anamnesis_query`` + the clinical question.
Output: a structured ``AnamnesisSummary`` interpreting the patient's self-reported history —
        translating colloquial language into clinical terms (while preserving the patient's own
        words), assessing medication adherence, and handling sensitive disclosures with care.

Modules exercised: M3 (prompt design, structured output), M4 (interpreting conversational input),
M7 (an agent over a data source).
"""

from __future__ import annotations

from pathlib import Path

from clinicalbridge.agents.base import Agent, clean_source_ref
from clinicalbridge.dataio import load_anamnesis
from clinicalbridge.llm import generate_structured
from clinicalbridge.schemas import AnamnesisSummary, RetrievalQuery, TriageDecision


def format_anamnesis(record: dict) -> str:
    """Render an anamnesis record into labeled, source-tagged sections for the LLM."""
    pid = record["patient_id"]

    def tag(section: str) -> str:
        return f"[Anamnesis:{pid}/{section}]"

    lines: list[str] = [f"PATIENT: {pid}"]

    if record.get("chief_complaint"):
        lines.append(f"{tag('chief_complaint')} Chief complaint: {record['chief_complaint']}")
    if record.get("history_of_present_illness"):
        lines.append(f"{tag('hpi')} History of present illness: {record['history_of_present_illness']}")

    ros = record.get("review_of_systems") or {}
    if ros:
        body = "; ".join(f"{k}: {v}" for k, v in ros.items())
        lines.append(f"{tag('ros')} Review of systems: {body}")

    social = record.get("social_history") or {}
    if social:
        body = "; ".join(f"{k}: {v}" for k, v in social.items())
        lines.append(f"{tag('social')} Social history: {body}")

    family = record.get("family_history") or []
    if family:
        lines.append(f"{tag('family')} Family history: {'; '.join(family)}")

    adherence = record.get("medication_adherence") or []
    if adherence:
        items = "\n".join(
            f"   - {a.get('medication', '?')}: {a.get('reported_status', '?')} — {a.get('detail', '')}"
            for a in adherence
        )
        lines.append(f"{tag('adherence')} Medication adherence (patient-reported):\n{items}")

    diary = record.get("symptom_diary") or []
    if diary:
        items = "\n".join(f"   - {d.get('date', '?')}: {d.get('entry', '')}" for d in diary)
        lines.append(f"{tag('diary')} Symptom diary:\n{items}")

    concerns = record.get("patient_concerns") or []
    if concerns:
        lines.append(f"{tag('concerns')} Patient concerns: {'; '.join(concerns)}")

    sensitive = record.get("sensitive_notes") or []
    if sensitive:
        lines.append(f"{tag('sensitive')} Sensitive notes: {'; '.join(sensitive)}")

    return "\n".join(lines)


class AnamnesisAgent(Agent):
    role = "anamnesis"
    prompt_id = "anamnesis/system"

    def __init__(self, *, anamnesis_dir: Path | None = None, model: str | None = None,
                 prompt_version: int | None = None):
        super().__init__(model=model, prompt_version=prompt_version)
        self.anamnesis_dir = anamnesis_dir

    def run(self, patient_id: str, anamnesis_query: RetrievalQuery,
            clinical_question: str = "") -> AnamnesisSummary:
        record = load_anamnesis(patient_id, anamnesis_dir=self.anamnesis_dir)
        if record is None:
            return AnamnesisSummary(
                patient_id=patient_id,
                missing_data_flags=["No anamnesis record was found for this patient."],
            )

        user = (
            f"CLINICAL QUESTION: {clinical_question or '(none provided)'}\n"
            f"FOCUS TERMS: {', '.join(anamnesis_query.focus_terms)}\n\n"
            "PATIENT ANAMNESIS RECORD (use ONLY this; copy each item's source_ref):\n"
            f"{format_anamnesis(record)}\n\n"
            "Produce the structured anamnesis summary now."
        )
        summary = generate_structured(
            AnamnesisSummary, system=self.system_prompt, user=user, role=self.role, model=self.model
        )
        summary.patient_id = patient_id
        # Normalize citations: models sometimes copy the section tag with its surrounding brackets.
        for sym in summary.reported_symptoms:
            sym.source_ref = clean_source_ref(sym.source_ref)
        if not summary.source_documents:
            summary.source_documents = [f"anamnesis/{patient_id}"]
        return summary

    def run_from_triage(self, triage: TriageDecision) -> AnamnesisSummary:
        return self.run(triage.patient_id, triage.anamnesis_query, triage.clinical_question)
