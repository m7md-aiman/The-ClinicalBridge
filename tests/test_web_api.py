"""W1 tests: the FastAPI backend (offline, against bundled cache where present)."""

import pytest
from fastapi.testclient import TestClient

from web.backend.app import app
from web.backend.cache import cached_run

client = TestClient(app)


def test_meta():
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert "live_available" in body and isinstance(body["live_available"], bool)
    assert body["name"] == "ClinicalBridge"


def test_list_scenarios():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 5
    ids = {s["id"] for s in rows}
    assert {"missed_medication", "false_alarm", "silent_deterioration",
            "incomplete_record", "conflicting_data"} == ids
    for s in rows:
        assert s["expected_urgency"] and s["alert_display"]


def test_scenario_detail_includes_gold_and_rubric():
    r = client.get("/api/scenarios/missed_medication")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "missed_medication"
    assert "rubric" in body and "must_include" in body["rubric"]
    assert body["gold_brief_markdown"].startswith("# Clinical Context Brief")


def test_unknown_scenario_404():
    assert client.get("/api/scenarios/nope").status_code == 404


def test_evaluation_endpoint_shape():
    r = client.get("/api/evaluation")
    assert r.status_code == 200
    assert set(r.json().keys()) == {"report", "progression"}


@pytest.mark.skipif(cached_run("missed_medication") is None,
                    reason="web cache not built yet (run scripts/build_web_cache.py)")
def test_cached_result_payload():
    r = client.get("/api/results/missed_medication")
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is True
    assert body["result"]["patient_id"] == "PT-001"
    assert "brief" in body["result"]
    assert "score" in body and "passed" in body["score"]
    # Anti-hallucination invariant should hold in the cached run.
    assert body["score"]["hallucination_count"] == 0
