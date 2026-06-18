"""Simple data-access helpers for the generated dataset.

Used by the Anamnesis Agent (reads anamnesis directly) and later by the orchestrator/demo to load
EHR, RPM, and anamnesis records by patient id. EHR *retrieval* goes through the RAG vector store;
these helpers are for whole-record loads.
"""

from __future__ import annotations

import json
from pathlib import Path

from clinicalbridge.config import settings


def _load_json(directory: Path, patient_id: str) -> dict | None:
    path = Path(directory) / f"{patient_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_ehr(patient_id: str, *, ehr_dir: Path | None = None) -> dict | None:
    return _load_json(ehr_dir or settings.ehr_dir, patient_id)


def load_rpm(patient_id: str, *, rpm_dir: Path | None = None) -> dict | None:
    return _load_json(rpm_dir or settings.rpm_dir, patient_id)


def load_anamnesis(patient_id: str, *, anamnesis_dir: Path | None = None) -> dict | None:
    return _load_json(anamnesis_dir or settings.anamnesis_dir, patient_id)


def list_patient_ids(*, ehr_dir: Path | None = None) -> list[str]:
    directory = Path(ehr_dir or settings.ehr_dir)
    return sorted(p.stem for p in directory.glob("*.json"))
