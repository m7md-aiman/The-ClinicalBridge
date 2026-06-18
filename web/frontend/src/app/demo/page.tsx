"use client";

import { CheckCircle2, Loader2, Play, Radio, XCircle, Zap } from "lucide-react";
import * as React from "react";
import { getMeta, getResult, getScenarios, streamRun } from "@/lib/api";
import type {
  Brief,
  Meta,
  OrchestrationResult,
  ResultPayload,
  ScenarioSummary,
  SessionEvent,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { BriefCard } from "@/components/brief-card";
import { PipelineTrace } from "@/components/pipeline-trace";
import { UrgencyBadge } from "@/components/urgency-badge";
import { cn } from "@/lib/utils";

export default function DemoPage() {
  const [meta, setMeta] = React.useState<Meta | null>(null);
  const [scenarios, setScenarios] = React.useState<ScenarioSummary[]>([]);
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [payload, setPayload] = React.useState<ResultPayload | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [showGold, setShowGold] = React.useState(false);

  // Live run state
  const [mode, setMode] = React.useState<"cached" | "live">("cached");
  const [liveSteps, setLiveSteps] = React.useState<SessionEvent[]>([]);
  const [liveBrief, setLiveBrief] = React.useState<Brief | null>(null);
  const [running, setRunning] = React.useState(false);
  const [liveError, setLiveError] = React.useState<string | null>(null);
  const cleanupRef = React.useRef<(() => void) | null>(null);

  React.useEffect(() => {
    getMeta().then(setMeta).catch(() => setMeta(null));
    getScenarios()
      .then((rows) => {
        setScenarios(rows);
        if (rows.length) setSelectedId(rows[0].id);
      })
      .catch(() => setScenarios([]));
  }, []);

  React.useEffect(() => {
    if (!selectedId) return;
    cleanupRef.current?.();
    setMode("cached");
    setLiveSteps([]);
    setLiveBrief(null);
    setLiveError(null);
    setShowGold(false);
    setLoading(true);
    getResult(selectedId)
      .then(setPayload)
      .catch(() => setPayload(null))
      .finally(() => setLoading(false));
  }, [selectedId]);

  React.useEffect(() => () => cleanupRef.current?.(), []);

  const scenario = scenarios.find((s) => s.id === selectedId) || payload?.scenario;

  function runLive() {
    if (!selectedId || !meta?.live_available) return;
    setMode("live");
    setLiveSteps([]);
    setLiveBrief(null);
    setLiveError(null);
    setRunning(true);
    cleanupRef.current = streamRun(selectedId, {
      onStep: (step, summary, data) =>
        setLiveSteps((prev) => [...prev, { ts: "", step, summary, data }]),
      onResult: (result) => {
        const r = result as OrchestrationResult;
        setLiveBrief(r.brief);
        setRunning(false);
      },
      onError: (message) => {
        setLiveError(message);
        setRunning(false);
      },
    });
  }

  const events = mode === "live" ? liveSteps : payload?.result.session.events ?? [];
  const brief = mode === "live" ? liveBrief : payload?.result.brief ?? null;
  const score = payload?.score;

  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Interactive Demo</h1>
      <p className="mt-2 max-w-2xl text-muted-foreground">
        Pick a clinical scenario and watch the multi-agent pipeline turn an RPM alert into a cited
        Clinical Context Brief.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[300px_1fr]">
        {/* Scenario picker */}
        <div className="space-y-3">
          {scenarios.map((s) => (
            <button
              key={s.id}
              onClick={() => setSelectedId(s.id)}
              className={cn(
                "w-full rounded-2xl border bg-card p-4 text-left transition-colors hover:border-primary/50",
                selectedId === s.id && "border-primary ring-1 ring-primary",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{s.title}</span>
                <UrgencyBadge level={s.expected_urgency} />
              </div>
              <p className="mt-1.5 line-clamp-3 text-sm text-muted-foreground">{s.lesson}</p>
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                {s.alert_display} · {s.alert_category}
              </p>
            </button>
          ))}
        </div>

        {/* Main panel */}
        <div className="space-y-6">
          {loading || !scenario ? (
            <Card>
              <CardContent className="flex items-center gap-3 py-16 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" /> Loading scenario…
              </CardContent>
            </Card>
          ) : (
            <>
              {/* Controls + alert */}
              <Card>
                <CardContent className="pt-6">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-semibold">{scenario.title}</h2>
                      <p className="mt-1 max-w-xl text-sm text-muted-foreground">{scenario.lesson}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {meta?.live_available ? (
                        <Button onClick={runLive} disabled={running}>
                          {running ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Zap className="h-4 w-4" />
                          )}
                          Run live
                        </Button>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border bg-muted/40 px-4 py-3 text-sm">
                    <span className="font-medium">RPM alert:</span>
                    <span className="font-mono">{scenario.alert_display}</span>
                    <span className="text-muted-foreground">({scenario.alert_category})</span>
                    <span className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground">
                      {mode === "live" ? (
                        <>
                          <Radio className="h-3.5 w-3.5 text-urgency-critical" /> live run
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5" /> cached run (instant, no API key)
                        </>
                      )}
                    </span>
                  </div>
                  {liveError && (
                    <p className="mt-3 text-sm text-urgency-critical">Live run failed: {liveError}</p>
                  )}
                </CardContent>
              </Card>

              {/* Pipeline trace */}
              <Card>
                <CardContent className="pt-6">
                  <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Pipeline trace
                  </h3>
                  {events.length ? (
                    <PipelineTrace events={events} running={running} />
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {running ? "Starting…" : "No steps yet."}
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Score (cached) */}
              {mode === "cached" && score && (
                <ScorePanel score={score} />
              )}

              {/* Brief */}
              {brief ? (
                <BriefCard brief={brief} label={mode === "live" ? "live" : "system"} />
              ) : running ? (
                <Card>
                  <CardContent className="flex items-center gap-3 py-10 text-muted-foreground">
                    <Loader2 className="h-5 w-5 animate-spin" /> Synthesizing the brief…
                  </CardContent>
                </Card>
              ) : null}

              {/* Gold comparison */}
              <div>
                <Button variant="outline" onClick={() => setShowGold((v) => !v)}>
                  {showGold ? "Hide" : "Show"} gold-standard brief
                </Button>
                {showGold && payload && (
                  <div className="mt-4">
                    <BriefCard brief={payload.gold_brief} label="gold standard" />
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ ok, label, value }: { ok: boolean; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      {ok ? (
        <CheckCircle2 className="h-4 w-4 text-ok" />
      ) : (
        <XCircle className="h-4 w-4 text-urgency-critical" />
      )}
      <span className="text-sm">
        <span className="font-medium">{value}</span>{" "}
        <span className="text-muted-foreground">{label}</span>
      </span>
    </div>
  );
}

function ScorePanel({ score }: { score: ResultPayload["score"] }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Evaluation vs gold rubric
          </h3>
          <span
            className={cn(
              "rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              score.passed
                ? "text-ok border-ok/30 bg-ok/10"
                : "text-urgency-critical border-urgency-critical/30 bg-urgency-critical/10",
            )}
          >
            {score.passed ? "PASS" : "FAIL"}
          </span>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Stat ok={score.urgency_ok} value={score.final_urgency} label="urgency (acceptable)" />
          <Stat
            ok={score.hallucination_count === 0}
            value={`${score.hallucination_count}`}
            label="hallucinated citations"
          />
          <Stat
            ok={score.must_include_coverage >= 0.6}
            value={`${Math.round(score.must_include_coverage * 100)}%`}
            label="key-fact coverage"
          />
          <Stat
            ok={score.citation_coverage >= 0.9}
            value={`${Math.round(score.citation_coverage * 100)}%`}
            label="citation coverage"
          />
        </div>
      </CardContent>
    </Card>
  );
}
