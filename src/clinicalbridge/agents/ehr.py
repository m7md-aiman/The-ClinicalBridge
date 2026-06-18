"""EHR Retrieval Agent.

Input:  patient_id + the Triage Agent's ``ehr_query`` (focus terms) + the clinical question.
Output: a structured ``EHRContext`` extracted strictly from retrieved EHR chunks, with every item
        cited to a ``source_ref`` and missing data flagged rather than invented.

Modules exercised: M6 (RAG retrieval + structured output), M7 (an agent using a retrieval tool).
"""

from __future__ import annotations

from langchain_core.documents import Document

from clinicalbridge.agents.base import Agent
from clinicalbridge.llm import generate_structured
from clinicalbridge.schemas import EHRContext, RetrievalQuery, TriageDecision

MAX_CONTEXT_DOCS = 12


def format_context(docs: list[Document]) -> str:
    if not docs:
        return "(No EHR excerpts were retrieved for this patient.)"
    blocks = []
    for i, d in enumerate(docs, 1):
        ref = d.metadata.get("source_ref", "?")
        section = d.metadata.get("section", "?")
        blocks.append(f"[{i}] source_ref={ref} | section={section}\n{d.page_content}")
    return "\n\n".join(blocks)


class EHRRetrievalAgent(Agent):
    role = "ehr"
    prompt_id = "ehr/system"

    def __init__(self, retriever=None, *, model: str | None = None, prompt_version: int | None = None):
        super().__init__(model=model, prompt_version=prompt_version)
        self._retriever = retriever

    @property
    def retriever(self):
        if self._retriever is None:
            # Lazy import + load so unit tests that inject a retriever need no vector store.
            from clinicalbridge.rag.retriever import EHRRetriever
            self._retriever = EHRRetriever()
        return self._retriever

    def _retrieve(self, patient_id: str, query: RetrievalQuery, clinical_question: str) -> list[Document]:
        seen: set[str] = set()
        ordered: list[Document] = []
        # Broad combined query first, then each focus term for recall.
        searches = [clinical_question] if clinical_question else []
        searches.append(", ".join(query.focus_terms))
        searches.extend(query.focus_terms)
        for q in searches:
            if not q.strip():
                continue
            for d in self.retriever.search(q, patient_id=patient_id, k=3):
                key = f"{d.metadata.get('source_ref', '')}|{d.page_content[:48]}"
                if key not in seen:
                    seen.add(key)
                    ordered.append(d)
        return ordered[:MAX_CONTEXT_DOCS]

    def run(self, patient_id: str, ehr_query: RetrievalQuery, clinical_question: str = "") -> EHRContext:
        docs = self._retrieve(patient_id, ehr_query, clinical_question)

        # No records → return an honest, empty, flagged context without calling the LLM.
        if not docs:
            return EHRContext(
                patient_id=patient_id,
                retrieval_confidence=0.0,
                missing_data_flags=["No EHR records were retrieved for this patient."],
                source_documents=[],
            )

        user = (
            f"CLINICAL QUESTION: {clinical_question or '(none provided)'}\n"
            f"FOCUS TERMS: {', '.join(ehr_query.focus_terms)}\n"
            f"PATIENT: {patient_id}\n\n"
            "RETRIEVED EHR EXCERPTS (use ONLY these; copy each item's source_ref):\n"
            f"{format_context(docs)}\n\n"
            "Extract the structured, citable EHR context now."
        )
        context = generate_structured(
            EHRContext, system=self.system_prompt, user=user, role=self.role, model=self.model
        )
        context.patient_id = patient_id
        if not context.source_documents:
            context.source_documents = sorted({d.metadata.get("source_ref", "") for d in docs})
        return context

    def run_from_triage(self, triage: TriageDecision) -> EHRContext:
        return self.run(triage.patient_id, triage.ehr_query, triage.clinical_question)
