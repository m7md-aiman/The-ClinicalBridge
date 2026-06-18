"""Versioned prompt library for ClinicalBridge.

Prompts are plain-text files so they can be version-controlled, diffed, and reviewed like code —
a core requirement of the Module 3 / Module 8 prompt-engineering portfolio.

Layout (created from Phase 6 onward)::

    prompts/library/<agent>/<name>.v<N>.txt

e.g. ``library/triage/system.v1.txt``, ``library/triage/system.v2.txt``.

Variable substitution uses ``string.Template`` (``$name`` / ``${name}``) rather than ``str.format``
so that literal ``{ }`` braces in JSON examples inside a prompt do **not** need escaping.

Usage::

    from clinicalbridge.prompts import load_prompt
    rec = load_prompt("triage/system")            # latest version
    rec = load_prompt("triage/system", version=1) # pin a version
    text = rec.render(urgency_levels="Critical, Urgent, Routine, Informational")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from string import Template

LIBRARY_DIR = Path(__file__).parent / "library"

_FILE_RE = re.compile(r"^(?P<name>.+)\.v(?P<version>\d+)\.txt$")


@dataclass(frozen=True)
class PromptRecord:
    """A single resolved prompt: its identity, version, text, and source path."""

    agent: str
    name: str
    version: int
    text: str
    path: Path

    def render(self, **kwargs: object) -> str:
        """Substitute ``$variables`` in the prompt; leaves unknown placeholders untouched."""
        return Template(self.text).safe_substitute(**kwargs)


def _candidates(agent: str, name: str, base_dir: Path) -> list[tuple[int, Path]]:
    agent_dir = base_dir / agent
    if not agent_dir.is_dir():
        return []
    found: list[tuple[int, Path]] = []
    for path in agent_dir.glob(f"{name}.v*.txt"):
        match = _FILE_RE.match(path.name)
        if match and match.group("name") == name:
            found.append((int(match.group("version")), path))
    found.sort()
    return found


def list_versions(rel: str, base_dir: Path = LIBRARY_DIR) -> list[int]:
    """Return the available version numbers for ``<agent>/<name>``, ascending."""
    agent, name = _split(rel)
    return [v for v, _ in _candidates(agent, name, base_dir)]


def load_prompt(rel: str, version: int | None = None, base_dir: Path = LIBRARY_DIR) -> PromptRecord:
    """Load ``<agent>/<name>``; latest version unless ``version`` is given."""
    agent, name = _split(rel)
    candidates = _candidates(agent, name, base_dir)
    if not candidates:
        raise FileNotFoundError(f"No prompt files for '{rel}' under {base_dir / agent}")

    if version is None:
        chosen_version, path = candidates[-1]
    else:
        matches = [c for c in candidates if c[0] == version]
        if not matches:
            available = [v for v, _ in candidates]
            raise FileNotFoundError(f"Prompt '{rel}' has no v{version}; available: {available}")
        chosen_version, path = matches[0]

    return PromptRecord(
        agent=agent,
        name=name,
        version=chosen_version,
        text=path.read_text(encoding="utf-8"),
        path=path,
    )


def _split(rel: str) -> tuple[str, str]:
    if "/" not in rel:
        raise ValueError(f"Prompt id must be '<agent>/<name>', got {rel!r}")
    agent, name = rel.split("/", 1)
    return agent, name


__all__ = ["PromptRecord", "load_prompt", "list_versions", "LIBRARY_DIR"]
