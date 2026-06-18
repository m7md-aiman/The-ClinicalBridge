"""Phase 14 tests: evaluation metrics.

Offline tests verify the matching logic and score the hand-authored gold briefs (which should pass
their own rubrics). One opt-in live test runs the real evaluation across all scenarios.
"""

import os

import pytest

from clinicalbridge.config import settings
from clinicalbridge.evaluation.metrics import (
    avoid_violations,
    citation_coverage,
    contains_substring,
    contains_word,
    score_brief,
    term_coverage,
)
from clinicalbridge.scenarios import build_scenarios


# --- Matching logic (the Phase-5 lesson) ------------------------------------


def test_contains_word_is_boundary_safe():
    assert contains_word("the patient is lying", "lying")
    assert not contains_word("without implying missed doses", "lying")  # the key false-positive


def test_contains_substring_is_lenient():
    assert contains_substring("started a low-carb dietary plan", "diet")
    assert not contains_substring("no match here", "warfarin")


def test_term_coverage_fraction():
    cov = term_coverage("warfarin and inr noted", ["warfarin", "inr", "salad"])
    assert cov["coverage"] == round(2 / 3, 3)
    assert cov["missing"] == ["salad"]


# --- Gold briefs should satisfy their own rubrics ---------------------------


def test_gold_briefs_pass_their_rubrics():
    for s in build_scenarios():
        score = score_brief(s.gold_brief, s.expected_urgency, s.rubric)  # no allowed -> skip halluc.
        assert score["urgency_ok"], f"{s.id}: gold urgency not acceptable"
        assert score["must_include_coverage"] == 1.0, f"{s.id}: gold missing include terms"
        assert score["must_avoid_violations"] == [], f"{s.id}: gold violated avoid terms"
        assert score["citation_coverage"] == 1.0, f"{s.id}: gold has uncited statements"


def test_citation_coverage_on_gold():
    s = build_scenarios()[0]
    cov = citation_coverage(s.gold_brief)
    assert cov["coverage"] == 1.0 and cov["total"] >= 1


# --- Live full evaluation (opt-in: many LLM calls) --------------------------


@pytest.mark.skipif(
    not settings.is_configured or os.getenv("CB_RUN_EVAL") != "1",
    reason="set CB_RUN_EVAL=1 (and configure the API key) to run the full live evaluation",
)
def test_live_full_evaluation_quality():
    from clinicalbridge.evaluation.runner import evaluate_all

    report = evaluate_all()
    agg = report["aggregate"]
    # Hard safety guarantees should hold across all scenarios:
    assert agg["total_hallucinated_citations"] == 0
    assert agg["total_must_avoid_violations"] == 0
    assert agg["mean_citation_coverage"] >= 0.9
