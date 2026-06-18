"""Phase 9 tests: Anamnesis Agent.

Offline tests cover prompt loading, formatting, and the missing-record path. Live tests verify the
agent translates colloquial language (preserving patient words), assesses adherence, and applies
sensitivity guardrails.
"""

import pytest

from clinicalbridge.agents.anamnesis import AnamnesisAgent, format_anamnesis
from clinicalbridge.config import settings
from clinicalbridge.schemas import AdherenceStatus, AnamnesisSummary, RetrievalQuery

LIVE = pytest.mark.skipif(not settings.is_configured, reason="OPENROUTER_API_KEY not configured")


# --- Offline -----------------------------------------------------------------


def test_prompt_loads_with_sensitivity_and_verbatim_rules():
    agent = AnamnesisAgent()
    lowered = " ".join(agent.system_prompt.lower().split())
    assert agent.prompt.version >= 1
    assert "patient_words" in lowered and "verbatim" in lowered
    assert "sensitiv" in lowered and "without judgment" in lowered


def test_format_anamnesis_tags_sources():
    record = {
        "patient_id": "PT-001", "chief_complaint": "High BP",
        "history_of_present_illness": "Stopped his pill due to a cough.",
        "review_of_systems": {"respiratory": "dry cough"},
        "social_history": {"diet": "salty"}, "family_history": ["Father: stroke"],
        "medication_adherence": [{"medication": "Lisinopril", "reported_status": "non_adherent",
                                  "detail": "stopped 2 weeks ago"}],
        "symptom_diary": [{"date": "2026-05-20", "entry": "tickly cough"}],
        "patient_concerns": ["worried"], "sensitive_notes": [],
    }
    out = format_anamnesis(record)
    assert "[Anamnesis:PT-001/hpi]" in out
    assert "[Anamnesis:PT-001/adherence]" in out
    assert "tickly cough" in out


def test_missing_record_is_flagged(tmp_path):
    agent = AnamnesisAgent(anamnesis_dir=tmp_path)  # empty dir → no record
    summary = agent.run("PT-999", RetrievalQuery(focus_terms=["x"], rationale="y"), "q?")
    assert isinstance(summary, AnamnesisSummary)
    assert summary.missing_data_flags


# --- Live --------------------------------------------------------------------


@LIVE
def test_live_translates_and_assesses_adherence(data_root):
    agent = AnamnesisAgent(anamnesis_dir=data_root / "anamnesis")
    summary = agent.run(
        "PT-001",
        RetrievalQuery(focus_terms=["medication adherence", "cough", "side effects"],
                       rationale="why BP rose"),
        "Why has the patient's blood pressure risen?",
    )
    assert summary.patient_id == "PT-001"
    # Adherence problem with the ACE inhibitor should be detected.
    assert summary.medication_adherence in (AdherenceStatus.NON_ADHERENT, AdherenceStatus.PARTIAL)
    blob = summary.model_dump_json().lower()
    assert "cough" in blob          # the colloquial complaint was captured
    # The patient's own words are preserved somewhere in the reported symptoms.
    assert summary.reported_symptoms
    assert any("Anamnesis:PT-001" in s.source_ref for s in summary.reported_symptoms)
    # Citations are normalized (no stray brackets).
    assert all(not s.source_ref.startswith("[") for s in summary.reported_symptoms)


@LIVE
def test_live_sensitivity_guardrail_on_mental_health(data_root):
    agent = AnamnesisAgent(anamnesis_dir=data_root / "anamnesis")
    summary = agent.run(
        "PT-012",  # hypertension + generalized anxiety disorder
        RetrievalQuery(focus_terms=["stress", "anxiety", "blood pressure"], rationale="BP spike"),
        "Why did this patient's blood pressure spike?",
    )
    assert summary.patient_id == "PT-012"
    # Mental-health content should be acknowledged via the sensitive-flags channel.
    assert summary.sensitive_flags, "expected a sensitivity flag for anxiety content"
