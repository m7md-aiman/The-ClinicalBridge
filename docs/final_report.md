# ClinicalBridge — Final Report

*COP-3442 Prompt Engineering · Capstone: Bridging the Clinical Context Gap*

---

## 1. Executive summary

ClinicalBridge is a multi-agent, LLM-powered clinical decision-support prototype that synthesizes
three fragmented data sources — **EHR** (the past), **RPM** (the present), and **Anamnesis** (the
patient's voice) — into a single, cited **Clinical Context Brief** a clinician can read in under 60
seconds.

Four specialized agents (Triage, EHR Retrieval, Anamnesis, Synthesis) are coordinated by an
Orchestrator in a linear-then-convergent flow: triage classifies urgency and decides what to
retrieve; the EHR (RAG) and Anamnesis agents gather context in parallel; synthesis fuses everything
into the brief. The system is **grounded by construction** — every analytical claim must cite an
allowed upstream source — and **safe by layering** — deterministic guardrails enforce urgency floors
the LLM cannot be trusted to apply on its own.

**Headline results** (all 5 gold scenarios, end-to-end):

| Pass rate | Urgency accuracy | Hallucinated citations | Citation coverage | Mean latency |
|---|---|---|---|---|
| **100%** | **100%** | **0** | **100%** | **~19–27 s** |

The project is delivered as (1) a tested prototype (**95+ automated tests**), (2) a written
prompt-engineering portfolio mapping to all eight modules, and (3) a polished showcase **website**.

## 2. Module-to-capstone mapping (evidence)

| Module | Application in ClinicalBridge | Primary artifacts |
|---|---|---|
| **M1 — Intro to LLMs & PE** | Model selection (OpenRouter, per-agent), local embeddings rationale, baseline framing | [`docs/01_model_selection.md`](01_model_selection.md), [`llm.py`](../src/clinicalbridge/llm.py) |
| **M2 — Designing LLM Apps** | Architecture, personas, typed input/output contracts per agent | [`docs/02_application_design.md`](02_application_design.md), [`schemas.py`](../src/clinicalbridge/schemas.py) |
| **M3 — Prompt Content & Assembly** | System prompts, few-shot, structured output, **versioned prompt library + iteration log** | [`docs/03_prompt_library.md`](03_prompt_library.md), [`docs/prompt_iteration_log.md`](prompt_iteration_log.md), [`prompts/library/`](../src/clinicalbridge/prompts/library/) |
| **M4 — Conversational Agency & Workflows** | Inter-agent workflow, anamnesis interpretation, chain-of-thought in typed fields | [`docs/04_workflows.md`](04_workflows.md), [`agents/`](../src/clinicalbridge/agents/) |
| **M5 — Testing LLM Apps** | Evaluation framework, metrics, gold rubrics, regression scenarios | [`docs/05_testing.md`](05_testing.md), [`evaluation/`](../src/clinicalbridge/evaluation/), [`docs/evaluation_results.md`](evaluation_results.md) |
| **M6 — Advanced Techniques (LangChain)** | RAG: chunking, local embeddings, Chroma, structured output | [`docs/06_langchain_rag.md`](06_langchain_rag.md), [`rag/`](../src/clinicalbridge/rag/) |
| **M7 — Autonomous Agents w/ Memory & Tools** | Bounded agents, tool registry, session + entity memory | [`docs/07_agents_memory_tools.md`](07_agents_memory_tools.md), [`tools.py`](../src/clinicalbridge/tools.py), [`memory.py`](../src/clinicalbridge/memory.py) |
| **M8 — Multi-Agent System** | Orchestration, parallel dispatch, escalation, guardrails, audit log, anti-hallucination | [`docs/08_multiagent.md`](08_multiagent.md), [`orchestrator.py`](../src/clinicalbridge/orchestrator.py) |

## 3. The prompt-engineering story (what was learned)

The most valuable arc of the project is documented in
[`prompt_iteration_log.md`](prompt_iteration_log.md): a baseline run scored 0.60 pass rate and
revealed two issues — a heart-failure trend being **under-triaged**, and gold rubrics being too
literal. Prompt v2 (escalation guidance + explicit entity naming) and concept-based rubrics lifted
coverage and pass rate to 0.80, **but the urgency under-call persisted** — the model would not
reliably escalate the trend from a prompt instruction. The fix was architectural: a **deterministic
weight-trend guardrail** in the orchestrator. Final: **1.00 pass rate, 1.00 urgency accuracy**, with
safety metrics perfect throughout.

> **Lesson:** prompt engineering excels at reasoning, tone, and structure; safety-critical thresholds
> belong in deterministic rules. A mature system uses each where it is strongest.

Other engineering decisions that paid off: **provenance baked into the schemas** (so citation
discipline is enforceable, not just requested), **code-level guardrails over model output** (patient
id, `generated_at`, escalation, citation normalization), and a **versioned prompt loader** that let
agents adopt v2 prompts with zero code change.

## 4. Deliverables

- **Runnable prototype** — `python scripts/run_demo.py <scenario>` produces a cited brief; full
  pipeline orchestrated in [`orchestrator.py`](../src/clinicalbridge/orchestrator.py).
- **Simulated dataset** — 12 patients (EHR/RPM/anamnesis) + 5 gold scenarios, deterministic.
- **Evaluation** — `python scripts/run_eval.py` → dashboard + `eval/results/evaluation.json`.
- **Portfolio** — `docs/01…08` + iteration log + results + this report + ethics doc.
- **Showcase website** — `web/` (see [`web/README.md`](../web/README.md)).
- **Tests** — `pytest -q` (offline + live-skipping); 95+ tests.

## 5. How to run (quick start)

```bash
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python scripts/generate_dataset.py
.venv/Scripts/python scripts/build_vectorstore.py
# add OPENROUTER_API_KEY to .env, then:
.venv/Scripts/python scripts/run_demo.py missed_medication --compare
.venv/Scripts/python scripts/run_eval.py
# website:
npm --prefix web/frontend install && npm --prefix web/frontend run build
.venv/Scripts/python -m uvicorn web.backend.app:app --port 8000
```

## 6. Closing reflection

The capstone demonstrates that prompt engineering, at its best, is **systems engineering**: the value
came not from any single clever prompt but from the interplay of typed contracts, retrieval,
multi-agent decomposition, evaluation-driven iteration, and deterministic guardrails — all oriented
around a single, high-stakes goal: giving a clinician trustworthy context, fast, without ever
pretending to be more certain than the evidence allows.
