# Module 6 — Advanced Techniques with LangChain: the EHR RAG Pipeline

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M6: Advanced Techniques with
LangChain**. Implemented in [`src/clinicalbridge/rag/`](../src/clinicalbridge/rag/).*

---

## 1. Why RAG for the EHR

A patient's longitudinal EHR is far larger than what should be stuffed into a prompt, and most of
it is irrelevant to any single alert. Retrieval-Augmented Generation lets the EHR Retrieval Agent
(Phase 8) pull only the chunks relevant to the triage query, keeping the context tight, grounded,
and citable. This directly counters two LLM failure modes from Module 1: **context dilution** and
**hallucination** (the model can only cite what was retrieved).

## 2. Chunking strategy

Clinical records are *semi-structured*, so naive fixed-size character chunking would split a lab
value from its name or merge unrelated facts. Instead we chunk along **clinically meaningful
units** ([`ingest.ehr_to_documents`](../src/clinicalbridge/rag/ingest.py)):

| Unit | One chunk per… | Example `source_ref` |
|---|---|---|
| Problem | diagnosis | `EHR:PT-001/problem_list` |
| Medication | drug | `EHR:PT-001/medications` |
| Lab | result (preserves trend points) | `EHR:PT-001/labs` |
| Visit note | note | `EHR:PT-001/visit_note(2026-03-15)` |
| Allergies | record (incl. "no known allergies") | `EHR:PT-001/allergies` |
| Record status | sparse-record flag | `EHR:PT-004/record_status` |

Each chunk **begins with a patient header** (`Patient Harold Whitfield (PT-001, 68M).`) so the
embedding carries identity, and every chunk stores metadata: `patient_id`, `section`,
`source_ref`, `date`. The 12-patient corpus produces **91 chunks**.

Two deliberate touches:
- A synthetic *"no known drug allergies recorded"* chunk so the retriever can represent **absence**
  of data, not just presence.
- A *record-status* chunk for sparse patients (PT-004) so the system can **retrieve the fact that
  data is missing** — essential for the "Incomplete Record" scenario.

## 3. Embeddings: local, not OpenRouter

OpenRouter serves chat models only — it has **no embeddings endpoint**. So embeddings run locally
with `sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface`
([`ingest.get_embeddings`](../src/clinicalbridge/rag/ingest.py)). Benefits: free, offline after a
one-time ~80 MB download, deterministic, and nothing leaves the machine. The model is cached in
‑process so repeated calls don't reload it.

## 4. Vector store: persistent Chroma

[`build_vectorstore`](../src/clinicalbridge/rag/ingest.py) embeds the chunks and persists a Chroma
collection (`ehr_records`) to `.chroma/`. Rebuilds reset the directory to avoid stale duplicates.

## 5. Retrieval with hard patient filtering

[`EHRRetriever`](../src/clinicalbridge/rag/retriever.py) layers a **metadata filter
(`patient_id`)** on top of semantic similarity, so one patient's record can never leak into
another's context — a safety property as much as a relevance one. `search()` returns the top-k
relevant `Document`s; `search_with_scores()` exposes distances for debugging/evaluation.

## 6. Verified retrieval quality

`python scripts/build_vectorstore.py --check` runs sample queries. Observed results (top-3,
patient-scoped):

- *"blood pressure medication and recent BP control"* (PT-001) → visit note, **Lisinopril**
  medication, hypertension problem.
- *"heart failure, fluid retention, diuretic, weight"* (PT-003) → cardiology note, **HFrEF**
  problem.
- *"warfarin anticoagulation INR levels"* (PT-005) → anticoag note, **warfarin** med, **INR** lab.
- *"is the medical record complete?"* (PT-004) → the **record-status** (sparse) chunk first.

Automated coverage in [`tests/test_rag.py`](../tests/test_rag.py): chunk/metadata correctness and
patient-filtered isolation run offline with a deterministic fake embedding; a real-embedding
semantic-quality test is opt-in via `CB_RUN_RAG_TESTS=1` (keeps the default suite fast).

## 7. How Phase 8 builds on this

The EHR Retrieval Agent will issue the Triage Agent's `ehr_query.focus_terms` against this
retriever, then ask the LLM to extract a structured `EHRContext` **only from the retrieved chunks**,
citing each `source_ref` and flagging anything missing — turning raw retrieval into grounded,
citable clinical context.
