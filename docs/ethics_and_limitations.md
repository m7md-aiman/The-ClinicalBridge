# Ethical Considerations & Limitations

*Part of the ClinicalBridge portfolio (COP-3442 Prompt Engineering capstone).*

---

## Critical disclaimers

- **Not a medical device.** ClinicalBridge is a proof-of-concept for a prompt-engineering course. It
  must not be used for real clinical decisions.
- **All data is fully simulated.** The 12 patients and 5 scenarios are fabricated
  ([`datagen.py`](../src/clinicalbridge/datagen.py), [`scenarios.py`](../src/clinicalbridge/scenarios.py)).
  No real patient data of any kind is used, and the system is not HIPAA-compliant.
- **Clinician-in-the-loop, always.** The system *surfaces context and possibilities*; it never
  diagnoses, prescribes, or acts autonomously. The Synthesis Agent is explicitly instructed not to
  make definitive diagnoses, and Critical alerts are escalated to a human before synthesis completes.

## Ethical design principles (and how they're enforced)

| Principle | How it is realized |
|---|---|
| **Traceability over fluency** | Every analytical claim must cite an allowed upstream source; the evaluator measures hallucinated citations (currently **0**). A confident-but-unsourced brief is treated as a failure. |
| **Honest uncertainty** | `missing_data_flags`, `uncertainties_and_gaps`, and calibrated confidence give the model a place to express doubt instead of inventing facts. |
| **Safety floors that don't depend on the LLM** | A deterministic severity floor and a weight-trend guardrail ensure dangerous readings are never silently under-called, regardless of model behavior. |
| **Non-judgmental handling of conflicts** | When self-report contradicts the record (e.g. PT-005), the system presents the discrepancy neutrally; "must-avoid" terms (lying/accusatory language) are tested to be absent. |
| **Sensitivity** | Mental-health / substance-use disclosures are summarized factually via a scoped `sensitive_flags` channel, never moralized. |
| **Reproducibility** | The dataset is deterministic (fixed seed), so evaluation is repeatable and data-quality vs prompt-quality failures stay distinguishable. |

## Known limitations

1. **LLM dependence and variability.** Outputs depend on the chosen model (default
   `openai/gpt-4o-mini` via OpenRouter). A key lesson (documented in
   [`prompt_iteration_log.md`](prompt_iteration_log.md)) is that a safety-critical urgency rule could
   *not* be made reliable by prompting alone and had to be enforced deterministically.
2. **Small, synthetic evaluation set.** 12 patients / 5 scenarios exercise specific failure modes but
   are not a statistically meaningful sample. Results (100% pass) demonstrate capability on the
   designed cases, not general clinical safety.
3. **Rubric-based scoring, not clinical validation.** Metrics use concept/keyword matching against
   hand-authored gold briefs, not expert clinician review. "Coverage" approximates, but does not
   guarantee, clinical completeness.
4. **Heuristic thresholds.** The weight-trend guardrail (~2.5 kg) and the rule-based severity bands
   are reasonable but simplified; real deployment would need validated, condition-specific rules.
5. **Retrieval scope.** RAG runs over a 12-patient corpus with a small local embedding model
   (`all-MiniLM-L6-v2`); retrieval quality and disambiguation would need revisiting at real scale.
6. **Out of scope (by design).** No real EHR interoperability (HL7/FHIR), no device integration, no
   authentication/authorization, no production hardening, no regulatory validation.
7. **Cost & latency.** Live runs make several LLM calls (~15–30 s, small cost); the showcase website
   mitigates this with bundled cached runs but live runs remain model-bound.

## Responsible-use summary

ClinicalBridge is a teaching artifact that demonstrates how careful prompt engineering, retrieval,
memory, multi-agent orchestration, and **deterministic guardrails** can turn fragmented data into a
cited, uncertainty-aware brief — while making explicit, at every layer, that a human clinician
remains the decision-maker.
