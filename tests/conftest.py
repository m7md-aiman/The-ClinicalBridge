"""Shared pytest fixtures for ClinicalBridge.

Builds the simulated dataset and (when needed) a real-embedding EHR vector store once per session,
so the agent integration tests can share them without rebuilding repeatedly.
"""

import pytest

from clinicalbridge.datagen import write_dataset


@pytest.fixture(scope="session")
def data_root(tmp_path_factory):
    """Generate the full simulated dataset into a temp directory once per test session."""
    root = tmp_path_factory.mktemp("cb_data")
    write_dataset(out_root=root)
    return root


@pytest.fixture(scope="session")
def ehr_retriever(data_root, tmp_path_factory):
    """A real-embedding EHRRetriever over a freshly built vector store (built once per session)."""
    from clinicalbridge.rag.ingest import build_vectorstore, get_embeddings
    from clinicalbridge.rag.retriever import EHRRetriever

    persist = tmp_path_factory.mktemp("cb_chroma")
    vs = build_vectorstore(
        persist_dir=persist, ehr_dir=data_root / "ehr",
        embeddings=get_embeddings(), reset=True,
    )
    return EHRRetriever(vectorstore=vs, k=6)
