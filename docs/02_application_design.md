# Module 2 — Application Design & Agent Interface Specifications

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M2: Designing LLM
Applications**.*

---

## 1. The application in one sentence

ClinicalBridge turns a single **RPM alert** into a cited, prioritized **Clinical Context Brief**
by routing it through four specialized LLM agents whose inputs and outputs are strict, typed
contracts (see [`src/clinicalbridge/schemas.py`](../src/clinicalbridge/schemas.py)).

## 2. User personas (simulated)

| Persona | Context | What they need from ClinicalBridge |
|---|---|---|
| **Dr. Aisha Rahman — Primary Care Physician** | Manages a panel of chronic patients; reviews RPM alerts between visits, time-poor. | A 60-second synthesized brief, not raw data: *is this alert real, why, and what should I do?* |
| **Nurse Tom Alvarez — Remote Monitoring Nurse** | First responder to the RPM alert queue; triages dozens of alerts per shift; suffers alert fatigue. | Fast, trustworthy urgency triage + enough context to decide escalate-vs-defer without hunting across systems. |

Both personas share the core need the system optimizes for: **reduced cognitive load and
time-to-decision**, with explicit uncertainty so they know when *not* to trust the machine.

Design implications drawn from the personas:
- Output is a **brief**, front-loaded with urgency and the bottom line (Alert Summary first).
- Every analytical claim is **cited** so a skeptical clinician can verify in seconds.
- Gaps and conflicts are **surfaced, never hidden** — a wrong-but-confident brief is worse than
  an honest "insufficient data."

## 3. System decomposition (why multi-agent)

Clinical reasoning is decomposed the way a care team works — triage nurse → record review →
patient's own account → senior synthesis. Each cognitive role becomes a separately
prompt-engineered, testable agent, which makes iteration measurable: improving triage means
editing one prompt, not a monolith. (Full architecture rationale lives in Module 8's doc; this
module fixes the **interface contracts** between the pieces.)

## 4. Input / output contracts per agent

All contracts are Pydantic models; field-level descriptions in `schemas.py` are the source of
truth and are fed to the LLM as JSON schema (Phase 3).

| Agent | Input | Output | Key safety fields |
|---|---|---|---|
| **Triage** | `RPMAlert` | `TriageDecision` | `urgency`, `requires_immediate_escalation`, `reasoning` (CoT) |
| **EHR Retrieval** | `patient_id` + `TriageDecision.ehr_query` | `EHRContext` | `retrieval_confidence`, `missing_data_flags`, `source_documents` |
| **Anamnesis** | `patient_id` + `TriageDecision.anamnesis_query` | `AnamnesisSummary` | `sensitive_flags`, `missing_data_flags`, per-symptom `source_ref` |
| **Synthesis** | `RPMAlert` + `TriageDecision` + `EHRContext` + `AnamnesisSummary` | `ClinicalContextBrief` | `CitedStatement.sources` on every claim, `uncertainties_and_gaps`, `overall_confidence` |

### Contract data flow

```
RPMAlert
   │
   ▼ (Triage)
TriageDecision ── ehr_query ─────▶ EHRContext ──────┐
   │            └ anamnesis_query ▶ AnamnesisSummary ┤
   │                                                 ▼ (Synthesis)
   └──────────────── original alert ───────────▶ ClinicalContextBrief
```

## 5. Key design decisions encoded in the schema

1. **Provenance everywhere.** `ProblemListEntry`, `MedicationEntry`, `LabResult`,
   `VisitNoteExcerpt`, and `ReportedSymptom` each carry a `source_ref`; `CitedStatement` and
   `RecommendedAction` carry source lists. This makes the Module-8 anti-hallucination rule
   ("every claim cites a source") *structurally enforceable*, not just a prompt request.
2. **Uncertainty is a field, not a footnote.** `missing_data_flags`, `uncertainties_and_gaps`,
   `retrieval_confidence`, and `ConfidenceLevel` give the model a *place* to put doubt, which
   discourages confident hallucination.
3. **Controlled vocabularies.** Enums (`UrgencyLevel`, `AdherenceStatus`, `TrendDirection`,
   `ConfidenceLevel`) prevent free-text drift and make evaluation (Module 5) exact-match scorable.
4. **Colloquial-vs-clinical split.** `ReportedSymptom` keeps both `patient_words` and
   `clinical_interpretation`, preserving the patient's voice while enabling clinical reasoning.
5. **Safety is first-class.** `requires_immediate_escalation` lets the orchestrator (Module 8)
   short-circuit Critical alerts; `sensitive_flags` routes mental-health/substance-use content
   to neutral, careful handling.
6. **The CCB renders itself.** `ClinicalContextBrief.render()` produces the clinician-facing
   markdown, separating data (the model) from presentation and giving the demo a stable output.

## 6. Output contract: the Clinical Context Brief

Six fixed sections, matching the project specification:
1. **Alert Summary** (`alert_summary`, `urgency`)
2. **Patient Snapshot** (`patient_snapshot`)
3. **Contextual Analysis** (`contextual_analysis: list[CitedStatement]`)
4. **Risk Assessment** (`risk_assessment: list[CitedStatement]`)
5. **Recommended Actions** (`recommended_actions: list[RecommendedAction]` w/ confidence)
6. **Uncertainties & Gaps** (`uncertainties_and_gaps`) + `overall_confidence`, `cited_sources`

This fixed shape is what lets a clinician scan the brief in under 60 seconds and trust where
each statement came from.
