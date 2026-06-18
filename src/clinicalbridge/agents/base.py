"""Shared base class for ClinicalBridge agents.

Each agent is a thin object that pairs a **role** (which selects the model via configuration) with a
**versioned system prompt** loaded from the prompt library. Subclasses implement ``run()``.

Keeping this minimal is deliberate: the intellectual work lives in the prompts and the structured
schemas, not in a heavy framework.
"""

from __future__ import annotations

from clinicalbridge.prompts import PromptRecord, load_prompt


def clean_source_ref(ref: str) -> str:
    """Strip stray brackets/whitespace a model may copy along with a source tag.

    Keeps citations consistent across agents (e.g. ``[EHR:PT-001/labs]`` -> ``EHR:PT-001/labs``),
    which matters because the Synthesis Agent and evaluator match on these strings.
    """
    return (ref or "").strip().strip("[]").strip()


class Agent:
    """Base class: resolves a versioned system prompt for a named role."""

    #: model-selection role key (see clinicalbridge.llm.resolve_model)
    role: str = "default"
    #: prompt library id, e.g. "triage/system"; set by subclasses
    prompt_id: str | None = None

    def __init__(self, *, model: str | None = None, prompt_version: int | None = None) -> None:
        self.model = model
        self.prompt_version = prompt_version
        self._prompt: PromptRecord | None = None

    @property
    def prompt(self) -> PromptRecord:
        if self.prompt_id is None:
            raise NotImplementedError(f"{type(self).__name__} must set a prompt_id.")
        if self._prompt is None:
            self._prompt = load_prompt(self.prompt_id, version=self.prompt_version)
        return self._prompt

    @property
    def system_prompt(self) -> str:
        return self.prompt.text

    def __repr__(self) -> str:
        ver = self.prompt.version if self.prompt_id else "n/a"
        return f"<{type(self).__name__} role={self.role!r} prompt={self.prompt_id!r} v{ver}>"
