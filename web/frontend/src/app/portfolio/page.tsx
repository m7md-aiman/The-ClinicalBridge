"use client";

import {
  AlertTriangle,
  Clock,
  Download,
  FileText,
  Quote,
  ShieldCheck,
  Target,
} from "lucide-react";
import * as React from "react";
import { getEvaluation } from "@/lib/api";
import type { EvaluationReport, ProgressionStage } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/metric-card";
import { ProgressionChart } from "@/components/progression-chart";
import { Reveal } from "@/components/reveal";

const TOC = [
  ["summary", "Summary"],
  ["problem", "Problem"],
  ["architecture", "Architecture"],
  ["metrics", "Metrics up front"],
  ["iteration", "Prompt iteration"],
  ["evaluation", "Evaluation"],
  ["safety", "Safety"],
  ["anti-hallucination", "Anti-hallucination"],
  ["lessons", "Lessons"],
  ["ethics", "Ethics"],
];

const FALLBACK_PROGRESSION: ProgressionStage[] = [
  { stage: "v1 baseline", pass_rate: 0.6, urgency_accuracy: 0.8, mean_must_include_coverage: 0.62, mean_citation_coverage: 1, total_hallucinated_citations: 0, mean_latency_seconds: 23.2 },
  { stage: "v2 prompts", pass_rate: 0.8, urgency_accuracy: 0.8, mean_must_include_coverage: 0.82, mean_citation_coverage: 1, total_hallucinated_citations: 0, mean_latency_seconds: 25.5 },
  { stage: "v2 + trend guardrail", pass_rate: 1, urgency_accuracy: 1, mean_must_include_coverage: 0.87, mean_citation_coverage: 1, total_hallucinated_citations: 0, mean_latency_seconds: 18.9 },
];

const EVAL_TEXT = `scenario              final     expected   urg  incl  cite  hall  pass
--------------------------------------------------------------------------
missed_medication     Urgent    Urgent     OK   0.67  1.0   0     PASS
false_alarm           Routine   Routine    OK   0.67  1.0   0     PASS
silent_deterioration  Urgent    Urgent     OK   1.00  1.0   0     PASS
incomplete_record     Urgent    Routine    OK   0.67  1.0   0     PASS
conflicting_data      Urgent    Urgent     OK   0.67  1.0   0     PASS
--------------------------------------------------------------------------
pass_rate 1.0 · urgency_accuracy 1.0 · citation_coverage 1.0 · hallucinations 0`;

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 border-t pt-10">
      <Reveal>
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        <div className="mt-4 space-y-4 text-[15px] leading-relaxed text-foreground/90">{children}</div>
      </Reveal>
    </section>
  );
}

function Shot({ src, alt }: { src: string; alt: string }) {
  return (
    <figure className="overflow-hidden rounded-2xl border shadow-sm">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="w-full" />
    </figure>
  );
}

