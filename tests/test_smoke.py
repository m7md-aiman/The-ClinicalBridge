"""Phase 1 smoke test: the package imports and configuration loads correctly."""

from pathlib import Path

import clinicalbridge
from clinicalbridge.config import settings, load_settings


def test_package_version():
    assert clinicalbridge.__version__ == "0.1.0"


def test_settings_load():
    s = load_settings()
    # Defaults must always be present even without a .env file.
    assert s.openrouter_base_url.startswith("https://")
    assert s.default_model
    assert s.embedding_model
    assert 0.0 <= s.temperature <= 2.0


def test_settings_paths_under_project_root():
    assert isinstance(settings.data_dir, Path)
    assert settings.ehr_dir.parent == settings.data_dir
    assert settings.scenarios_dir.parent == settings.data_dir


def test_per_agent_model_falls_back_to_default(monkeypatch):
    # When no per-agent override is set, agents use the default model.
    monkeypatch.delenv("CB_TRIAGE_MODEL", raising=False)
    monkeypatch.setenv("CB_DEFAULT_MODEL", "test/model-x")
    s = load_settings()
    assert s.default_model == "test/model-x"
    assert s.triage_model == "test/model-x"
