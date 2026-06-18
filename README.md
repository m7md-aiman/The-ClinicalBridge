# ClinicalBridge

**Bridging the Clinical Context Gap** — an LLM-powered, multi-agent system that synthesizes
**Electronic Health Records (EHR)**, **Remote Patient Monitoring (RPM)**, and **Anamnesis**
(patient-reported history) into a single, prioritized **Clinical Context Brief (CCB)** that a
clinician can review in under 60 seconds.

> COP-3442 Prompt Engineering — Capstone Project. This is a **proof-of-concept on fully
> simulated data**. It is **not** a medical device and must never be used for real clinical
> decisions. See [`docs/ethics_and_limitations.md`](docs/ethics_and_limitations.md).

### 📂 Key deliverables
- **📘 [Prompt-Engineering Portfolio](docs/PORTFOLIO.md)** — the comprehensive write-up (design,
  prompt iterations, evaluation, safety, anti-hallucination, lessons + appendices). Also a designed
  page on the website at `/portfolio`.
- **🖥️ [Showcase website](web/README.md)** — Overview · Interactive Demo · Evaluation · Portfolio
  (`uvicorn web.backend.app:app` → http://localhost:8000).
- **🧩 Prototype** — `src/clinicalbridge/`; run `python scripts/run_demo.py missed_medication --compare`.

---

## What it does

A simulated RPM alert (e.g. sustained high blood pressure) enters the system and flows through
four specialized, prompt-engineered agents coordinated by an orchestrator:

```
RPM alert ─▶ Triage Agent ─▶ ┌─ EHR Retrieval Agent (RAG over vector store) ─┐
                             └─ Anamnesis Agent (patient-reported history)  ─┴─▶ Synthesis Agent ─▶ Clinical Context Brief
```

The Brief contains: Alert Summary · Patient Snapshot · Contextual Analysis · Risk Assessment ·
Recommended Actions · Uncertainties & Gaps — each claim cited back to a source.

## Architecture at a glance

| Component | Role | Modules |
|---|---|---|
| Alert Triage Agent | Classify urgency, identify patient, formulate retrieval queries | M2, M3, M4 |
| EHR Retrieval Agent | RAG search of longitudinal EHR; flags missing data | M6, M7 |
| Anamnesis Agent | Interpret self-reported symptoms/adherence/lifestyle | M3, M4, M7 |
| Synthesis Agent | Merge all sources into the cited Clinical Context Brief | M4, M6, M8 |
| Orchestrator | Route flow, parallelize retrieval, escalate, audit, guardrails | M7, M8 |

## Tech stack

- **Python 3.11+**, **LangChain** for orchestration
- **OpenRouter** (OpenAI-compatible) for all chat/reasoning — model is configurable per agent
- **ChromaDB** vector store with **local** `sentence-transformers` embeddings
  (OpenRouter has no embeddings endpoint, so retrieval runs offline & free)

---

## Setup (Windows / PowerShell)

This machine has multiple Pythons; use **3.11** via the `py` launcher.

```powershell
# 1. From the project root, create and populate a 3.11 virtual environment
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .

# 2. Configure your OpenRouter key
copy .env.example .env
#   then edit .env and set OPENROUTER_API_KEY=sk-or-...

# 3. Verify the install
.\.venv\Scripts\python -m clinicalbridge.config     # prints resolved settings
.\.venv\Scripts\python -m pytest -q                 # runs the test suite
```

> The embedding model (~80 MB) downloads automatically the first time the RAG pipeline runs
> (Phase 7), then is cached for offline use.

## Project layout

```
data/{ehr,rpm,anamnesis,scenarios}/   simulated dataset (generated)
src/clinicalbridge/
  config.py        central settings (reads .env)
  schemas.py       Pydantic data contracts            (Phase 2)
  llm.py           OpenRouter chat wrapper            (Phase 3)
  prompts/         versioned prompt templates         (Phase 3+)
  rag/             chunk + embed + retrieve EHR        (Phase 7)
  agents/          triage, ehr, anamnesis, synthesis  (Phases 6–11)
  memory.py        agent memory                       (Phase 10)
  tools.py         agent tools                        (Phase 10)
  orchestrator.py  multi-agent coordination           (Phase 12)
scripts/           generate_dataset, build_vectorstore, run_demo
eval/              metrics + scenario tests           (Phase 14)
tests/             unit tests
docs/              prompt-engineering portfolio (01..08 per module + report)
```

## Build status

Built in 16 phases (see [`docs/`](docs/) and the project plan). Currently: **Phase 1 complete —
project scaffold & environment**.

## License / disclaimer

For educational use only. All patient data is fictional and machine-generated.
