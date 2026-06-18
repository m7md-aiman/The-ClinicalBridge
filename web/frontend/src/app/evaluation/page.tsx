"use client";

import { CheckCircle2, Clock, Gauge, Quote, ShieldCheck, Target, XCircle } from "lucide-react";
import * as React from "react";
import { getEvaluation } from "@/lib/api";
import type { EvaluationReport } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/metric-card";
import { ProgressionChart } from "@/components/progression-chart";
import { UrgencyBadge } from "@/components/urgency-badge";
import { cn } from "@/lib/utils";

export default function EvaluationPage() {
  const [data, setData] = React.useState<EvaluationReport | null>(null);
  const [error, setError] = React.useState(false);

  React.useEffect(() => {
    getEvaluation().then(setData).catch(() => setError(true));
  }, []);

  const agg = data?.report?.aggregate;
  const rows = data?.report?.scenarios ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Evaluation</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">
        Every scenario is scored end-to-end against a hand-authored gold rubric: urgency, key-fact
        coverage, citation discipline, and hallucinations.
      </p>

      {error && <p className="mt-8 text-urgency-critical">Could not load evaluation data.</p>}

      {agg && (
        <>
          <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            <MetricCard
              icon={<Target className="h-5 w-5" />}
              value={`${Math.round(agg.pass_rate * 100)}%`}
              label="Scenario pass rate"
              sub={`${rows.filter((r) => r.passed).length}/${agg.scenarios} scenarios`}
              good={agg.pass_rate === 1}
            />
            <MetricCard
              icon={<Gauge className="h-5 w-5" />}
              value={`${Math.round(agg.urgency_accuracy * 100)}%`}
              label="Urgency accuracy"
              good={agg.urgency_accuracy === 1}
            />
            <MetricCard
              icon={<ShieldCheck className="h-5 w-5" />}
              value={`${agg.total_hallucinated_citations}`}
              label="Hallucinated citations"
              good={agg.total_hallucinated_citations === 0}
            />
            <MetricCard
              icon={<Quote className="h-5 w-5" />}
              value={`${Math.round(agg.mean_citation_coverage * 100)}%`}
              label="Citation coverage"
              good={agg.mean_citation_coverage >= 0.9}
            />
            <MetricCard
              icon={<Clock className="h-5 w-5" />}
              value={`${agg.mean_latency_seconds.toFixed(0)}s`}
              label="Mean latency"
              sub="goal < 60s"
              good={agg.mean_latency_seconds < 60}
            />
          </div>

          {/* Per-scenario results */}
          <Card className="mt-8">
            <CardContent className="overflow-x-auto pt-6">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                Per-scenario results
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Scenario</th>
                    <th className="py-2 pr-4 font-medium">Final</th>
                    <th className="py-2 pr-4 font-medium">Expected</th>
                    <th className="py-2 pr-4 font-medium">Coverage</th>
                    <th className="py-2 pr-4 font-medium">Citations</th>
                    <th className="py-2 pr-4 font-medium">Halluc.</th>
                    <th className="py-2 font-medium">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.scenario_id} className="border-b last:border-0">
                      <td className="py-3 pr-4 font-medium">{r.title}</td>
                      <td className="py-3 pr-4">
                        <UrgencyBadge level={r.final_urgency} />
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">{r.expected_urgency}</td>
                      <td className="py-3 pr-4">{Math.round(r.must_include_coverage * 100)}%</td>
                      <td className="py-3 pr-4">{Math.round(r.citation_coverage * 100)}%</td>
                      <td className="py-3 pr-4">{r.hallucination_count}</td>
                      <td className="py-3">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold",
                            r.passed
                              ? "text-ok border-ok/30 bg-ok/10"
                              : "text-urgency-critical border-urgency-critical/30 bg-urgency-critical/10",
                          )}
                        >
                          {r.passed ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5" />
                          )}
                          {r.passed ? "PASS" : "FAIL"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}

      {/* Progression story */}
      {data?.progression && (
        <Card className="mt-8">
          <CardContent className="pt-6">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Prompt-iteration progression
            </h2>
            <p className="mt-1 mb-4 max-w-2xl text-sm text-muted-foreground">
              How the system improved across iterations — v1 prompts → v2 prompts → v2 plus a
              deterministic trend guardrail. Safety metrics (citations, hallucinations) stayed perfect
              throughout.
            </p>
            <ProgressionChart stages={data.progression} />
          </CardContent>
        </Card>
      )}

      {!data && !error && (
        <p className="mt-8 text-muted-foreground">Loading evaluation…</p>
      )}
    </div>
  );
}
