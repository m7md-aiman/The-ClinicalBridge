"""LLM infrastructure for ClinicalBridge.

A thin, reliability-focused layer over OpenRouter (an OpenAI-compatible gateway) accessed through
LangChain's ``ChatOpenAI``. Responsibilities:

- Build chat models per **agent role**, so each agent can use its own configured model
  (``settings.triage_model`` etc.), all behind one API key.
- Produce **schema-validated structured output** from any Pydantic model, with two strategies:
  native tool/function-calling first, then a JSON-parsing fallback for models that don't support
  tools — so the system degrades gracefully across the many models OpenRouter exposes.
- **Retry** transient failures (network blips, rate limits, occasional malformed output).

Public API:
    get_chat_model(role) -> ChatOpenAI
    chat(system, user, role=...) -> str
    generate_structured(schema, system=..., user=..., role=...) -> <schema instance>
"""

from __future__ import annotations

import json
import re
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from clinicalbridge.config import settings

T = TypeVar("T", bound=BaseModel)

# Optional attribution headers OpenRouter uses for its rankings (harmless if ignored).
_DEFAULT_HEADERS = {
    "HTTP-Referer": "https://github.com/clinicalbridge-capstone",
    "X-Title": "ClinicalBridge",
}

# Retry policy shared by all network-bound calls.
_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


class LLMNotConfiguredError(RuntimeError):
    """Raised when an LLM call is attempted without a valid OpenRouter API key."""


def resolve_model(role: str | None = None, model: str | None = None) -> str:
    """Resolve the model id for a role, honoring an explicit override."""
    if model:
        return model
    mapping = {
        "triage": settings.triage_model,
        "ehr": settings.ehr_model,
        "anamnesis": settings.anamnesis_model,
        "synthesis": settings.synthesis_model,
    }
    return mapping.get(role or "", settings.default_model)


def get_chat_model(
    role: str | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """Construct a ``ChatOpenAI`` pointed at OpenRouter for the given agent role."""
    if not settings.is_configured:
        raise LLMNotConfiguredError(
            "OPENROUTER_API_KEY is missing or still a placeholder. "
            "Set it in the project .env file (format: OPENROUTER_API_KEY=sk-or-...)."
        )
    return ChatOpenAI(
        model=resolve_model(role, model),
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=settings.temperature if temperature is None else temperature,
        max_tokens=settings.max_tokens if max_tokens is None else max_tokens,
        timeout=settings.request_timeout,
        default_headers=_DEFAULT_HEADERS,
    )


def chat(
    system: str,
    user: str,
    *,
    role: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> str:
    """Plain text completion. Used for non-structured calls and smoke tests."""
    llm = get_chat_model(role, model=model, temperature=temperature)

    @_retry
    def _run() -> str:
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return resp.content if isinstance(resp.content, str) else str(resp.content)

    return _run()


def generate_structured(
    schema: type[T],
    *,
    system: str,
    user: str,
    role: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
) -> T:
    """Return an instance of ``schema`` produced by the model and validated by Pydantic.

    Tries native function-calling structured output first; on any failure falls back to asking
    the model for raw JSON and parsing it. Both paths are retried.
    """
    llm = get_chat_model(role, model=model, temperature=temperature)
    messages = [SystemMessage(content=system), HumanMessage(content=user)]

    try:
        return _structured_via_tools(llm, schema, messages)
    except Exception:
        # Fall back to JSON-parsing for models without reliable tool support.
        return _structured_via_json(llm, schema, messages)


@_retry
def _structured_via_tools(llm: ChatOpenAI, schema: type[T], messages: list) -> T:
    structured = llm.with_structured_output(schema, method="function_calling")
    result = structured.invoke(messages)
    if result is None:
        raise ValueError("Structured output returned None.")
    return result  # type: ignore[return-value]


def _structured_via_json(llm: ChatOpenAI, schema: type[T], messages: list) -> T:
    parser = PydanticOutputParser(pydantic_object=schema)
    json_messages = messages + [
        HumanMessage(
            content=(
                "Respond with ONLY a single valid JSON object — no prose, no markdown fences.\n\n"
                + parser.get_format_instructions()
            )
        )
    ]

    @_retry
    def _run() -> T:
        resp = llm.invoke(json_messages)
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        return schema.model_validate(extract_json(text))

    return _run()


def extract_json(text: str) -> dict:
    """Extract the first JSON object from a model response, tolerating code fences/prose."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"No JSON object found in model response: {text[:200]!r}")
        candidate = text[start : end + 1]
    return json.loads(candidate)


__all__ = [
    "LLMNotConfiguredError",
    "resolve_model",
    "get_chat_model",
    "chat",
    "generate_structured",
    "extract_json",
]
