"""Scoring metrics for ClinicalBridge briefs (Module 5).

Design note on matching (the lesson from Phase 5):
- **must_include / must_flag use lenient substring matching** — we want to detect the *concept*
  even if phrased differently ("diet" should match "dietary").
- **must_avoid uses strict word-boundary matching** — to prevent false positives like the forbidden
  word "lying" matching inside "imp-lying". This asymmetry is deliberate.
"""

from __future__ import annotations

import re

from clinicalbridge.schemas import ClinicalContextBrief, UrgencyLevel


def contains_substring(text: str, term: str) -> bool:
    return bool(term) and term.lower() in text.lower()


def contains_word(text: str, term: str) -> bool:
    """Whole-token match (so 'lying' does NOT match 'implying')."""
    if not term:
        return False
    pattern = r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def term_present(text: str, term: str) -> bool:
    """Concept matching: a term may be a synonym group 'a|b|c'; any alternative counts (substring).

    Introduced after the baseline run showed the model expressing required concepts with synonyms
    (e.g. 'stopped' -> 'discontinued', 'salad' -> 'leafy greens'). This matches the *concept*, not a
    literal word.
    """
    return any(contains_substring(text, alt) for alt in term.split("|") if alt)


def avoid_present(text: str, term: str) -> bool:
    """A forbidden term (possibly a group) is present if any alternative matches as a whole word."""
    return any(contains_word(text, alt) for alt in term.split("|") if alt)


def term_coverage(text: str, terms: list[str]) -> dict:
    found = [t for t in terms if term_present(text, t)]
    missing = [t for t in terms if t not in found]
    coverage = (len(found) / len(terms)) if terms else 1.0
    return {"found": found, "missing": missing, "coverage": round(coverage, 3)}


def avoid_violations(text: str, terms: list[str]) -> list[str]:
    return [t for t in terms if avoid_present(text, t)]


def urgency_acceptable(urgency: UrgencyLevel, acceptable: list[str]) -> bool:
    return urgency.value in acceptable


def citation_coverage(brief: ClinicalContextBrief) -> dict:
    """Fraction of analytical statements that carry at least one source."""
    statements = brief.contextual_analysis + brief.risk_assessment
    total = len(statements)
    cited = sum(1 for s in statements if s.sources)
    return {"cited": cited, "total": total, "coverage": round(cited / total, 3) if total else 1.0}


def hallucinated_citations(brief: ClinicalContextBrief, allowed: list[str]) -> list[str]:
    allowed_set = set(allowed)
    used: set[str] = set()
    for s in brief.contextual_analysis + brief.risk_assessment:
        used.update(s.sources)
    for a in brief.recommended_actions:
        used.update(a.supporting_evidence)
    return sorted(c for c in used if c and c not in allowed_set)


# Thresholds for a scenario to "pass".
MIN_INCLUDE_COVERAGE = 0.6
MIN_CITATION_COVERAGE = 0.9


def score_brief(
    brief: ClinicalContextBrief,
    final_urgency: UrgencyLevel,
    rubric: dict,
    *,
    allowed_sources: list[str] | None = None,
    latency_seconds: float | None = None,
    errors: int = 0,
) -> dict:
    """Score one brief against a scenario rubric. Returns a flat, serializable dict."""
    text = brief.render().lower()
    gap_text = (text + " " + " ".join(brief.uncertainties_and_gaps)).lower()

    include = term_coverage(text, rubric.get("must_include", []))
    flag = term_coverage(gap_text, rubric.get("must_flag", []))
    violations = avoid_violations(text, rubric.get("must_avoid", []))
    urg_ok = urgency_acceptable(final_urgency, rubric.get("acceptable_urgencies", []))
    citation = citation_coverage(brief)
    hallucinated = hallucinated_citations(brief, allowed_sources) if allowed_sources is not None else []

    passed = (
        urg_ok
        and not violations
        and not hallucinated
        and include["coverage"] >= MIN_INCLUDE_COVERAGE
        and citation["coverage"] >= MIN_CITATION_COVERAGE
    )

    return {
        "final_urgency": final_urgency.value,
        "acceptable_urgencies": rubric.get("acceptable_urgencies", []),
        "urgency_ok": urg_ok,
        "must_include_coverage": include["coverage"],
        "must_include_missing": include["missing"],
        "must_flag_coverage": flag["coverage"],
        "must_flag_missing": flag["missing"],
        "must_avoid_violations": violations,
        "citation_coverage": citation["coverage"],
        "citations_cited": citation["cited"],
        "citations_total": citation["total"],
        "hallucinated_citations": hallucinated,
        "hallucination_count": len(hallucinated),
        "latency_seconds": round(latency_seconds, 2) if latency_seconds is not None else None,
        "errors": errors,
        "passed": passed,
    }
