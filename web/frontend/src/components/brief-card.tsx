import { AlertCircle, FileText } from "lucide-react";
import type { Brief } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { UrgencyBadge } from "@/components/urgency-badge";
import { cn } from "@/lib/utils";

function confidenceClasses(level: string): string {
  switch (level) {
    case "High":
      return "text-ok border-ok/30 bg-ok/10";
    case "Moderate":
      return "text-urgency-urgent border-urgency-urgent/30 bg-urgency-urgent/10";
    default:
      return "text-muted-foreground border-border bg-muted";
  }
}

function SourceChips({ sources }: { sources: string[] }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {sources.map((s) => (
        <span
          key={s}
          className="rounded-md border bg-muted/60 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground"
        >
          {s}
        </span>
      ))}
    </div>
  );
}

function Section({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        <span className="grid h-5 w-5 place-items-center rounded bg-muted text-[11px] text-foreground">
          {n}
        </span>
        {title}
      </h4>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export function BriefCard({ brief, label }: { brief: Brief; label?: string }) {
  return (
    <Card>
      <CardContent className="space-y-6 pt-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            <span className="font-semibold">
              Clinical Context Brief{label ? ` · ${label}` : ""}
            </span>
            <span className="text-sm text-muted-foreground">Patient {brief.patient_id}</span>
          </div>
          <div className="flex items-center gap-2">
            <UrgencyBadge level={brief.urgency} />
            <span
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs font-medium",
                confidenceClasses(brief.overall_confidence),
              )}
            >
              {brief.overall_confidence} confidence
            </span>
          </div>
        </div>

        <Section n={1} title="Alert Summary">
          <p className="text-sm">{brief.alert_summary}</p>
        </Section>

        <Section n={2} title="Patient Snapshot">
          <p className="text-sm">{brief.patient_snapshot}</p>
        </Section>

        <Section n={3} title="Contextual Analysis">
          <ul className="space-y-3">
            {brief.contextual_analysis.map((s, i) => (
              <li key={i} className="text-sm">
                {s.statement}
                <SourceChips sources={s.sources} />
              </li>
            ))}
          </ul>
        </Section>

        <Section n={4} title="Risk Assessment">
          <ul className="space-y-3">
            {brief.risk_assessment.map((s, i) => (
              <li key={i} className="text-sm">
                {s.statement}
                <SourceChips sources={s.sources} />
              </li>
            ))}
          </ul>
        </Section>

        <Section n={5} title="Recommended Actions">
          <ul className="space-y-2.5">
            {brief.recommended_actions.map((a, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <span
                  className={cn(
                    "mt-0.5 shrink-0 rounded-md border px-1.5 py-0.5 text-[11px] font-medium",
                    confidenceClasses(a.confidence),
                  )}
                >
                  {a.confidence}
                </span>
                <div>
                  {a.action}
                  <SourceChips sources={a.supporting_evidence} />
                </div>
              </li>
            ))}
          </ul>
        </Section>

        <Section n={6} title="Uncertainties & Gaps">
          {brief.uncertainties_and_gaps.length ? (
            <ul className="space-y-1.5">
              {brief.uncertainties_and_gaps.map((u, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-urgency-urgent" />
                  {u}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">None flagged.</p>
          )}
        </Section>

        {brief.cited_sources?.length > 0 && (
          <div className="border-t pt-3 text-xs text-muted-foreground">
            Sources consulted: {brief.cited_sources.join(" · ")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