export default function PortfolioPage() {
  const [data, setData] = React.useState<EvaluationReport | null>(null);
  React.useEffect(() => {
    getEvaluation().then(setData).catch(() => setData(null));
  }, []);
  const agg = data?.report?.aggregate;
  const progression = data?.progression ?? FALLBACK_PROGRESSION;

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      {/* Header */}
      <Reveal>
        <Badge className="bg-muted text-muted-foreground">Capstone deliverable · COP-3442</Badge>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight md:text-5xl">
          Prompt-Engineering Portfolio
        </h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Every design decision, prompt iteration, evaluation result, and lesson learned — from the
          ClinicalBridge multi-agent clinical decision-support system.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <a
            href="/ClinicalBridge_Portfolio.md"
            download
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
          >
            <Download className="h-4 w-4" /> Download full portfolio (Markdown)
          </a>
          <a
            href="https://github.com"
            className="inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium hover:bg-muted"
          >
            <FileText className="h-4 w-4" /> Source: docs/ + src/clinicalbridge/
          </a>
        </div>
      </Reveal>

      {/* TOC */}
      <nav className="sticky top-16 z-30 -mx-4 mt-8 border-y bg-background/85 px-4 py-2 backdrop-blur">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {TOC.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="text-muted-foreground hover:text-primary">
              {label}
            </a>
          ))}
        </div>
      </nav>

      <div className="mt-4 space-y-2">
        {/* Summary */}
        <Section id="summary" title="1 · Executive summary">
          <p>
            ClinicalBridge turns a single RPM alert into a structured, cited Clinical Context Brief a
            clinician can read in under 60 seconds, using four prompt-engineered agents (Triage, EHR
            Retrieval, Anamnesis, Synthesis) coordinated by an Orchestrator. It is{" "}
            <strong>grounded by construction</strong> (every claim cites an allowed source) and{" "}
            <strong>safe by layering</strong> (deterministic guardrails enforce urgency floors).
          </p>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <MetricCard icon={<Target className="h-5 w-5" />} value={agg ? `${Math.round(agg.pass_rate * 100)}%` : "100%"} label="Scenario pass rate" good />
            <MetricCard icon={<ShieldCheck className="h-5 w-5" />} value={agg ? `${agg.total_hallucinated_citations}` : "0"} label="Hallucinated citations" good />
            <MetricCard icon={<Quote className="h-5 w-5" />} value={agg ? `${Math.round(agg.mean_citation_coverage * 100)}%` : "100%"} label="Citation coverage" good />
            <MetricCard icon={<Clock className="h-5 w-5" />} value={agg ? `${agg.mean_latency_seconds.toFixed(0)}s` : "~27s"} label="Mean latency (goal <60s)" good />
          </div>
        </Section>

        {/* Problem */}
        <Section id="problem" title="2 · The Clinical Context Gap">
          <p>
            Clinicians have more data than ever, yet decide with less meaningful context, because three
            data streams never connect:
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            {[
              ["EHR — the past", "~30% of hypertensive patients miss the structured diagnosis code."],
              ["RPM — the present", "Only 5–13% of ICU alarms are actionable; 2% of patients cause 77% of false alarms."],
              ["Anamnesis — the voice", "Often unstructured; sometimes not stored in the EHR at all."],
            ].map(([t, s]) => (
              <Card key={t}><CardContent className="pt-5">
                <div className="font-semibold">{t}</div>
                <div className="mt-1 text-sm text-muted-foreground">{s}</div>
              </CardContent></Card>
            ))}
          </div>
        </Section>

        {/* Architecture */}
        <Section id="architecture" title="3 · System architecture">
          <p>
            A linear-then-convergent pipeline: triage classifies urgency and decides what to retrieve;
            the EHR (RAG) and Anamnesis agents gather context in parallel; synthesis fuses everything
            into the cited brief. Agents pass typed Pydantic contracts, so provenance survives every hop.
          </p>
          <Shot src="/assets/architecture.png" alt="ClinicalBridge architecture diagram" />
        </Section>

        {/* Metrics up front */}
        <Section id="metrics" title="4 · Success metrics — defined up front">
          <p>
            Before any agent was built, each scenario was given a rubric: an acceptable urgency band,
            required facts (<code>must_include</code>), required gap flags (<code>must_flag</code>), and
            forbidden content (<code>must_avoid</code>). A scenario passes only with acceptable urgency,
            <strong> zero hallucinated citations</strong>, zero must-avoid violations, ≥60% key-fact
            coverage, and ≥90% citation coverage.
          </p>
          <p className="text-sm text-muted-foreground">
            Matching is asymmetric by design: lenient substring for must-include (find the concept),
            strict whole-word for must-avoid (so "lying" never matches "imp-lying").
          </p>
        </Section>

        {/* Iteration */}
        <Section id="iteration" title="5 · Prompt iteration (the centerpiece)">
          <p>The system improved through evidence-driven iteration:</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Metric</th>
                <th className="py-2 pr-4 font-medium">v1</th>
                <th className="py-2 pr-4 font-medium">v2 prompts</th>
                <th className="py-2 font-medium">v2 + guardrail</th>
              </tr></thead>
              <tbody>
                {[["Pass rate", "0.60", "0.80", "1.00"], ["Urgency accuracy", "0.80", "0.80", "1.00"], ["Hallucinations", "0", "0", "0"]].map((r) => (
                  <tr key={r[0]} className="border-b last:border-0">
                    <td className="py-2 pr-4 font-medium">{r[0]}</td><td className="py-2 pr-4">{r[1]}</td>
                    <td className="py-2 pr-4">{r[2]}</td><td className="py-2 font-semibold text-ok">{r[3]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ProgressionChart stages={progression} />
          <div className="rounded-xl border-l-4 border-primary bg-muted/40 p-4">
            <strong>The headline lesson:</strong> the v2 prompt told the model to escalate the
            heart-failure weight trend — and it still wouldn&apos;t reliably. A safety-critical threshold
            belongs in a <strong>deterministic rule, not a prompt</strong>. The trend guardrail (rising
            weight ≥2.5 kg → Urgent) fixed urgency accuracy 0.80 → 1.00.
          </div>
        </Section>

        {/* Evaluation */}
        <Section id="evaluation" title="6 · Evaluation framework & results">
          <p>
            The full pipeline runs against all five scenarios, scored on urgency, key-fact coverage,
            citation discipline, and hallucinations, plus 101 automated tests.
          </p>
          <pre className="overflow-x-auto rounded-xl border bg-foreground/[0.04] p-4 font-mono text-xs leading-relaxed text-foreground/80">
{EVAL_TEXT}
          </pre>
          <Shot src="/assets/site-evaluation.png" alt="Evaluation dashboard" />
        </Section>

        {/* Safety */}
        <Section id="safety" title="7 · Safety guardrails">
          <ul className="list-disc space-y-1.5 pl-5">
            <li><strong>Deterministic severity floor</strong> — final urgency = max(LLM, rule); danger is never silently downgraded.</li>
            <li><strong>Weight-trend guardrail</strong> — rapid weight gain escalates to Urgent (HF red flag).</li>
            <li><strong>Critical escalation before synthesis</strong> — flagged for a human before the brief is assembled.</li>
            <li><strong>Graceful degradation</strong> + a full <strong>audit log</strong> of every step.</li>
            <li><strong>Code-level guardrails</strong> over model output (patient id, timestamps, citations).</li>
          </ul>
        </Section>

        {/* Anti-hallucination */}
        <Section id="anti-hallucination" title="8 · Anti-hallucination & uncertainty">
          <p>
            The Synthesis agent receives an explicit <strong>ALLOWED SOURCES</strong> list compiled from
            the real upstream outputs; every analytical claim must cite one, validated in code. Result:{" "}
            <strong>0 hallucinated citations, 100% citation coverage</strong> across all scenarios.
            Uncertainty is a first-class field — the EHR agent flags missing data instead of inventing
            it (e.g. &quot;no recent in-clinic BP readings in the EHR&quot;), and confidence is calibrated down
            when data is sparse.
          </p>
          <Shot src="/assets/site-demo.png" alt="Interactive demo: pipeline trace and cited brief" />
        </Section>

        {/* Lessons */}
        <Section id="lessons" title="9 · Lessons learned">
          <ul className="list-disc space-y-1.5 pl-5">
            <li>Prompt engineering for reasoning/tone/structure; <strong>deterministic rules for hard safety floors</strong>.</li>
            <li>Citations baked into schemas make anti-hallucination <strong>enforceable, not hopeful</strong>.</li>
            <li>System metadata must be set in code — models will fill it with training-cutoff guesses.</li>
            <li>Soft metrics fluctuate run-to-run; criteria-based metrics stay stable.</li>
            <li>Prompt engineering is, at its best, <strong>systems engineering</strong>.</li>
          </ul>
        </Section>

        {/* Ethics */}
        <Section id="ethics" title="10 · Ethics & limitations">
          <div className="flex items-start gap-2 rounded-xl border border-urgency-urgent/30 bg-urgency-urgent/10 p-4 text-sm">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-urgency-urgent" />
            <span>
              Not a medical device. All patient data is fully simulated (no real PHI). Clinician-in-the-loop
              always — the system surfaces context and never diagnoses or acts autonomously. Known limits:
              model variability, a small synthetic evaluation set, rubric-based (not clinician-validated)
              scoring, and heuristic guardrail thresholds.
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            The complete write-up — including all prompt texts, schemas, worked briefs, and appendices —
            is in the downloadable Markdown above and across the project&apos;s <code>docs/</code> folder.
          </p>
        </Section>
      </div>
    </div>
  );
}
