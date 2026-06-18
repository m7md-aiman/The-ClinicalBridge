// TypeScript mirrors of the FastAPI JSON contracts (see web/backend + clinicalbridge.schemas).

export type UrgencyLevel = "Critical" | "Urgent" | "Routine" | "Informational";

export interface Meta {
  live_available: boolean;
  model: string;
  name: string;
}

export interface CitedStatement {
  statement: string;
  sources: string[];
}

export interface RecommendedAction {
  action: string;
  confidence: string;
  supporting_evidence: string[];
}

export interface Brief {
  patient_id: string;
  generated_at: string;
  alert_summary: string;
  urgency: UrgencyLevel;
  patient_snapshot: string;
  contextual_analysis: CitedStatement[];
  risk_assessment: CitedStatement[];
  recommended_actions: RecommendedAction[];
  uncertainties_and_gaps: string[];
  overall_confidence: string;
  cited_sources: string[];
}

export interface SessionEvent {
  ts: string;
  step: string;
  summary: string;
  data: Record<string, unknown>;
}

export interface OrchestrationResult {
  alert_id: string;
  patient_id: string;
  final_urgency: UrgencyLevel;
  escalated: boolean;
  deterministic_severity: { severity: string; urgency: string; rationale: string };
  errors: string[];
  triage: Record<string, unknown> | null;
  ehr_context: Record<string, unknown> | null;
  anamnesis_summary: Record<string, unknown> | null;
  brief: Brief;
  session: { alert_id: string; patient_id: string; created_at: string; events: SessionEvent[] };
}

export interface Score {
  final_urgency: string;
  acceptable_urgencies: string[];
  urgency_ok: boolean;
  must_include_coverage: number;
  must_include_missing: string[];
  must_flag_coverage: number;
  must_avoid_violations: string[];
  citation_coverage: number;
  citations_cited: number;
  citations_total: number;
  hallucination_count: number;
  hallucinated_citations: string[];
  latency_seconds: number | null;
  errors: number;
  passed: boolean;
}

export interface ScenarioSummary {
  id: string;
  title: string;
  lesson: string;
  expected_urgency: UrgencyLevel;
  patient_id: string;
  alert: Record<string, unknown>;
  alert_display: string;
  alert_category: string;
}

export interface ResultPayload {
  scenario: ScenarioSummary;
  result: OrchestrationResult;
  score: Score;
  gold_brief: Brief;
  gold_brief_markdown: string;
  cached: boolean;
}

export interface EvaluationScenarioRow extends Score {
  scenario_id: string;
  title: string;
  patient_id: string;
  expected_urgency: string;
}

export interface EvaluationAggregate {
  scenarios: number;
  pass_rate: number;
  urgency_accuracy: number;
  mean_must_include_coverage: number;
  mean_citation_coverage: number;
  total_hallucinated_citations: number;
  total_must_avoid_violations: number;
  mean_latency_seconds: number;
  total_errors: number;
}

export interface ProgressionStage {
  stage: string;
  pass_rate: number;
  urgency_accuracy: number;
  mean_must_include_coverage: number;
  mean_citation_coverage: number;
  total_hallucinated_citations: number;
  mean_latency_seconds: number;
}

export interface EvaluationReport {
  report: { scenarios: EvaluationScenarioRow[]; aggregate: EvaluationAggregate } | null;
  progression: ProgressionStage[] | null;
}
