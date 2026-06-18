# Prompt Iteration Log

*The evidence-driven record of how ClinicalBridge's prompts (and one guardrail) evolved from a
baseline to a fully-passing system. Maps to **M3** (prompt iteration) and informed by **M5**
(evaluation) and **M8** (guardrails). Each entry: what changed, why, and the measured impact.*

---

## Headline: the before → after

All five scenarios run end-to-end through the multi-agent pipeline, scored against gold rubrics
(`python scripts/run_eval.py`). Model: `openai/gpt-4o-mini`.

| metric | v1 baseline | v2 prompts | v2 + trend guardrail |
|---|---|---|---|
| pass_rate | 0.60 | 0.80 | **1.00** |
| urgency_accuracy | 0.80 | 0.80 | **1.00** |
| mean must-include coverage | 0.62 | 0.82 | **0.87** |
| mean citation coverage | 1.00 | 1.00 | **1.00** |
| total hallucinated citations | 0 | 0 | **0** |
| total must-avoid violations | 0 | 0 | **0** |
| mean latency (s) | 23.2 | 25.5 | **18.9** |

The safety properties (no hallucinations, no accusatory language, full citation coverage) held at
every step — improvements never came at the cost of safety.

---

## Iteration 1 — Synthesis prompt v1 → v2

**Trigger (from the baseline run).** `silent_deterioration` was classified **Routine** when the gold
standard is **Urgent**, and several briefs scored low on must-include coverage because the model used
synonyms ("discontinued" for "stopped", "leafy greens" for "salad").

**Failure analysis.** Two distinct causes:
1. The synthesis prompt weighed the raw number over the *trend*: a gradual weight gain whose
   individual readings stayed within threshold was treated as low-urgency, even with corroborating
   symptoms (edema, orthopnea).
2. The prompt did not push the model to name specific clinical entities, so concept terms were
   present in spirit but not in words.

**Change (`synthesis/system.v2.txt`).** Added two sections:
- **URGENCY CALIBRATION** — explicit rule: escalate to Urgent when a serious chronic condition + a
  sustained worsening trend + corroborating self-report co-occur, *even if no single reading crossed
  a threshold*; and conversely, don't over-escalate an isolated, well-explained reading.
- **BE CONCRETE — NAME ENTITIES EXPLICITLY** — name medications, the actual dietary/lifestyle item,
  and the specific lab/value.

**Measured impact.** must-include coverage 0.62 → 0.82; pass_rate 0.60 → 0.80. **But the urgency
under-call persisted** — `gpt-4o-mini` still returned Routine for the weight trend despite the
explicit instruction. (Lesson below.)

---

## Iteration 2 — Anamnesis prompt v1 → v2

**Trigger (observed in Phase 9).** For PT-001 (no mental-health content) the agent put an ordinary
cough worry into `sensitive_flags`, over-scoping a channel reserved for sensitive disclosures.

**Change (`anamnesis/system.v2.txt`).** Scoped `sensitive_flags` precisely to mental-health /
psychological / substance-use content; routed ordinary medical worries to `patient_concerns`; and
asked the agent to name specific lifestyle items (supporting concept coverage downstream).

**Measured impact.** Cleaner separation of concerns; PT-012 (anxiety) still correctly flags, PT-001
no longer mis-flags. No regression in other metrics.

---

## Iteration 3 — Evaluation refinement: concept matching

**Trigger.** The baseline "missing terms" were mostly synonyms the brief *did* express. Strict
literal matching was under-counting correct content.

**Change (`evaluation/metrics.py`).** `must_include` / `must_flag` now use **synonym groups**
(`"stopped|discontinu|non-adher"`) matched as substrings — concept matching. Crucially, `must_avoid`
still uses **whole-word** matching, so the forbidden "lying" never matches "imp-lying" (the Phase-5
bug). The rubrics were rewritten as concept groups.

**Measured impact.** Coverage scores now reflect concepts rather than exact words; combined with
Iteration 1 this lifted mean coverage to 0.82 (then 0.87 after Iteration 4).

---

## Iteration 4 — Deterministic trend guardrail (the key lesson)

**Trigger.** After Iterations 1–3, `silent_deterioration` *still* under-called urgency (Routine). The
prompt instruction alone could not make `gpt-4o-mini` reliably escalate the heart-failure weight
trend.

**Decision.** A patient-safety rule should **not depend on the LLM**. Rapid weight gain (~≥2.5 kg
over the monitoring window) is a standard heart-failure decompensation red flag, so it belongs in the
deterministic guardrail layer. Added `Orchestrator._trend_severity_floor()`: a rising weight series
with net gain ≥ 2.5 kg raises the severity floor to **Urgent**, and the final urgency is
`max(LLM, floor)`.

**Measured impact.** `silent_deterioration` → **Urgent** (coverage also rose to 1.0); urgency_accuracy
0.80 → **1.00**; pass_rate 0.80 → **1.00**. Only this scenario was affected — stable-weight HF
patients (PT-011) are not falsely escalated, and non-weight alerts are untouched (verified by test).

**The broader lesson (a portfolio takeaway).** Prompt engineering is powerful for reasoning, tone,
and structure, but for crisp, safety-critical thresholds a deterministic rule is more reliable than
coaxing the model. The mature design uses each where it is strongest: the LLM synthesizes and
explains; deterministic guardrails enforce hard safety floors.

---

## Residual gaps (honest accounting)

- `false_alarm` and `conflicting_data` sit at 0.667 must-include coverage (still PASS): the model
  occasionally phrases a concept outside even the synonym group (e.g. "one reading" without the
  word, or "vitamin K" via "leafy greens" already covered). These are minor wording variations, not
  reasoning failures, and do not affect safety metrics.
- Urgency for the trend case is enforced by a rule, not learned by the model — a deliberate trade-off
  documented above and in `docs/ethics_and_limitations.md`.

## How to reproduce

```
python scripts/run_eval.py        # prints the dashboard, writes eval/results/evaluation.json
```
Prompt versions are selectable in code (`Agent(prompt_version=1)`) to A/B test v1 vs v2.
