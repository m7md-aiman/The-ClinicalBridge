"""Phase 11 tests: Synthesis Agent.

Offline tests cover the allowed-source collection, citation validation, and formatting. Live tests
build realistic upstream inputs and assert the brief is well-formed, cited only from allowed
sources (anti-hallucination), confidence-calibrated, and non-accusatory on conflicts.
"""

import pytest

from clinicalbridge.agents.synthesis import (
    SynthesisAgent,
    collect_allowed_sources,
    invalid_citations,
)
from clinicalbridge.config import settings
from clinicalbridge.scenarios import get_scenario
from clinicalbridge.schemas import (
    AdherenceStatus,
    AnamnesisSummary,
    CitedStatement,
    ClinicalContextBrief,
    EHRContext,
    LabResult,
    MedicationEntry,
    ProblemListEntry,
    ReportedSymptom,
    RetrievalQuery,
    TriageDecision,
    UrgencyLevel,
)

LIVE = pytest.mark.skipif(not settings.is_configured, reason="OPENROUTER_API_KEY not configured")


# --- Input builders (realistic upstream outputs) ----------------------------


def _triage(pid, urgency, question):
    return TriageDecision(
        patient_id=pid, urgency=urgency, clinical_question=question, reasoning="...",
        ehr_query=RetrievalQuery(focus_terms=["x"], rationale="x"),
        anamnesis_query=RetrievalQuery(focus_terms=["y"], rationale="y"),
    )


def _pt001_inputs():
    alert = get_scenario("missed_medication").alert
    triage = _triage("PT-001", UrgencyLevel.URGENT, "Why is BP elevated above baseline?")
    ehr = EHRContext(
        patient_id="PT-001",
        problem_list=[ProblemListEntry(condition="Essential hypertension", icd10_code="I10",
                                       status="active", source_ref="EHR:PT-001/problem_list")],
        medications=[MedicationEntry(name="Lisinopril", dose="10 mg", frequency="daily",
                                     status="active", source_ref="EHR:PT-001/medications")],
        retrieval_confidence=0.8,
        missing_data_flags=["No recent in-clinic BP readings found in the EHR."],
        source_documents=["EHR:PT-001/problem_list", "EHR:PT-001/medications"],
    )
    anam = AnamnesisSummary(
        patient_id="PT-001",
        reported_symptoms=[ReportedSymptom(symptom="persistent dry cough",
                                           patient_words="an annoying dry tickle in my throat",
                                           clinical_interpretation="possible ACE-inhibitor cough",
                                           source_ref="Anamnesis:PT-001/hpi")],
        medication_adherence=AdherenceStatus.NON_ADHERENT,
        adherence_detail="stopped lisinopril ~2 weeks ago due to a dry cough; continues atorvastatin",
        source_documents=["Anamnesis:PT-001/hpi", "Anamnesis:PT-001/adherence"],
    )
    return alert, triage, ehr, anam


def _pt005_inputs():
    alert = get_scenario("conflicting_data").alert
    triage = _triage("PT-005", UrgencyLevel.URGENT, "Why is HR elevated and INR sub-therapeutic?")
    ehr = EHRContext(
        patient_id="PT-005",
        problem_list=[ProblemListEntry(condition="Atrial fibrillation", icd10_code="I48.91",
                                       status="active", source_ref="EHR:PT-005/problem_list")],
        medications=[MedicationEntry(name="Warfarin", dose="5 mg", frequency="daily",
                                     status="active", source_ref="EHR:PT-005/medications")],
        lab_results=[LabResult(test_name="INR", value="1.3", unit="ratio",
                               reference_range="2.0-3.0", flag="low", source_ref="EHR:PT-005/labs")],
        retrieval_confidence=0.85, source_documents=["EHR:PT-005/labs"],
    )
    anam = AnamnesisSummary(
        patient_id="PT-005",
        medication_adherence=AdherenceStatus.ADHERENT,
        adherence_detail="patient insists he takes warfarin every day without missing",
        lifestyle_factors=["recently started large daily kale-and-spinach salads"],
        source_documents=["Anamnesis:PT-005/hpi", "Anamnesis:PT-005/adherence"],
    )
    return alert, triage, ehr, anam


# --- Offline -----------------------------------------------------------------


def test_prompt_loads_with_anti_hallucination_rule():
    agent = SynthesisAgent()
    lowered = " ".join(agent.system_prompt.lower().split())
    assert agent.prompt.version >= 1
    assert "allowed sources" in lowered
    assert "every claim must cite" in lowered or "must be supported by at least one source" in lowered
    assert "never accuse" in lowered


def test_collect_allowed_sources():
    _, _, ehr, anam = _pt001_inputs()
    allowed = collect_allowed_sources(ehr, anam)
    assert "RPM alert" in allowed
    assert "EHR:PT-001/medications" in allowed
    assert "Anamnesis:PT-001/hpi" in allowed
    assert "RPM trend" not in allowed  # only when a trend note is supplied


def test_invalid_citations_detects_hallucinated_source():
    brief = ClinicalContextBrief(
        patient_id="PT-001", alert_summary="x", urgency=UrgencyLevel.URGENT, patient_snapshot="y",
        contextual_analysis=[CitedStatement(statement="claim", sources=["EHR:PT-001/medications",
                                                                        "EHR:PT-001/FABRICATED"])],
    )
    bad = invalid_citations(brief, allowed=["EHR:PT-001/medications", "RPM alert"])
    assert bad == ["EHR:PT-001/FABRICATED"]


# --- Live --------------------------------------------------------------------


@LIVE
def test_live_synthesis_missed_medication_grounded_and_cited():
    alert, triage, ehr, anam = _pt001_inputs()
    allowed = collect_allowed_sources(ehr, anam)
    brief = SynthesisAgent().run(alert, triage, ehr, anam)

    assert isinstance(brief, ClinicalContextBrief)
    assert brief.patient_id == "PT-001"
    assert brief.urgency != UrgencyLevel.INFORMATIONAL
    assert brief.contextual_analysis, "expected contextual analysis"
    # Anti-hallucination: every analytical statement is cited, and only from allowed sources.
    for st in brief.contextual_analysis + brief.risk_assessment:
        assert st.sources, f"uncited statement: {st.statement!r}"
    assert invalid_citations(brief, allowed) == []
    # It connected the dots: cough -> stopped ACE inhibitor -> BP rise.
    blob = brief.model_dump_json().lower()
    assert "cough" in blob and "lisinopril" in blob
    assert brief.uncertainties_and_gaps  # carries the missing-data gap
    assert "1. Alert Summary" in brief.render()
    # generated_at is system metadata set in code, not a model-hallucinated date.
    from datetime import datetime
    assert brief.generated_at.year == datetime.now().year


@LIVE
def test_live_synthesis_conflicting_data_is_neutral():
    alert, triage, ehr, anam = _pt005_inputs()
    allowed = collect_allowed_sources(ehr, anam)
    brief = SynthesisAgent().run(alert, triage, ehr, anam)

    assert brief.patient_id == "PT-005"
    assert invalid_citations(brief, allowed) == []
    text = brief.render().lower()
    assert "inr" in text and "warfarin" in text
    # Flags the discrepancy WITHOUT accusing the patient.
    for bad in ["lying", "accus", "dishonest"]:
        assert bad not in text
