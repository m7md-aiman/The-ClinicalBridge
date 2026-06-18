"""Agent memory for ClinicalBridge (Module 7).

Two complementary memory types:

- :class:`SessionMemory` — short-term **working/audit memory** for a single alert-processing run.
  The orchestrator logs each agent step here, producing a traceable, replayable record of how a
  brief was assembled (used for the Module-8 auditability requirement).

- :class:`PatientMemory` — persistent, file-backed **entity memory** keyed by patient. It remembers
  prior interactions across runs so the system can be longitudinally aware (e.g., "this patient was
  flagged Urgent for the same issue last week"). ``digest()`` renders recent history as text that can
  be injected into a prompt — a lightweight **summary memory**.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from clinicalbridge.config import settings

DEFAULT_MEMORY_DIR = settings.project_root / ".memory"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SessionMemory:
    """Working/audit memory for one alert-processing run."""

    def __init__(self, alert_id: str, patient_id: str) -> None:
        self.alert_id = alert_id
        self.patient_id = patient_id
        self.created_at = _now()
        self.events: list[dict] = []

    def log(self, step: str, summary: str, data: dict | None = None) -> None:
        self.events.append({"ts": _now(), "step": step, "summary": summary, "data": data or {}})

    def steps(self) -> list[str]:
        return [e["step"] for e in self.events]

    def to_dict(self) -> dict:
        return {"alert_id": self.alert_id, "patient_id": self.patient_id,
                "created_at": self.created_at, "events": self.events}

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path


class PatientMemory:
    """Persistent per-patient entity memory across sessions (one JSON file per patient)."""

    def __init__(self, store_dir: Path | None = None) -> None:
        self.dir = Path(store_dir or DEFAULT_MEMORY_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, patient_id: str) -> Path:
        return self.dir / f"{patient_id}.json"

    def history(self, patient_id: str) -> list[dict]:
        path = self._path(patient_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def record_interaction(self, patient_id: str, *, urgency: str, summary: str,
                           flags: list[str] | None = None, alert_id: str | None = None) -> dict:
        entry = {"ts": _now(), "alert_id": alert_id, "urgency": urgency,
                 "summary": summary, "flags": flags or []}
        history = self.history(patient_id)
        history.append(entry)
        self._path(patient_id).write_text(json.dumps(history, indent=2), encoding="utf-8")
        return entry

    def last(self, patient_id: str) -> dict | None:
        history = self.history(patient_id)
        return history[-1] if history else None

    def digest(self, patient_id: str, limit: int = 3) -> str:
        """Render recent interactions as text suitable for injection into an agent prompt."""
        history = self.history(patient_id)
        if not history:
            return ""
        lines = [f"Prior ClinicalBridge interactions for {patient_id} (most recent last):"]
        for e in history[-limit:]:
            flags = f" | flags: {', '.join(e['flags'])}" if e.get("flags") else ""
            lines.append(f"  - [{e['ts']}] urgency={e['urgency']}: {e['summary']}{flags}")
        return "\n".join(lines)
