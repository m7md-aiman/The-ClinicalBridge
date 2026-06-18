"""Evaluation framework for ClinicalBridge (Module 5)."""

from clinicalbridge.evaluation.metrics import score_brief
from clinicalbridge.evaluation.runner import evaluate_all, evaluate_scenario, render_report

__all__ = ["score_brief", "evaluate_all", "evaluate_scenario", "render_report"]
