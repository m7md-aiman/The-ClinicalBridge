"""Phase 3 tests: LLM layer.

Offline tests cover model resolution and JSON extraction. A single live test exercises a real
OpenRouter structured call; it is skipped automatically when no API key is configured.
"""

import pytest
from pydantic import BaseModel, Field

from clinicalbridge.config import settings
from clinicalbridge.llm import extract_json, generate_structured, resolve_model

# --- Offline -----------------------------------------------------------------


def test_resolve_model_uses_role_mapping():
    # Mapping logic reflects the live (frozen) settings without mutating them.
    assert resolve_model() == settings.default_model
    assert resolve_model("triage") == settings.triage_model
    assert resolve_model("synthesis") == settings.synthesis_model
    assert resolve_model("unknown-role") == settings.default_model


def test_resolve_model_explicit_override():
    assert resolve_model("triage", "override/y") == "override/y"


def test_extract_json_plain():
    assert extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_extract_json_with_fence_and_prose():
    text = 'Here is the result:\n```json\n{"answer": 4}\n```\nThanks!'
    assert extract_json(text) == {"answer": 4}


def test_extract_json_embedded_in_prose():
    assert extract_json('blah {"answer": 4} trailing') == {"answer": 4}


def test_extract_json_raises_when_absent():
    with pytest.raises(ValueError):
        extract_json("no json here")


# --- Live (requires OPENROUTER_API_KEY) -------------------------------------


class _Arithmetic(BaseModel):
    answer: int = Field(description="The numeric answer.")
    explanation: str = Field(description="One short sentence explaining the calculation.")


@pytest.mark.skipif(not settings.is_configured, reason="OPENROUTER_API_KEY not configured")
def test_live_structured_call():
    result = generate_structured(
        _Arithmetic,
        system="You are a precise calculator. Return only the structured answer.",
        user="What is 2 + 2?",
        role="triage",
        temperature=0,
    )
    assert isinstance(result, _Arithmetic)
    assert result.answer == 4
