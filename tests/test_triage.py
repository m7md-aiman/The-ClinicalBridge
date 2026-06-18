"""Phase 6 tests: Alert Triage Agent.

Offline tests check prompt loading and alert formatting. Live tests (skipped without an API key)
verify the agent returns well-formed, sensible triage decisions from real OpenRouter calls.

Note: triage urgency is an ALERT-ONLY judgment (the agent has no history yet), so it is NOT
asserted to equal a scenario's final/gold urgency — only to be clinically reasonable.
"""

from datetime import datetime

import pytest

from clinicalbridge.agents.triage import TriageAgent, format_alert
from clinicalbridge.config import settings
from clinicalbridge.scenarios import build_scenarios
from clinicalbridge.schemas import (
    RPMAlert,
    RPMThreshold,
    TriageDecision,
    UrgencyLevel,
    VitalReading,
    VitalType,
)

LIVE = pytest.mark.skipif(not settings.is_configured, reason="OPENROUTER_API_KEY not configured")


# --- Offline -----------------------------------------------------------------


def test_prompt_loads_v1_with_urgency_levels():
    agent = TriageAgent()
    assert agent.prompt.version >= 1
    text = agent.system_prompt
    for level in ["Critical", "Urgent", "Routine", "Informational"]:
        assert level in text


def test_format_alert_contains_key_fields():
    alert = RPMAlert(
        alert_id="A1", patient_id="PT-999", timestamp=datetime(2026, 6, 1, 8, 0),
        device_type="BP cuff",
        reading=VitalReading(vital_type=VitalType.BLOOD_PRESSURE, value=176, value_secondary=102, unit="mmHg"),
        device_alert_category="BP_HIGH", baseline_value=128,
        thresholds=RPMThreshold(vital_type=VitalType.BLOOD_PRESSURE, high=140, low=90, unit="mmHg"),
        notes="sustained over 3 readings",
    )
    text = format_alert(alert)
    assert "PT-999" in text and "176/102 mmHg" in text
    assert "threshold high: 140" in text and "baseline: 128" in text
    assert "sustained over 3 readings" in text


def test_format_alert_handles_unknown_baseline():
    alert = RPMAlert(
        alert_id="A2", patient_id="PT-000", timestamp=datetime(2026, 6, 1, 8, 0),
        device_type="loaner cuff",
        reading=VitalReading(vital_type=VitalType.BLOOD_PRESSURE, value=158, value_secondary=96, unit="mmHg"),
        device_alert_category="BP_HIGH", baseline_value=None,
        thresholds=RPMThreshold(vital_type=VitalType.BLOOD_PRESSURE, high=140, low=90, unit="mmHg"),
    )
    assert "baseline: unknown" in format_alert(alert)


# --- Live --------------------------------------------------------------------


def _critical_alert() -> RPMAlert:
    return RPMAlert(
        alert_id="A-CRIT", patient_id="PT-TEST", timestamp=datetime(2026, 6, 1, 8, 0),
        device_type="pulse oximeter",
        reading=VitalReading(vital_type=VitalType.SPO2, value=84, unit="%"),
        device_alert_category="SPO2_LOW", baseline_value=95,
        thresholds=RPMThreshold(vital_type=VitalType.SPO2, low=90, high=None, unit="%"),
        notes="patient reports acute shortness of breath",
    )


@LIVE
def test_live_critical_alert_classified_high_and_escalates():
    decision = TriageAgent().run(_critical_alert())
    assert isinstance(decision, TriageDecision)
    assert decision.urgency in (UrgencyLevel.CRITICAL, UrgencyLevel.URGENT)
    if decision.urgency == UrgencyLevel.CRITICAL:
        assert decision.requires_immediate_escalation is True
    assert decision.patient_id == "PT-TEST"


@LIVE
def test_live_triage_on_all_scenarios_is_wellformed():
    for s in build_scenarios():
        decision = TriageAgent().run(s.alert)
        assert decision.patient_id == s.patient_id
        assert decision.reasoning.strip()
        assert decision.clinical_question.strip()
        assert len(decision.ehr_query.focus_terms) >= 1
        assert len(decision.anamnesis_query.focus_terms) >= 1


@LIVE
def test_live_high_bp_scenario_not_trivially_low():
    # PT-001 alert is 178/100 sustained — alert-only triage should not be Informational.
    s = next(s for s in build_scenarios() if s.id == "missed_medication")
    decision = TriageAgent().run(s.alert)
    assert decision.urgency in (UrgencyLevel.URGENT, UrgencyLevel.CRITICAL, UrgencyLevel.ROUTINE)
    assert decision.urgency != UrgencyLevel.INFORMATIONAL
