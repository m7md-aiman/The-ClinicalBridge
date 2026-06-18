"""Phase 7 tests: EHR RAG pipeline.

Structural tests use a deterministic fake embedding (no model download) to verify chunking,
metadata, persistence, and patient filtering. A semantic retrieval-quality test using the real
embedding model is gated behind the CB_RUN_RAG_TESTS=1 env var (it downloads/loads the model).
"""

import hashlib
import os

import pytest
from langchain_core.embeddings import Embeddings

from clinicalbridge.datagen import write_dataset
from clinicalbridge.rag.ingest import build_vectorstore, ehr_to_documents, load_ehr_documents
from clinicalbridge.rag.retriever import EHRRetriever


class HashEmbeddings(Embeddings):
    """Deterministic, offline embedding: maps text to a fixed-size vector via SHA-256."""

    def __init__(self, size: int = 32) -> None:
        self.size = size

    def _vec(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vals = [b / 255.0 for b in digest[: self.size]]
        return vals + [0.0] * (self.size - len(vals))

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    write_dataset(out_root=d)
    return d


# --- Chunking ---------------------------------------------------------------


def test_ehr_to_documents_sections_and_metadata():
    ehr = {
        "patient_id": "PT-001", "name": "Test Patient", "age": 68, "sex": "male",
        "problem_list": [{"condition": "Essential hypertension", "icd10": "I10",
                          "status": "active", "onset_date": "2016-04-10"}],
        "medications": [{"name": "Lisinopril", "dose": "10 mg", "frequency": "daily",
                         "status": "active", "started": "2016-04-10"}],
        "lab_results": [{"test": "Potassium", "value": "4.2", "unit": "mmol/L",
                         "reference_range": "3.5-5.1", "date": "2026-03-15", "flag": "normal"}],
        "visit_notes": [{"date": "2026-03-15", "author": "Dr. P", "specialty": "PC", "note": "Stable."}],
        "allergies": [], "record_completeness": "complete",
    }
    docs = ehr_to_documents(ehr)
    sections = {d.metadata["section"] for d in docs}
    assert {"problem_list", "medications", "labs", "visit_note", "allergies"} <= sections
    for d in docs:
        assert d.metadata["patient_id"] == "PT-001"
        assert d.metadata["source_ref"].startswith("EHR:PT-001/")
        # No null metadata (Chroma requirement).
        assert all(v is not None for v in d.metadata.values())
    med = next(d for d in docs if d.metadata["section"] == "medications")
    assert "Lisinopril" in med.page_content


def test_sparse_record_gets_status_chunk(dataset_dir):
    docs = load_ehr_documents(dataset_dir / "ehr")
    pt004 = [d for d in docs if d.metadata["patient_id"] == "PT-004"]
    assert any(d.metadata["section"] == "record_status" for d in pt004)
    assert not any(d.metadata["section"] == "medications" for d in pt004)  # sparse: no meds


def test_load_all_patients(dataset_dir):
    docs = load_ehr_documents(dataset_dir / "ehr")
    pids = {d.metadata["patient_id"] for d in docs}
    assert len(pids) == 12


# --- Persistence + filtering (fake embeddings) ------------------------------


def test_build_and_patient_filtered_retrieval(dataset_dir, tmp_path):
    vs = build_vectorstore(
        persist_dir=tmp_path / "chroma", ehr_dir=dataset_dir / "ehr",
        embeddings=HashEmbeddings(), reset=True,
    )
    retriever = EHRRetriever(vectorstore=vs, k=5)
    results = retriever.search("hypertension medication", patient_id="PT-001")
    assert results, "expected at least one chunk"
    assert all(d.metadata["patient_id"] == "PT-001" for d in results)  # no cross-patient leakage


# --- Semantic quality (real embeddings, opt-in) -----------------------------


@pytest.mark.skipif(os.getenv("CB_RUN_RAG_TESTS") != "1",
                    reason="set CB_RUN_RAG_TESTS=1 to run the real-embedding retrieval test")
def test_real_embedding_retrieval_quality(dataset_dir, tmp_path):
    from clinicalbridge.rag.ingest import get_embeddings

    vs = build_vectorstore(
        persist_dir=tmp_path / "chroma_real", ehr_dir=dataset_dir / "ehr",
        embeddings=get_embeddings(), reset=True,
    )
    retriever = EHRRetriever(vectorstore=vs, k=3)
    # The patient's BP medication should surface for a semantic BP-meds query.
    results = retriever.search("blood pressure lowering medication", patient_id="PT-001")
    joined = " ".join(d.page_content.lower() for d in results)
    assert "lisinopril" in joined or "hypertension" in joined
    assert all(d.metadata["patient_id"] == "PT-001" for d in results)
