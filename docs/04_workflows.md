# Module 4 — Conversational Agency & LLM Workflows

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M4: Conversational Agency &
LLM Workflows**.*

---

## 1. The inter-agent workflow (linear-then-convergent)

ClinicalBridge is not one conversation — it is a *workflow* of specialized turns whose outputs feed
each other. Information flows through typed contracts, not free text, which is what makes the
"conversation" between agents reliable.

```
            ┌──────────────┐
 RPMAlert ─▶│ Triage Agent │── TriageDecision ───┐
            └──────────────┘   (urgency,         │
                                clinical_question,│
                                ehr_query,        │
                                anamnesis_query)  │
                         ┌─────────────┴─────────────┐   (parallel)
                         ▼                           ▼
                 ┌───────────────┐          ┌──────────────────┐
                 │ EHR Retrieval │          │ Anamnesis Agent  │
                 │   (RAG)       │          │ (self-report)    │
                 └──────┬────────┘          └─────────┬────────┘
                  EHRContext                   AnamnesisSummary
                         └───────────┬───────────────┘
                                     ▼
                            ┌──────────────────┐
                            │ Synthesis Agent  │── ClinicalContextBrief
                            └──────────────────┘
```

The **Triage Agent's output is the routing instruction** for everything downstream: its
`clinical_question` focuses both retrievers, and its `ehr_query` / `anamnesis_query` tell each agent
*what to look for*. This is the conversational hand-off — each agent receives a precise brief, not a
vague dump. (The orchestrator that actually drives this flow, including running the two retrieval
agents in parallel, is built in Phase 12 / Module 8.)

## 2. The Anamnesis Agent as a patient-interview interpreter

The Anamnesis Agent simulates the interpretive work a clinician does when reading a patient's
intake: it turns conversational self-report into clinical meaning. Its workflow
([`agents/anamnesis.py`](../src/clinicalbridge/agents/anamnesis.py)):

1. **Load** the patient's anamnesis record and render it as labeled, source-tagged sections
   (chief complaint, HPI, ROS, social/family history, adherence log, symptom diary, concerns).
2. **Interpret colloquial → clinical**, keeping *both* representations per symptom:
   - `patient_words`: verbatim, e.g. *"an annoying dry tickle in my throat"*
   - `clinical_interpretation`: e.g. *"persistent dry cough, possibly ACE-inhibitor related"*
   This dual capture preserves the patient's voice (so a clinician can hear them) while enabling
   downstream reasoning.
3. **Assess adherence** into a controlled status + a free-text detail.
4. **Apply sensitivity guardrails** for mental-health / substance-use content (summarize neutrally,
   flag via `sensitive_flags`, never moralize).

Verified live: for PT-001 the agent produced `patient_words="an annoying dry tickle in my throat"`
→ `clinical_interpretation="persistent dry cough"`, adherence = **Partial** with detail *"stopped
lisinopril ~2 weeks ago due to a dry cough; continues atorvastatin"* — exactly the interpretive
bridge the system needs.

## 3. Chain-of-thought designs

Rather than free-floating "think step by step", reasoning is captured in **structured fields**, so
it is both elicited and inspectable:

| Agent | Chain-of-thought mechanism |
|---|---|
| Triage | A `reasoning` field whose prompt prescribes 4 explicit steps (value vs threshold vs baseline → single/sustained → danger signals → conclude urgency). |
| EHR Retrieval | Reasoning is *constrained to grounding*: extract-and-cite only from retrieved excerpts; flag gaps. |
| Anamnesis | Per-symptom reasoning splits observation (`patient_words`) from inference (`clinical_interpretation`). |
| Synthesis (Phase 11) | A differential-style reasoning chain that correlates all three sources, with every claim cited (`CitedStatement.sources`). |

Putting chain-of-thought into typed fields is a deliberate workflow choice: it keeps the "thinking"
auditable and prevents it from leaking into or polluting the final structured output.

## 4. Why typed hand-offs beat free-text conversation

A naive multi-agent design passes prose between agents and hopes the next one parses it. ClinicalBridge
instead passes **Pydantic objects**: `TriageDecision`, `EHRContext`, `AnamnesisSummary`. Benefits:

- **Determinism of routing** — the EHR agent always knows the patient id and focus terms; nothing is
  lost in translation.
- **Independent testability** — each turn can be evaluated in isolation against its contract.
- **Traceability** — provenance (`source_ref`) survives every hop, enabling the cited final brief.
