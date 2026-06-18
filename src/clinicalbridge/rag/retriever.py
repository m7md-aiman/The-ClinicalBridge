"""Retrieval interface over the persisted EHR Chroma store (Module 6).

The retriever supports **hard patient filtering** (so one patient's record never leaks into
another's context) layered on top of semantic similarity search.
"""

from __future__ import annotations

from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from clinicalbridge.config import settings
from clinicalbridge.rag.ingest import COLLECTION, get_embeddings


def load_vectorstore(*, persist_dir: Path | None = None, embeddings=None) -> Chroma:
    """Open the existing persisted Chroma collection for querying."""
    persist = Path(persist_dir or settings.chroma_dir)
    if not persist.exists():
        raise FileNotFoundError(
            f"No vector store at {persist}. Build it first: python scripts/build_vectorstore.py"
        )
    emb = embeddings or get_embeddings()
    return Chroma(collection_name=COLLECTION, embedding_function=emb, persist_directory=str(persist))


class EHRRetriever:
    """Semantic search over EHR chunks, optionally scoped to a single patient."""

    def __init__(self, vectorstore: Chroma | None = None, *, k: int = 6) -> None:
        self.vs = vectorstore or load_vectorstore()
        self.k = k

    def search(self, query: str, *, patient_id: str | None = None, k: int | None = None) -> list[Document]:
        flt = {"patient_id": patient_id} if patient_id else None
        return self.vs.similarity_search(query, k=k or self.k, filter=flt)

    def search_with_scores(
        self, query: str, *, patient_id: str | None = None, k: int | None = None
    ) -> list[tuple[Document, float]]:
        flt = {"patient_id": patient_id} if patient_id else None
        return self.vs.similarity_search_with_score(query, k=k or self.k, filter=flt)
