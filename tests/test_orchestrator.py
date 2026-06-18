"""Phase 12 tests: the Orchestrator.

Offline tests use stub agents (no LLM) to verify routing, the severity-floor guardrail, escalation,
graceful fallback, parallelism, and serialization. One live test runs the real end-to-end pipeline.
"""

from datetime import datetime

import pytest

from clinicalbridge.config import settings
from clinicalbridge.orchestrator import Orchestrator
from clinicalbridge.schemas import (
    AnamnesisSummary,
    ClinicalContextBrief,
    EHRContext,
    ProblemListEntry,
    RetrievalQuery,
    RPMAlert,
    RPMThreshold,
    TriageDecision,
    UrgencyLevel,
    VitalReading,
    VitalType,
)

LIVE = pytest.mark.skipif(not settings.is_configured, reason="OPENROUTER_API_KEY not configured")


# --- Stubs -------------------------------------------------------------------


class StubTriage:
    def __init__(self, urgency=UrgencyLevel.ROUTINE, escalate=False):
        self.urgency, self.escalate = urgency, escalate

    def run(self, alert):
        return TriageDecision(
            patient_id=alert.patient_id, urgency=self.urgency, clinical_question="q?",
            reasoning="r", requires_immediate_escalation=self.escalate,
            ehr_query=RetrievalQuery(focus_terms=["a"], rationale="x"),
            anamnesis_query=RetrievalQuery(focus_terms=["b"], rationale="y"),
        )


class StubEHR:
    def __init__(self, raise_=False):
        self.called, self.raise_ = False, raise_

    def run_from_triage(self, triage):
        self.called = True
        if self.raise_:
            raise RuntimeError("ehr boom")
        return EHRContext(patient_id=triage.patient_id, retrieval_confidence=0.7,
                          problem_list=[ProblemListEntry(condition="Hypertension", source_ref="EHR:x")])


class StubAnamnesis:
    def __init__(self, raise_=False):
        self.called, self.raise_ = False, raise_

    def run_from_triage(self, triage):
        self.called = True
        if self.raise_:
            raise RuntimeError("anamnesis boom")
        return AnamnesisSummary(patient_id=triage.patient_id, source_documents=["anamnesis/x"])


class StubSynthesis:
    def __init__(self, urgency=UrgencyLevel.ROUTINE, raise_=False):
        self.urgency, self.raise_ = urgency, raise_

    def run(self, alert, triage, ehr, anam, *, prior_context="", rpm_trend_note=""):
        if self.raise_:
            raise RuntimeError("synthesis boom")
        return ClinicalContextBrief(patient_id=alert.patient_id, alert_summary="summary",
                                    urgency=self.urgency, patient_snapshot="snapshot")


def _alert(vt=VitalType.BLOOD_PRESSURE, value=178, secondary=100, unit="mmHg",
           category="BP_HIGH", high=140, low=90, pid="PT-001"):
    return RPMAlert(
        alert_id=f"ALERT-{pid}", patient_id=pid, timestamp=datetime(2026, 6, 1, 8, 0),
        device_type="dev", reading=VitalReading(vital_type=vt, value=value, value_secondary=secondary, unit=unit),
        device_alert_category=category, baseline_value=None,
        thresholds=RPMThreshold(vital_type=vt, high=high, low=low, unit=unit),
    )


def _orch(**kw):
    return Orchestrator(triage=kw.get("triage", StubTriage()), ehr=kw.get("ehr", StubEHR()),
                        anamnesis=kw.get("anamnesis", StubAnamnesis()),
                        synthesis=kw.get("synthesis", StubSynthesis()), rpm_dir=kw.get("rpm_dir"))


# --- Offline -----------------------------------------------------------------


def test_happy_path_runs_full_flow(tmp_path):
    res = _orch(rpm_dir=tmp_path).process_alert(_alert())
    assert res.brief is not None
    steps = res.session.steps()
    for s in ["alert_received", "triage", "ehr_retrieval", "anamnesis", "synthesis", "complete"]:
        assert s in steps
    assert not res.errors


