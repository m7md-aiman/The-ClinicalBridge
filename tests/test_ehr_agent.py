"""Phase 8 tests: EHR Retrieval Agent.

Offline tests cover prompt loading and context formatting. Live tests (skipped without an API key)
run the agent against the real vector store and check grounding, citation, and missing-data flagging.
"""

import pytest
from langchain_core.documents import Document

from clinicalbridge.agents.ehr import EHRRetrievalAgent, format_context
from clinicalbridge.config import settings
from clinicalbridge.schemas import EHRContext, RetrievalQuery

LIVE = pytest.mark.skipif(not settings.is_configured, reason="OPENROUTER_API_KEY not configured")


# --- Offline -----------------------------------------------------------------


def test_prompt_loads_and_is_analyst_not_diagnostician():
    agent = EHRRetrievalAgent(retriever=object())  # retriever not used here
    text = agent.system_prompt
    assert agent.prompt.version >= 1
    lowered = " ".join(text.lower().split())  # normalize line wrapping
    assert "data analyst" in lowered
    assert "not a diagnostician" in lowered
    assert "do not diagnose" in lowered
    assert "source_ref" in text


def test_format_context_labels_sources():
    docs = [
        Document(page_content="Patient X. Medication: Lisinopril 10 mg.",
                 metadata={"source_ref": "EHR:PT-001/medications", "section": "medications"}),
    ]
    out = format_context(docs)
    assert "EHR:PT-001/medications" in out and "Lisinopril" in out


def test_format_context_empty():
    assert "No EHR excerpts" in format_context([])


def test_no_docs_returns_flagged_empty_context():
    """If retrieval yields nothing, the agent must flag it (and not call the LLM)."""
    class EmptyRetriever:
        def search(self, *a, **k):
            return []

    ctx = EHRRetrievalAgent(retriever=EmptyRetriever()).run(
        "PT-404", RetrievalQuery(focus_terms=["anything"], rationale="x"), "any question")
    assert isinstance(ctx, EHRContext)
    assert ctx.retrieval_confidence == 0.0
    assert ctx.missing_data_flags


# --- Live --------------------------------------------------------------------


@LIVE
def test_live_extracts_grounded_cited_context(ehr_retriever):
    agent = EHRRetrievalAgent(retriever=ehr_retriever)
    ctx = agent.run(
        "PT-001",
        RetrievalQuery(focus_terms=["hypertension", "antihypertensive medications", "recent BP"],
                       rationale="interpret high BP alert"),
        "Why is this patient's blood pressure elevated above baseline?",
    )
    assert ctx.patient_id == "PT-001"
    # Grounded findings should mention the patient's real condition/medication.
    blob = (ctx.model_dump_json()).lower()
    assert "hypertension" in blob or "lisinopril" in blob
    # Every extracted item must be cited to a PT-001 source.
    items = ctx.problem_list + ctx.medications + ctx.lab_results + ctx.visit_notes
    assert items, "expected at least one extracted item"
    for it in items:
        assert it.source_ref.startswith("EHR:PT-001"), f"bad source_ref: {it.source_ref}"


@LIVE
def test_live_sparse_record_flags_missing_data(ehr_retriever):
    agent = EHRRetrievalAgent(retriever=ehr_retriever)
    ctx = agent.run(
        "PT-004",
        RetrievalQuery(focus_terms=["hypertension", "medications", "recent labs"],
                       rationale="sparse transfer patient"),
        "What is known about this newly transferred patient?",
    )
    assert ctx.patient_id == "PT-004"
    assert ctx.missing_data_flags, "sparse record should produce missing-data flags"
    # No medications exist in PT-004's record, so none should be fabricated.
    assert ctx.medications == [] or all("unknown" in m.name.lower() for m in ctx.medications)
