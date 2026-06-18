"""Phase 10 tests: session (working/audit) memory and persistent patient (entity) memory."""

import json

from clinicalbridge.memory import PatientMemory, SessionMemory


def test_session_memory_logs_and_saves(tmp_path):
    mem = SessionMemory(alert_id="ALERT-PT-001", patient_id="PT-001")
    mem.log("triage", "Classified Urgent", {"urgency": "Urgent"})
    mem.log("ehr", "Found hypertension + lisinopril")
    assert mem.steps() == ["triage", "ehr"]
    path = mem.save(tmp_path / "session.json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["patient_id"] == "PT-001"
    assert len(saved["events"]) == 2
    assert saved["events"][0]["data"]["urgency"] == "Urgent"


def test_patient_memory_persists_across_instances(tmp_path):
    mem = PatientMemory(store_dir=tmp_path)
    mem.record_interaction("PT-001", urgency="Urgent", summary="BP elevated after stopping ACEi",
                           flags=["self-report only"], alert_id="A1")
    # A fresh instance reads the persisted file.
    mem2 = PatientMemory(store_dir=tmp_path)
    history = mem2.history("PT-001")
    assert len(history) == 1
    assert history[0]["urgency"] == "Urgent"
    assert mem2.last("PT-001")["alert_id"] == "A1"


def test_patient_memory_digest_is_injectable_text(tmp_path):
    mem = PatientMemory(store_dir=tmp_path)
    mem.record_interaction("PT-003", urgency="Routine", summary="Weight stable")
    mem.record_interaction("PT-003", urgency="Urgent", summary="Weight trending up, fluid retention")
    digest = mem.digest("PT-003", limit=2)
    assert "PT-003" in digest
    assert "Urgent" in digest and "fluid retention" in digest
    assert digest.count("- [") == 2  # two entries rendered


def test_patient_memory_empty_history(tmp_path):
    mem = PatientMemory(store_dir=tmp_path)
    assert mem.history("PT-NONE") == []
    assert mem.last("PT-NONE") is None
    assert mem.digest("PT-NONE") == ""
