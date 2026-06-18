"""CLI: build (and optionally sanity-check) the EHR vector store.

Usage:
    python scripts/build_vectorstore.py            # build + persist to .chroma/
    python scripts/build_vectorstore.py --check     # build, then run sample retrieval queries

First run downloads the local embedding model (~80 MB), then caches it for offline use.
"""

from __future__ import annotations

import argparse

from clinicalbridge.config import settings
from clinicalbridge.rag.ingest import build_vectorstore, load_ehr_documents
from clinicalbridge.rag.retriever import EHRRetriever

SAMPLE_QUERIES = [
    ("PT-001", "blood pressure medication and recent BP control"),
    ("PT-003", "heart failure, fluid retention, diuretic, weight"),
    ("PT-005", "warfarin anticoagulation INR levels"),
    ("PT-004", "is the medical record complete?"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the EHR vector store.")
    parser.add_argument("--check", action="store_true", help="Run sample retrieval queries after building.")
    args = parser.parse_args()

    docs = load_ehr_documents()
    print(f"[..] Chunked EHR corpus into {len(docs)} documents.")
    print("[..] Building embeddings + Chroma store (first run downloads the model)...")
    build_vectorstore()
    print(f"[OK] Vector store persisted to {settings.chroma_dir}")

    if args.check:
        print("\nRetrieval sanity check")
        print("=" * 72)
        retriever = EHRRetriever(k=3)
        for pid, query in SAMPLE_QUERIES:
            print(f"\n[{pid}] query: {query!r}")
            for doc in retriever.search(query, patient_id=pid):
                snippet = doc.page_content[:110].replace("\n", " ")
                print(f"   - ({doc.metadata['source_ref']}) {snippet}...")


if __name__ == "__main__":
    main()
