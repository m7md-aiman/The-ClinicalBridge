"""Phase 4 tests: dataset is well-formed, internally consistent, deterministic, and carries
the signals required by the five clinical scenarios."""

import json

from clinicalbridge.datagen import CATALOG, DAYS, NOW, build_all, manifest, write_dataset


def test_twelve_patients_with_all_components():
    data = build_all()
    assert len(data) == 12
    for pid, parts in data.items():
        assert set(parts) == {"ehr", "rpm", "anamnesis"}
        assert parts["ehr"]["patient_id"] == pid
        assert parts["rpm"]["patient_id"] == pid
        assert parts["anamnesis"]["patient_id"] == pid


def test_rpm_reading_count_matches_vitals_times_days():
    data = build_all()
    for parts in data.values():
        n_vitals = len(parts["rpm"]["vitals"])
        assert len(parts["rpm"]["readings"]) == n_vitals * DAYS


def test_generation_is_deterministic():
    a = build_all()
    b = build_all()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_internal_consistency_adherence_refs_real_meds():
    """Every medication named in an anamnesis adherence log should exist in that patient's EHR
    med list — except deliberately 'unknown' meds for the sparse-record patient (PT-004)."""
    data = build_all()
    for pid, parts in data.items():
        ehr_meds = {m["name"].lower() for m in parts["ehr"]["medications"]}
        for entry in parts["anamnesis"]["medication_adherence"]:
            med = entry["medication"].lower()
            if "unknown" in med:
                continue
            assert med in ehr_meds, f"{pid}: adherence med {med!r} not in EHR meds {ehr_meds}"


def test_problem_lists_have_icd10():
    data = build_all()
    for pid, parts in data.items():
        for prob in parts["ehr"]["problem_list"]:
            assert prob.get("icd10"), f"{pid}: problem missing ICD-10: {prob}"


# --- Scenario signal checks --------------------------------------------------


def test_scenario1_missed_med_bp_climbs_above_threshold():
    """PT-001: most recent BP reading should be elevated well above the 140 threshold."""
    rpm = build_all()["PT-001"]["rpm"]
    bp = [r for r in rpm["readings"] if r["vital_type"] == "blood_pressure"]
    last = bp[-1]
    assert last["value"] > 160          # systolic clearly high
    assert last["value_secondary"] > 95  # diastolic high
    # early readings were near baseline (controlled)
    assert bp[0]["value"] < 140


def test_scenario2_false_alarm_isolated_glucose_spike():
    """PT-002: only the final glucose reading spikes; the rest are near-normal."""
    rpm = build_all()["PT-002"]["rpm"]
    glu = [r["value"] for r in rpm["readings"] if r["vital_type"] == "blood_glucose"]
    assert glu[-1] > 220                 # the alarming reading
    assert max(glu[:-1]) < 200           # everything before is benign


def test_scenario3_silent_deterioration_weight_trend_within_threshold():
    """PT-003: weight rises ~4 kg but no single reading crosses the absolute high threshold."""
    rpm = build_all()["PT-003"]["rpm"]
    weights = [r["value"] for r in rpm["readings"] if r["vital_type"] == "weight"]
    high = next(v["threshold_high"] for v in rpm["vitals"] if v["vital_type"] == "weight")
    assert weights[-1] - weights[0] >= 2.0          # clinically significant gain
    assert all(w < high for w in weights)            # but each reading is "within threshold"


def test_scenario4_incomplete_record_is_sparse():
    ehr = build_all()["PT-004"]["ehr"]
    assert ehr["record_completeness"] == "sparse"
    assert ehr["medications"] == []
    assert ehr["lab_results"] == []


def test_scenario5_conflicting_data_subtherapeutic_inr_vs_reported_adherence():
    parts = build_all()["PT-005"]
    inrs = [float(l["value"]) for l in parts["ehr"]["lab_results"] if l["test"] == "INR"]
    assert inrs and all(v < 2.0 for v in inrs)       # sub-therapeutic in EHR
    warfarin = [a for a in parts["anamnesis"]["medication_adherence"]
                if a["medication"].lower() == "warfarin"]
    assert warfarin and warfarin[0]["reported_status"] == "adherent"  # but patient reports adherence


def test_write_dataset_creates_files(tmp_path):
    summary = write_dataset(out_root=tmp_path)
    assert summary["patients"] == 12
    for pid in [p["id"] for p in CATALOG]:
        assert (tmp_path / "ehr" / f"{pid}.json").exists()
        assert (tmp_path / "rpm" / f"{pid}.json").exists()
        assert (tmp_path / "anamnesis" / f"{pid}.json").exists()
    assert (tmp_path / "patients.json").exists()
    rows = json.loads((tmp_path / "patients.json").read_text(encoding="utf-8"))
    assert len(rows) == 12


def test_manifest_shape():
    rows = manifest(build_all())
    assert {"patient_id", "name", "age", "conditions", "monitored_vitals"} <= set(rows[0])
    assert NOW.year == 2026  # anchor sanity
