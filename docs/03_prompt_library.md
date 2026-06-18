# Module 3 — Prompt Library & Output Schemas

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M3: Prompt Content & Assembling
the Prompt**. Prompts live in [`src/clinicalbridge/prompts/library/`](../src/clinicalbridge/prompts/library/);
the version history is described in [`prompt_iteration_log.md`](prompt_iteration_log.md).*

---

## 1. Prompts as versioned, reviewable artifacts

Every agent's system prompt is a plain-text file named `<agent>/<name>.v<N>.txt`. The loader
([`prompts/__init__.py`](../src/clinicalbridge/prompts/__init__.py)) returns the **latest** version
by default, so improving a prompt is as simple as adding a `vN+1` file — no code change. Versions are
never deleted, so the full history is diffable like source code.

| Prompt | Latest | Role |
|---|---|---|
| `triage/system` | v1 | classify urgency, formulate retrieval queries |
| `ehr/system` | v1 | extract cited EHR context (analyst, not diagnostician) |
| `anamnesis/system` | **v2** | interpret self-report; sensitivity scoping tightened |
| `synthesis/system` | **v2** | build the cited 6-section brief; trend-escalation added |

## 2. Prompt-design techniques demonstrated

- **Role & persona** — each prompt opens by fixing the agent's role and its boundary ("you are a
  triage assistant, NOT a diagnostician").
- **Few-shot examples** — the triage prompt maps three alert patterns → triage judgments.
- **Chain-of-thought in structured fields** — reasoning is captured in typed fields (`reasoning`,
  per-symptom `clinical_interpretation`) rather than free prose, keeping it auditable.
- **Structured output** — every agent returns a Pydantic schema via `with_structured_output`; the
  schema field descriptions (Module 2) are themselves part of the prompt.
- **$-templating** — prompts use `string.Template` so literal JSON braces never collide with
  variable substitution.
- **Guardrail instructions** — anti-hallucination ("cite only ALLOWED SOURCES"), uncertainty
  ("flag missing data, don't guess"), and safety ("never accuse the patient") are explicit.

## 3. Output schemas

The structured-output contracts are defined once in
[`schemas.py`](../src/clinicalbridge/schemas.py) and reused by every agent: `TriageDecision`,
`EHRContext`, `AnamnesisSummary`, and the 6-section `ClinicalContextBrief`. Controlled-vocabulary
enums (`UrgencyLevel`, `AdherenceStatus`, `ConfidenceLevel`, `TrendDirection`) keep outputs
exact-match scorable for evaluation.

## 4. The Clinical Context Brief template

The CCB is the product the clinician reads. Its fixed six-section shape (Alert Summary, Patient
Snapshot, Contextual Analysis, Risk Assessment, Recommended Actions, Uncertainties & Gaps) is
enforced by the schema and rendered by `ClinicalContextBrief.render()` — separating data from
presentation so the same object can be evaluated, serialized, and displayed.

## 5. Iteration

Prompt design here is iterative and evidence-driven: v1 prompts established a baseline, the Module-5
evaluation exposed specific weaknesses, and v2 prompts target them. The full before/after analysis —
rationale, diffs, and measured impact — is in [`prompt_iteration_log.md`](prompt_iteration_log.md).
