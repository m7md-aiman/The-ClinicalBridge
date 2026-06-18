"""Phase 3 tests: the versioned prompt loader (offline)."""

import pytest

from clinicalbridge.prompts import list_versions, load_prompt


def _write(base, agent, name, version, text):
    d = base / agent
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.v{version}.txt").write_text(text, encoding="utf-8")


def test_loads_latest_version(tmp_path):
    _write(tmp_path, "triage", "system", 1, "v1 text")
    _write(tmp_path, "triage", "system", 2, "v2 text")
    rec = load_prompt("triage/system", base_dir=tmp_path)
    assert rec.version == 2
    assert rec.text == "v2 text"
    assert list_versions("triage/system", base_dir=tmp_path) == [1, 2]


def test_pin_specific_version(tmp_path):
    _write(tmp_path, "triage", "system", 1, "v1 text")
    _write(tmp_path, "triage", "system", 2, "v2 text")
    rec = load_prompt("triage/system", version=1, base_dir=tmp_path)
    assert rec.version == 1
    assert rec.text == "v1 text"


def test_render_uses_dollar_template_not_braces(tmp_path):
    # JSON braces must survive; only $vars are substituted.
    _write(tmp_path, "triage", "system", 1, 'Levels: $levels. Schema: {"a": 1}')
    rec = load_prompt("triage/system", base_dir=tmp_path)
    out = rec.render(levels="Critical, Urgent")
    assert 'Schema: {"a": 1}' in out
    assert "Levels: Critical, Urgent." in out


def test_missing_prompt_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompt("nope/missing", base_dir=tmp_path)


def test_missing_version_raises(tmp_path):
    _write(tmp_path, "triage", "system", 1, "v1")
    with pytest.raises(FileNotFoundError):
        load_prompt("triage/system", version=9, base_dir=tmp_path)


def test_bad_id_raises():
    with pytest.raises(ValueError):
        load_prompt("no-slash")
