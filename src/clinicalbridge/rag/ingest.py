"""EHR ingestion for retrieval-augmented generation (Module 6).

Chunking strategy
-----------------
Clinical EHR documents are semi-structured, so instead of naive fixed-size character chunking we
split along **clinically meaningful units**: one chunk per problem, per medication, per lab result,
per visit note, and one for allergies. Every chunk:

- begins with a short patient header (name, id, age/sex) so the embedding carries identity context;
- carries metadata: ``patient_id`` (for hard filtering), ``section``, and a ``source_ref`` that
  matches the citation convention used elsewhere (e.g. ``EHR:PT-001/medications``) so downstream
  agents can cite precisely.

Embeddings run **locally** via sentence-transformers (OpenRouter has no embeddings endpoint), and
the vectors are persisted to a Chroma store on disk.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from clinicalbridge.config import settings

COLLECTION = "ehr_records"

# Cache the (heavy) embedding model so repeated calls in one process don't reload it.
_embeddings_cache = None


def get_embeddings():
    """Return the local HuggingFace embedding model (downloads once, then cached on disk)."""
    global _embeddings_cache
    if _embeddings_cache is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _embeddings_cache = HuggingFaceEmbeddings(model_name=settings.embedding_model)
    return _embeddings_cache


def _header(ehr: dict) -> str:
    sex = (ehr.get("sex") or "")[:1].upper()
    return f"Patient {ehr['name']} ({ehr['patient_id']}, {ehr.get('age', '?')}{sex})."


def ehr_to_documents(ehr: dict) -> list[Document]:
    """Turn one patient's EHR dict into a list of retrievable, citable chunks."""
    pid = ehr["patient_id"]
    name = ehr["name"]
    hdr = _header(ehr)

    def meta(section: str, source_ref: str, index: int = 0, date: str = "") -> dict:
        # Chroma metadata must be primitive and non-null.
        return {
            "patient_id": pid, "patient_name": name, "section": section,
            "source_ref": source_ref, "item_index": index, "date": date or "",
        }

    docs: list[Document] = []

    for i, p in enumerate(ehr.get("problem_list", [])):
        text = (f"{hdr} Problem/diagnosis: {p['condition']} (ICD-10 {p.get('icd10', 'n/a')}), "
                f"status {p.get('status', 'unknown')}, onset {p.get('onset_date', 'unknown')}.")
        docs.append(Document(page_content=text, metadata=meta("problem_list", f"EHR:{pid}/problem_list", i)))

    for i, m in enumerate(ehr.get("medications", [])):
        text = (f"{hdr} Medication: {m['name']} {m.get('dose', '')} {m.get('frequency', '')}, "
                f"status {m.get('status', 'unknown')}, started {m.get('started', 'unknown')}.")
        docs.append(Document(page_content=text, metadata=meta("medications", f"EHR:{pid}/medications", i)))

    for i, l in enumerate(ehr.get("lab_results", [])):
        text = (f"{hdr} Lab result: {l['test']} = {l['value']} {l.get('unit', '')} "
                f"(reference {l.get('reference_range', 'n/a')}) on {l.get('date', 'unknown')}; "
                f"flag {l.get('flag', 'n/a')}.")
        docs.append(Document(page_content=text,
                             metadata=meta("labs", f"EHR:{pid}/labs", i, l.get("date", ""))))

    for i, n in enumerate(ehr.get("visit_notes", [])):
        date = n.get("date", "")
        text = (f"{hdr} Visit note ({date or 'undated'}, {n.get('specialty', '')}, "
                f"{n.get('author', '')}): {n['note']}")
        docs.append(Document(page_content=text,
                             metadata=meta("visit_note", f"EHR:{pid}/visit_note({date})", i, date)))

    allergies = ehr.get("allergies", [])
    if allergies:
        listed = "; ".join(f"{a['substance']} (reaction: {a.get('reaction', '')}, "
                           f"severity: {a.get('severity', '')})" for a in allergies)
        text = f"{hdr} Allergies: {listed}."
    else:
        text = f"{hdr} Allergies: no known drug allergies recorded."
    docs.append(Document(page_content=text, metadata=meta("allergies", f"EHR:{pid}/allergies")))

    if ehr.get("record_completeness") == "sparse":
        text = (f"{hdr} RECORD STATUS: This EHR is sparse/incomplete. Outside records were requested "
                f"but not yet received; medication list and laboratory results are unavailable in the "
                f"system.")
        docs.append(Document(page_content=text, metadata=meta("record_status", f"EHR:{pid}/record_status")))

    return docs


def load_ehr_documents(ehr_dir: Path | None = None) -> list[Document]:
    """Load and chunk every EHR JSON file in ``ehr_dir``."""
    directory = Path(ehr_dir or settings.ehr_dir)
    docs: list[Document] = []
    for path in sorted(directory.glob("*.json")):
        ehr = json.loads(path.read_text(encoding="utf-8"))
        docs.extend(ehr_to_documents(ehr))
    return docs


def build_vectorstore(
    *,
    persist_dir: Path | None = None,
    ehr_dir: Path | None = None,
    embeddings=None,
    reset: bool = True,
) -> Chroma:
    """Chunk the EHR corpus, embed it, and persist a Chroma collection. Returns the store."""
    persist = Path(persist_dir or settings.chroma_dir)
    if reset and persist.exists():
        shutil.rmtree(persist)
    persist.mkdir(parents=True, exist_ok=True)

    docs = load_ehr_documents(ehr_dir)
    emb = embeddings or get_embeddings()
    return Chroma.from_documents(
        documents=docs, embedding=emb,
        collection_name=COLLECTION, persist_directory=str(persist),
    )
