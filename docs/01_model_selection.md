# Module 1 — Model Selection Rationale & Baseline Prompt Experiments

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M1: Intro to LLMs &
Prompt Engineering**.*

---

## 1. Why an LLM fits this problem

The Clinical Context Gap is fundamentally a **language and reasoning problem**, not a data
*availability* problem. The raw data already exists across EHR, RPM, and anamnesis systems; what
is missing is an intelligent intermediary that can (a) retrieve the relevant pieces from each
source, (b) interpret them *in combination*, and (c) express the result as a coherent clinical
narrative. These are exactly the capabilities LLMs provide:

- **Heterogeneous input** — LLMs handle free-text visit notes, numeric RPM trends rendered as
  text, and conversational anamnesis equally well, so one reasoning substrate spans all three
  data formats.
- **Synthesis over retrieval** — the value is in correlating an alert against history and
  self-report, which is generative reasoning, not database lookup.
- **Instruction-following & structure** — modern instruct models reliably emit structured JSON
  under a schema, which lets us build testable, composable agents.

## 2. LLM capabilities and limitations relevant to clinical text

| Capability we rely on | Limitation we must engineer around |
|---|---|
| Strong summarization & synthesis of mixed text | **Hallucination** — may invent plausible clinical facts |
| Few-shot in-context learning (no fine-tuning needed) | **Sycophancy / overconfidence** — may not flag uncertainty |
| Structured (JSON) output following a schema | **Numeric reasoning** on long time-series is weak → we pre-compute trends |
| Instruction-following for role/persona prompts | **Stale/again-general medical knowledge** → must ground every claim in provided data |
| Long context windows for multi-source synthesis | **Context dilution** — too much irrelevant text degrades focus → RAG keeps it tight |

These limitations directly shape the architecture: anti-hallucination guardrails (every claim
cites an upstream source), RAG to keep context relevant, explicit "flag missing data instead of
guessing" instructions, and confidence-calibration prompting.

## 3. Provider & deployment choice: OpenRouter

We call all chat/reasoning models through **OpenRouter**, an OpenAI-compatible API gateway.

**Why OpenRouter**
- *Model flexibility* — a single API key and base URL gives access to many providers
  (OpenAI, Anthropic, Google, Meta, etc.). We can compare models per agent without rewriting code.
- *OpenAI-compatible* — works directly with LangChain's `ChatOpenAI` by setting `base_url`,
  so no custom client is needed.
- *Per-agent model tiering* — cheaper/faster models for narrow tasks (Triage), stronger models
  for open-ended synthesis. Configured in `.env` (`CB_TRIAGE_MODEL`, `CB_SYNTHESIS_MODEL`, …).

**Embeddings caveat & decision** — OpenRouter exposes chat/completion endpoints only, **not**
embeddings. The EHR RAG pipeline therefore uses a **local** embedding model
(`sentence-transformers/all-MiniLM-L6-v2`) via `langchain-huggingface`. Benefits: zero added
cost, fully offline after a one-time ~80 MB download, deterministic vectors, and no patient-like
text leaving the machine — appropriate even though our data is simulated.

## 4. Model selection by agent role

The prototype is model-agnostic; defaults are chosen for a good cost/quality balance and are
overridable in `.env`. Recommended starting points:

| Agent | Task character | Recommended default | Why |
|---|---|---|---|
| Triage | Narrow classification + JSON | small/fast (e.g. `openai/gpt-4o-mini`) | Deterministic, schema-bound, latency-sensitive |
| EHR Retrieval | Grounded extraction over retrieved chunks | small/medium | Must stay faithful to context, not creative |
| Anamnesis | Interpret colloquial language | small/medium | Light reasoning, tone-sensitive |
| Synthesis | Open-ended multi-source reasoning | strongest available (e.g. `anthropic/claude-3.5-sonnet`) | Hardest reasoning; quality matters most here |

Temperature is kept **low (0.1)** system-wide for reproducibility and to reduce hallucination,
a deliberate trade-off favoring reliability over creativity in a high-stakes domain.

## 5. Baseline prompt experiments (to be recorded as the build proceeds)

Module 1 establishes the *baseline* against which later prompt iterations are measured. As each
agent is built (Phases 6–11), its very first prompt ("v1, naive") is captured here and in
`docs/03_prompt_library.md`, then improved. The pattern for each baseline experiment:

1. **Naive prompt** — minimal instruction, no role, no examples, no schema.
2. **Observed failure modes** — e.g. free-text instead of JSON, invented lab values, no
   uncertainty flags.
3. **First structured improvement** — add role, output schema, and one guardrail.
4. **Delta** — qualitative/quantitative change, feeding the Module 5 evaluation.

> Baseline entries are filled in starting at Phase 6 (Triage Agent) and consolidated in the
> Module 3 prompt library and Module 5 testing report.

## 6. Summary

ClinicalBridge uses LLMs as a reasoning intermediary, accessed through OpenRouter for model
flexibility, with local embeddings for RAG. Model choice is per-agent and configurable, defaults
favor reliability (low temperature, schema-bound output), and every known LLM limitation is
mapped to a concrete engineering countermeasure documented in later modules.