def test_parallel_retrieval_calls_both(tmp_path):
    ehr, anam = StubEHR(), StubAnamnesis()
    _orch(ehr=ehr, anamnesis=anam, rpm_dir=tmp_path).process_alert(_alert())
    assert ehr.called and anam.called


def test_severity_floor_escalates_critical(tmp_path):
    """A critical-by-rule SpO2 alert must escalate even if the (stub) triage says Routine."""
    alert = _alert(vt=VitalType.SPO2, value=83, secondary=None, unit="%", category="SPO2_LOW", high=None, low=90)
    res = _orch(triage=StubTriage(urgency=UrgencyLevel.ROUTINE),
                synthesis=StubSynthesis(urgency=UrgencyLevel.ROUTINE), rpm_dir=tmp_path).process_alert(alert)
    assert res.final_urgency == UrgencyLevel.CRITICAL   # floor raised it
    assert res.escalated is True
    assert "escalation" in res.session.steps()


def test_weight_trend_guardrail_escalates(data_root):
    """A rising-weight trend (PT-003) must be escalated to Urgent by the deterministic guardrail,
    even when the (stub) synthesis only says Routine — the safety rule does not rely on the LLM."""
    alert = _alert(vt=VitalType.WEIGHT, value=85.8, secondary=None, unit="kg",
                   category="WEIGHT_GAIN_TREND", high=88, low=70, pid="PT-003")
    res = _orch(synthesis=StubSynthesis(urgency=UrgencyLevel.ROUTINE),
                rpm_dir=data_root / "rpm").process_alert(alert)
    assert res.final_urgency == UrgencyLevel.URGENT
    assert "trend_guardrail" in res.session.steps()


def test_synthesis_failure_produces_fallback_brief(tmp_path):
    res = _orch(synthesis=StubSynthesis(raise_=True), rpm_dir=tmp_path).process_alert(_alert())
    assert res.brief is not None
    assert any("synthesis" in e for e in res.errors)
    assert "unavailable" in res.brief.patient_snapshot.lower()


def test_ehr_failure_degrades_gracefully(tmp_path):
    res = _orch(ehr=StubEHR(raise_=True), rpm_dir=tmp_path).process_alert(_alert())
    assert any("ehr_retrieval" in e for e in res.errors)
    assert res.ehr_context.missing_data_flags  # fallback context carries a flag
    assert res.brief is not None               # pipeline still finished


def test_result_to_dict_is_serializable(tmp_path):
    import json
    res = _orch(rpm_dir=tmp_path).process_alert(_alert())
    blob = json.dumps(res.to_dict())  # must not raise
    assert '"final_urgency"' in blob and '"brief"' in blob


# --- Live --------------------------------------------------------------------


@LIVE
def test_live_end_to_end_missed_medication(ehr_retriever, data_root):
    from clinicalbridge.agents.anamnesis import AnamnesisAgent
    from clinicalbridge.agents.ehr import EHRRetrievalAgent
    from clinicalbridge.agents.synthesis import collect_allowed_sources, invalid_citations
    from clinicalbridge.scenarios import get_scenario

    scenario = get_scenario("missed_medication")
    orch = Orchestrator(
        ehr=EHRRetrievalAgent(retriever=ehr_retriever),
        anamnesis=AnamnesisAgent(anamnesis_dir=data_root / "anamnesis"),
        rpm_dir=data_root / "rpm",
    )
    res = orch.process_alert(scenario.alert)

    assert res.patient_id == "PT-001"
    assert res.brief.urgency != UrgencyLevel.INFORMATIONAL
    assert {"triage", "ehr_retrieval", "anamnesis", "synthesis", "complete"} <= set(res.session.steps())
    # End-to-end anti-hallucination: the final brief cites only real upstream sources.
    # The orchestrator supplies a computed RPM trend note, so "RPM trend" is also allowed.
    allowed = collect_allowed_sources(res.ehr_context, res.anamnesis_summary, include_rpm_trend=True)
    assert invalid_citations(res.brief, allowed) == []
    blob = res.brief.model_dump_json().lower()
    assert "cough" in blob and "lisinopril" in blob
