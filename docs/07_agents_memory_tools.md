# Module 7 — Autonomous Agents with Memory & Tools

*Part of the ClinicalBridge prompt-engineering portfolio. Maps to **M7: Autonomous Agents with
Memory & Tools**. Implemented in [`agents/`](../src/clinicalbridge/agents/),
[`tools.py`](../src/clinicalbridge/tools.py), [`memory.py`](../src/clinicalbridge/memory.py).*

---

## 1. Agents operating within bounded autonomy

Each ClinicalBridge agent is autonomous within a tightly defined boundary: it owns one cognitive
task, reads a typed input, may use specific tools, and must return a validated schema. The boundary
is what makes the autonomy *safe* — an agent cannot wander outside its contract.

| Agent | Autonomy | Boundary (guardrail) |
|---|---|---|
| Triage | Decides urgency + what to retrieve | Alert-only; code forces escalation on Critical and overwrites patient_id |
| EHR Retrieval | Chooses what to extract from retrieved chunks | May use ONLY retrieved excerpts; must cite; flags gaps |
| Anamnesis | Interprets free-text self-report | Grounded in the record; sensitivity guardrails; citations normalized |
| Synthesis (Phase 11) | Correlates all sources | Every claim must cite an upstream source |

## 2. Tools (`tools.py`)

Tools are the bounded capabilities the system may invoke. They fall into two groups.

### Data tools (wrap existing capabilities under named entry points)
- `search_ehr(query, patient_id, k)` — patient-scoped semantic search over the RAG store.
- `load_patient_record(patient_id, source)` — whole-record load of EHR / RPM / anamnesis.

### Deterministic analysis tools (give the system reliable numeric reasoning)
LLMs are weak at arithmetic over long series, so these are pure Python, not prompts:
- `compute_trend(values)` — direction (rising/falling/stable), change, slope, min/max/mean/stdev,
  with a noise tolerance so jitter isn't mistaken for a trend.
- `summarize_vital_series(rpm_record, vital_type)` — stats + trend for one vital.
- `classify_alert_severity(alert)` — a **rule-based severity floor** (e.g. SpO2 < 85 → critical;
  systolic ≥ 200 → critical). Returns a severity the orchestrator uses to **cross-check the LLM
  triage and never under-call it** — defense-in-depth (the model proposes, deterministic rules
  guard).

A registry (`TOOLS`, `register`, `get_tool`, `list_tools`) makes tools discoverable and uniformly
described — the substrate for the orchestrator's tool use in Phase 12.

> **Why two severity opinions?** The Triage Agent reasons holistically but can be swayed; the rule
> tool is rigid but reliable. Combining them (final urgency = max of the two) means a clearly
> dangerous reading can never be silently downgraded. This directly addresses the project's patient-
> safety requirement. Note the complementary design for *weight*: the rule tool intentionally leaves
> a single in-threshold weight reading "informational", while `compute_trend` catches the gradual
> rise — exactly the "Silent Deterioration" case.

## 3. Memory (`memory.py`)

Two complementary memory types, matching the module's conversation / summary / entity taxonomy:

### Working / audit memory — `SessionMemory`
Short-term memory for a single alert run. The orchestrator logs every agent step
(`log(step, summary, data)`), yielding a replayable trace saved to disk — the foundation of the
Module-8 **auditability** requirement. `steps()` exposes the pipeline order; `save()` persists the
trace.

### Entity + summary memory — `PatientMemory`
Persistent, file-backed memory keyed by patient (one JSON per patient under `.memory/`). It records
each interaction (`record_interaction(... urgency, summary, flags)`) so the system gains
**longitudinal awareness across runs** — e.g. "flagged Urgent for the same issue last week". This is
the "track patient-reported information over multiple interactions" capability called for in the
Anamnesis spec. `digest(patient_id)` renders recent history as **summary text that can be injected
into a prompt** (the orchestrator can feed it to the Synthesis Agent for continuity).

## 4. How memory + tools are wired in

- **Tools** are consumed by the agents (EHR agent already uses the retriever; the orchestrator uses
  `classify_alert_severity` as a guardrail and `summarize_vital_series` to ground RPM trends).
- **`SessionMemory`** is created per run by the orchestrator (Phase 12) and populated as each agent
  returns.
- **`PatientMemory`** is updated at the end of a run and can be read at the start of the next, giving
  the multi-agent system a memory that outlives a single alert.

## 5. Tests

[`tests/test_tools.py`](../tests/test_tools.py) verifies the registry and the deterministic tools
(trend directions, severity rules, including the deliberate weight-is-trend-based behavior).
[`tests/test_memory.py`](../tests/test_memory.py) verifies session logging/persistence and that
patient memory survives across instances and renders an injectable digest. All run offline.
