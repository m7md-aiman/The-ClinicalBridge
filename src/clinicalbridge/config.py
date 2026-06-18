"""Central configuration for ClinicalBridge.

All settings are read from environment variables (loaded from a ``.env`` file at the
project root — see ``.env.example``) with sensible defaults, so the prototype is
runnable with only ``OPENROUTER_API_KEY`` set.

Usage::

    from clinicalbridge.config import settings
    print(settings.default_model)
    print(settings.ehr_dir)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Silence ChromaDB's noisy (and currently buggy) telemetry before any chroma import.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

# Project root = three levels up from this file: src/clinicalbridge/config.py -> root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load .env (if present) before reading any variables.
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str) -> str:
    """Return a stripped env var, falling back to ``default`` when unset/empty."""
    value = os.getenv(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of all runtime configuration."""

    # --- OpenRouter (chat/completions; OpenAI-compatible) ---
    openrouter_api_key: str
    openrouter_base_url: str

    # --- Models (any OpenRouter model id) ---
    default_model: str
    triage_model: str
    ehr_model: str
    anamnesis_model: str
    synthesis_model: str

    # --- Local embedding model (for the EHR vector store) ---
    embedding_model: str

    # --- Generation defaults ---
    temperature: float
    max_tokens: int
    request_timeout: int

    # --- Filesystem paths ---
    project_root: Path
    data_dir: Path
    ehr_dir: Path
    rpm_dir: Path
    anamnesis_dir: Path
    scenarios_dir: Path
    chroma_dir: Path

    @property
    def is_configured(self) -> bool:
        """True when an OpenRouter API key is present (required for LLM calls)."""
        return bool(self.openrouter_api_key) and "xxxx" not in self.openrouter_api_key


def load_settings() -> Settings:
    """Build a :class:`Settings` snapshot from the current environment."""
    default_model = _env("CB_DEFAULT_MODEL", "openai/gpt-4o-mini")
    data_dir = PROJECT_ROOT / "data"
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_base_url=_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        default_model=default_model,
        triage_model=_env("CB_TRIAGE_MODEL", default_model),
        ehr_model=_env("CB_EHR_MODEL", default_model),
        anamnesis_model=_env("CB_ANAMNESIS_MODEL", default_model),
        synthesis_model=_env("CB_SYNTHESIS_MODEL", default_model),
        embedding_model=_env("CB_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        temperature=float(_env("CB_TEMPERATURE", "0.1")),
        max_tokens=int(_env("CB_MAX_TOKENS", "1500")),
        request_timeout=int(_env("CB_REQUEST_TIMEOUT", "60")),
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        ehr_dir=data_dir / "ehr",
        rpm_dir=data_dir / "rpm",
        anamnesis_dir=data_dir / "anamnesis",
        scenarios_dir=data_dir / "scenarios",
        chroma_dir=PROJECT_ROOT / ".chroma",
    )


# Module-level singleton used across the codebase.
settings = load_settings()


if __name__ == "__main__":
    # Quick diagnostic: `python -m clinicalbridge.config`
    print("ClinicalBridge configuration")
    print("-" * 40)
    print(f"OpenRouter configured : {settings.is_configured}")
    print(f"Base URL              : {settings.openrouter_base_url}")
    print(f"Default model         : {settings.default_model}")
    print(f"  triage              : {settings.triage_model}")
    print(f"  ehr                 : {settings.ehr_model}")
    print(f"  anamnesis           : {settings.anamnesis_model}")
    print(f"  synthesis           : {settings.synthesis_model}")
    print(f"Embedding model       : {settings.embedding_model}")
    print(f"Temperature           : {settings.temperature}")
    print(f"Data dir              : {settings.data_dir}")
    print(f"Chroma dir            : {settings.chroma_dir}")
