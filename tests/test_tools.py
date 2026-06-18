"""Phase 10 tests: tool registry + deterministic analysis tools (all offline)."""

from datetime import datetime

import pytest

from clinicalbridge.schemas import RPMAlert, RPMThreshold, UrgencyLevel, VitalReading, VitalType
from clinicalbridge.tools import (
    classify_alert_severity,
    compute_trend,
    get_tool,
    list_tools,
    load_patient_record,
    severity_to_urgency,
    summarize_vital_series,
)


def test_registry_contains_expected_tools():
    names = {t.name for t in list_tools()}
    assert {"compute_trend", "summarize_vital_series", "classify_alert_severity",
            "load_patient_record", "search_ehr"} <= names
    assert get_tool("compute_trend").description


def test_get_tool_unknown_raises():
    with pytest.raises(KeyError):
        get_tool("nope")


def test_compute_trend_directions():
    assert compute_trend([81.8, 82.2, 83.5, 85.0, 85.8])["direction"] == "rising"
    assert compute_trend([5, 4, 3, 2, 1])["direction"] == "falling"
    assert compute_trend([120, 119, 121, 120, 120])["direction"] == "stable"
    assert compute_trend([])["direction"] == "unknown"


def test_compute_trend_stats():
    out = compute_trend([81.8, 85.8])
    assert out["change"] == 4.0 and out["first"] == 81.8 and out["last"] == 85.8


def test_summarize_vital_series_filters_by_type():
    rpm = {"readings": [
        {"vital_type": "weight", "value": 81.0},
        {"vital_type": "weight", "value": 85.0},
        {"vital_type": "heart_rate", "value": 70},
    ]}
    out = summarize_vital_series(rpm, "weight")
    assert out["count"] == 2 and out["direction"] == "rising"


def _alert(vt, value, unit, high=None, low=None):
    return RPMAlert(
        alert_id="A", patient_id="PT-X", timestamp=datetime(2026, 6, 1, 8, 0), device_type="dev",
        reading=VitalReading(vital_type=vt, value=value, unit=unit),
        device_alert_category="CAT",
        thresholds=RPMThreshold(vital_type=vt, high=high, low=low, unit=unit),
    )


def test_classify_alert_severity_rules():
    assert classify_alert_severity(_alert(VitalType.SPO2, 83, "%", low=90))["severity"] == "critical"
    assert classify_alert_severity(_alert(VitalType.BLOOD_PRESSURE, 182, "mmHg", high=140))["severity"] == "urgent"
    assert classify_alert_severity(_alert(VitalType.BLOOD_GLUCOSE, 247, "mg/dL", high=180))["severity"] == "routine"
    assert classify_alert_severity(_alert(VitalType.HEART_RATE, 124, "bpm", high=110))["severity"] == "urgent"
    # Weight is trend-based: a single in-threshold reading is NOT escalated by the rule tool.
    assert classify_alert_severity(_alert(VitalType.WEIGHT, 85.8, "kg", high=88))["severity"] == "informational"


def test_severity_to_urgency_mapping():
    assert severity_to_urgency("critical") is UrgencyLevel.CRITICAL
    assert severity_to_urgency("informational") is UrgencyLevel.INFORMATIONAL


def test_load_patient_record_tool(data_root):
    from clinicalbridge import dataio

    # Underlying loaders work against an explicit directory (here, the fixture dataset).
    assert dataio.load_ehr("PT-001", ehr_dir=data_root / "ehr")["patient_id"] == "PT-001"
    assert dataio.load_anamnesis("PT-001", anamnesis_dir=data_root / "anamnesis")["patient_id"] == "PT-001"
    # The registered tool validates its source argument.
    with pytest.raises(ValueError):
        load_patient_record("PT-001", "bogus")
