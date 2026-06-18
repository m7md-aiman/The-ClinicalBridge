# Module 8 — Multi-Agent System: the Orchestrator

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M8: Multi-Agent System**.
Implemented in [`src/clinicalbridge/orchestrator.py`](../src/clinicalbridge/orchestrator.py).*

---

## 1. Coordinating the agents (linear-then-convergent)

The orchestrator turns four independent agents into one system. It performs **no clinical
reasoning** itself — it routes, parallelizes, guards, and audits.

```
RPMAlert
   │  classify_alert_severity()  ← deterministic safety floor
   ▼
Triage Agent ──TriageDecision──┬───────────────┐   (parallel, ThreadPoolExecutor)
                               ▼               ▼
                      EHR Retrieval Agent   Anamnesis Agent
                          EHRContext         AnamnesisSummary
                               └───────┬───────┘
                                       ▼  (+ RPM trend note, + memory digest)
                                Synthesis Agent
                                       ▼
                          ClinicalContextBrief  (urgency floored, escalation flagged)
```

The two retrieval agents are **independent and network-bound**, so they run concurrently in a thread
pool — the parallel half of "linear-then-convergent". Triage must finish first (it decides *what* to
retrieve); synthesis runs last (it needs everything).

## 2. Inter-agent communication

Agents never exchange free text — they pass **typed Pydantic objects** (`TriageDecision` →
`EHRContext`/`AnamnesisSummary` → `ClinicalContextBrief`). The orchestrator owns the wiring:
`run_from_triage(triage)` hands each retrieval agent exactly the query and patient id it needs, and
synthesis receives all four upstream artifacts plus a computed RPM-trend note and (optionally) a
prior-interaction memory digest.

## 3. Clinical safety guardrails

| Guardrail | Mechanism |
|---|---|
| **Deterministic severity floor** | `classify_alert_severity()` computes a rule-based severity; the final urgency is `max(LLM urgency, rule floor)`. A dangerous reading can never be silently downgraded by the model — verified by a test where a Routine LLM verdict on SpO2 83% is forced to **Critical**. |
| **Escalate without waiting** | If the effective urgency is Critical (or triage demands it), an `escalation` event is logged **before** retrieval/synthesis — the human alert doesn't wait for the full brief. |
| **Identity & metadata integrity** | Agents overwrite `patient_id` and `generated_at` in code, never trusting model-supplied values. |
| **Anti-hallucination at the boundary** | Synthesis may cite only an explicit ALLOWED SOURCES list; the end-to-end test asserts the final brief contains zero out-of-allowlist citations. |

## 4. Error handling & fallback strategies

Every agent call is wrapped by `_guard()`. On failure the pipeline **degrades gracefully** instead
of crashing:

- **Triage fails** → a deterministic fallback `TriageDecision` built from the severity rules.
- **EHR/Anamnesis fails** → an empty context carrying a `missing_data_flags` note (the brief will
  honestly reflect the gap).
- **Synthesis fails** → a minimal fallback brief (urgency = the safety floor, confidence = Low,
  uncertainties listing the failure).

Each failure is recorded in `OrchestrationResult.errors` and the session log, so degraded runs are
visible, not silent. Tests confirm a synthesis failure still yields a usable (flagged) brief and an
EHR failure still completes the pipeline.

## 5. Auditability

A `SessionMemory` trace records every step — `alert_received`, `severity_floor`, `triage`,
`escalation`, `ehr_retrieval`, `anamnesis`, `synthesis`, `complete` — with timestamps and summaries.
`OrchestrationResult.to_dict()` serializes the whole run (intermediate agent outputs + brief +
session trace) to JSON for inspection, the demo, and evaluation. Optional `PatientMemory` records
each run so the next alert for the same patient can carry forward context.

## 6. Verified end-to-end

The live test runs the real four-agent pipeline on the "Missed Medication" scenario: triage →
parallel EHR+anamnesis → synthesis. It asserts the session contains all stages, the final brief
connects *cough → stopped lisinopril → high BP*, and **every citation is an allowed source**
(including the orchestrator-supplied `RPM trend`). Offline tests cover routing, the severity-floor
escalation, parallel dispatch, graceful fallback for each agent, and JSON serialization.
