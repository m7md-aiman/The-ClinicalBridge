"""Phase 5 tests: the five scenarios are well-formed, consistent with the dataset, and each
gold-standard brief satisfies its own evaluation rubric."""

import json

import pytest

from clinicalbridge.datagen import build_all
from clinicalbridge.scenarios import (
    build_scenarios,
    get_scenario,
    scenario_ids,
    write_scenarios,
)
from clinicalbridge.schemas import ClinicalContextBrief, RPMAlert, UrgencyLevel

EXPECTED_IDS = {
    "missed_medication", "false_alarm", "silent_deterioration",
    "incomplete_record", "conflicting_data",
}


def test_five_scenarios_present():
    assert set(scenario_ids()) == EXPECTED_IDS


def test_alerts_match_dataset_final_readings():
    """Each scenario alert's reading equals the patient's last reading for that vital."""
    ds = build_all()
    for s in build_scenarios():
        vital = s.alert.reading.vital_type.value
        last = [r for r in ds[s.patient_id]["rpm"]["readings"] if r["vital_type"] == vital][-1]
        assert s.alert.reading.value == last["value"]
        assert s.alert.reading.value_secondary == last.get("value_secondary")


def test_gold_brief_urgency_matches_expected():
    for s in build_scenarios():
        assert s.gold_brief.urgency == s.expected_urgency
        assert s.expected_urgency.value in s.rubric["acceptable_urgencies"]


def test_gold_brief_satisfies_its_own_rubric():
    """A gold brief must contain its must_include terms, flag its must_flag gaps, and avoid its
    must_avoid phrases — using the same concept-matching the evaluator uses."""
    from clinicalbridge.evaluation.metrics import avoid_present, term_present

    for s in build_scenarios():
        text = s.gold_brief.render().lower()
        gaps = " ".join(s.gold_brief.uncertainties_and_gaps).lower()
        for term in s.rubric["must_include"]:
            assert term_present(text, term), f"{s.id}: gold missing must_include {term!r}"
        for term in s.rubric["must_flag"]:
            assert term_present(text + " " + gaps, term), f"{s.id}: gold missing must_flag {term!r}"
        for term in s.rubric["must_avoid"]:
            assert not avoid_present(text, term), f"{s.id}: gold contains must_avoid {term!r}"


def test_every_gold_claim_is_cited():
    """Anti-hallucination at the gold level: each analytical statement carries >=1 source."""
    for s in build_scenarios():
        for stmt in s.gold_brief.contextual_analysis + s.gold_brief.risk_assessment:
            assert stmt.sources, f"{s.id}: uncited statement: {stmt.statement!r}"


def test_conflicting_data_avoids_accusation():
    s = get_scenario("conflicting_data")
    text = s.gold_brief.render().lower()
    for bad in ["lying", "accus", "dishonest"]:
        assert bad not in text


def test_false_alarm_not_over_escalated():
    s = get_scenario("false_alarm")
    assert s.expected_urgency in (UrgencyLevel.ROUTINE, UrgencyLevel.INFORMATIONAL)


def test_get_scenario_unknown_raises():
    with pytest.raises(KeyError):
        get_scenario("does_not_exist")


def test_write_scenarios_roundtrip(tmp_path):
    n = write_scenarios(out_dir=tmp_path)
    assert n == 5
    for sid in EXPECTED_IDS:
        data = json.loads((tmp_path / f"{sid}.json").read_text(encoding="utf-8"))
        # Persisted alert and gold brief reload into their Pydantic models.
        RPMAlert.model_validate(data["alert"])
        ClinicalContextBrief.model_validate(data["gold_brief"])
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(index) == 5
