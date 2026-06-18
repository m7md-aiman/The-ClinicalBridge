"""Phase 2 tests: data contracts validate, round-trip through JSON, and render."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from clinicalbridge.schemas import (
    AdherenceStatus,
    AnamnesisSummary,
    CitedStatement,
    ClinicalContextBrief,
    ConfidenceLevel,
    EHRContext,
    LabResult,
    MedicationEntry,
    ProblemListEntry,
    RecommendedAction,
    ReportedSymptom,
    RetrievalQuery,
    RPMAlert,
    RPMThreshold,
    TriageDecision,
    TrendDirection,
    UrgencyLevel,
    VitalReading,
    VitalType,
)


def _sample_alert() -> RPMAlert:
    return RPMAlert(
        alert_id="ALERT-001",
        patient_id="PT-001",
        timestamp=datetime(2026, 6, 1, 8, 30),
        device_type="BP cuff",
        reading=VitalReading(
            vital_type=VitalType.BLOOD_PRESSURE, value=178, value_secondary=104, unit="mmHg"
        ),
        device_alert_category="BP_HIGH",
        baseline_value=128,
        thresholds=RPMThreshold(vital_type=VitalType.BLOOD_PRESSURE, high=140, low=90, unit="mmHg"),
        notes="sustained over 3 morning readings",
    )


def test_vital_reading_display_paired_and_single():
    bp = VitalReading(vital_type=VitalType.BLOOD_PRESSURE, value=178, value_secondary=104, unit="mmHg")
    assert bp.display() == "178/104 mmHg"
    hr = VitalReading(vital_type=VitalType.HEART_RATE, value=92, unit="bpm")
    assert hr.display() == "92 bpm"


def test_rpm_alert_construction_and_json_roundtrip():
    alert = _sample_alert()
    dumped = alert.model_dump_json()
    restored = RPMAlert.model_validate_json(dumped)
    assert restored == alert
    assert restored.reading.vital_type is VitalType.BLOOD_PRESSURE


def test_triage_decision_requires_queries():
    decision = TriageDecision(
        patient_id="PT-001",
        urgency=UrgencyLevel.URGENT,
        clinical_question="Why is this patient's BP acutely elevated above baseline?",
        reasoning="178/104 is well above the 140 threshold and baseline 128; sustained.",
        requires_immediate_escalation=False,
        ehr_query=RetrievalQuery(focus_terms=["hypertension", "ACE inhibitor"], rationale="meds/dx"),
        anamnesis_query=RetrievalQuery(focus_terms=["adherence", "cough"], rationale="self-report"),
    )
    assert decision.urgency is UrgencyLevel.URGENT
    assert "hypertension" in decision.ehr_query.focus_terms


def test_triage_decision_rejects_bad_urgency():
    with pytest.raises(ValidationError):
        TriageDecision(
            patient_id="PT-001",
            urgency="EMERGENCY",  # not a valid UrgencyLevel
            clinical_question="q",
            reasoning="r",
            ehr_query=RetrievalQuery(focus_terms=[], rationale="x"),
            anamnesis_query=RetrievalQuery(focus_terms=[], rationale="x"),
        )


def test_ehr_context_confidence_bounds():
    with pytest.raises(ValidationError):
        EHRContext(patient_id="PT-001", retrieval_confidence=1.7)


def test_full_brief_construction_and_render():
    ehr = EHRContext(
        patient_id="PT-001",
        problem_list=[ProblemListEntry(condition="Essential hypertension", icd10_code="I10",
                                       status="active", source_ref="ehr/PT-001#problems")],
        medications=[MedicationEntry(name="Lisinopril", dose="10 mg", frequency="daily",
                                     status="active", source_ref="ehr/PT-001#meds")],
        lab_results=[LabResult(test_name="Potassium", value="4.1", unit="mmol/L",
                               trend=TrendDirection.STABLE, source_ref="ehr/PT-001#labs")],
        retrieval_confidence=0.82,
        missing_data_flags=["No BP readings logged in clinic in last 6 months"],
        source_documents=["ehr/PT-001"],
    )
    anam = AnamnesisSummary(
        patient_id="PT-001",
        reported_symptoms=[ReportedSymptom(symptom="dry cough", patient_words="this annoying tickle",
                                           clinical_interpretation="possible ACE-inhibitor cough",
                                           source_ref="anamnesis/PT-001#ros")],
        medication_adherence=AdherenceStatus.NON_ADHERENT,
        adherence_detail="stopped lisinopril 2 weeks ago due to cough",
        source_documents=["anamnesis/PT-001"],
    )
    brief = ClinicalContextBrief(
        patient_id="PT-001",
        alert_summary="Sustained BP 178/104 mmHg, well above baseline (128) — classified Urgent.",
        urgency=UrgencyLevel.URGENT,
        patient_snapshot="68yo with essential hypertension (I10), prescribed lisinopril 10 mg daily.",
        contextual_analysis=[
            CitedStatement(statement="BP rise coincides with self-reported cessation of lisinopril.",
                           sources=["anamnesis/PT-001#ros", "RPM alert"]),
        ],
        risk_assessment=[
            CitedStatement(statement="Uncontrolled hypertension raises cardiovascular/stroke risk.",
                           sources=["ehr/PT-001#problems"]),
        ],
        recommended_actions=[
            RecommendedAction(action="Contact patient to confirm medication status",
                              confidence=ConfidenceLevel.HIGH,
                              supporting_evidence=["anamnesis/PT-001#ros"]),
        ],
        uncertainties_and_gaps=["EHR does not record the cough side effect; relies on self-report."],
        overall_confidence=ConfidenceLevel.HIGH,
        cited_sources=["RPM alert", "ehr/PT-001#problems", "anamnesis/PT-001#ros"],
    )
    # JSON round-trip preserves the structure.
    restored = ClinicalContextBrief.model_validate_json(brief.model_dump_json())
    assert restored.urgency is UrgencyLevel.URGENT
    assert len(restored.contextual_analysis) == 1

    # render() produces all six numbered sections.
    md = brief.render()
    for heading in ["1. Alert Summary", "2. Patient Snapshot", "3. Contextual Analysis",
                    "4. Risk Assessment", "5. Recommended Actions", "6. Uncertainties & Gaps"]:
        assert heading in md
    assert "anamnesis/PT-001#ros" in md
    assert ehr.retrieval_confidence == 0.82  # sanity on the EHR object too
