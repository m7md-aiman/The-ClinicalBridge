"""Alert Triage Agent.

Input:  an ``RPMAlert``.
Output: a ``TriageDecision`` — urgency classification, the clinical question to resolve, a
        chain-of-thought ``reasoning`` field, and focused retrieval queries for the downstream
        EHR and Anamnesis agents.

Modules exercised: M2 (input/output contract), M3 (system prompt, few-shot, structured output),
M4 (chain-of-thought reasoning).
"""

from __future__ import annotations

from clinicalbridge.agents.base import Agent
from clinicalbridge.llm import generate_structured
from clinicalbridge.schemas import RPMAlert, TriageDecision, UrgencyLevel


def format_alert(alert: RPMAlert) -> str:
    """Render an RPMAlert as the user message for the Triage Agent."""
    unit = alert.reading.unit
    lines = [
        "RPM ALERT",
        f"- alert_id: {alert.alert_id}",
        f"- patient_id: {alert.patient_id}",
        f"- timestamp: {alert.timestamp.isoformat()}",
        f"- device: {alert.device_type}",
        f"- vital: {alert.reading.vital_type.value}",
        f"- measured value: {alert.reading.display()}",
        f"- device alert category: {alert.device_alert_category}",
    ]
    if alert.baseline_value is not None:
        lines.append(f"- patient baseline: {alert.baseline_value:g} {unit}")
    else:
        lines.append("- patient baseline: unknown (no established baseline on file)")
    if alert.thresholds is not None:
        low = "n/a" if alert.thresholds.low is None else f"{alert.thresholds.low:g}"
        high = "n/a" if alert.thresholds.high is None else f"{alert.thresholds.high:g}"
        lines.append(f"- threshold low: {low} {unit}")
        lines.append(f"- threshold high: {high} {unit}")
    if alert.notes:
        lines.append(f"- device notes: {alert.notes}")
    lines.append("\nClassify this alert, state the clinical question, and formulate retrieval queries.")
    return "\n".join(lines)


class TriageAgent(Agent):
    role = "triage"
    prompt_id = "triage/system"

    def run(self, alert: RPMAlert) -> TriageDecision:
        decision = generate_structured(
            TriageDecision,
            system=self.system_prompt,
            user=format_alert(alert),
            role=self.role,
            model=self.model,
        )
        # Safety / consistency guardrails applied in code, independent of the model:
        decision.patient_id = alert.patient_id                       # never trust the model's id
        if decision.urgency == UrgencyLevel.CRITICAL:
            decision.requires_immediate_escalation = True            # Critical always escalates
        return decision


def triage_alert(alert: RPMAlert, *, model: str | None = None) -> TriageDecision:
    """Convenience one-shot helper."""
    return TriageAgent(model=model).run(alert)
