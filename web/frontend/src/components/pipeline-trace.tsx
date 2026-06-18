"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bell,
  Brain,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  Gauge,
  Loader2,
  MessageSquareText,
  TrendingUp,
} from "lucide-react";
import * as React from "react";
import type { SessionEvent } from "@/lib/types";

const META: Record<string, { label: string; icon: React.ReactNode }> = {
  alert_received: { label: "Alert received", icon: <Bell className="h-4 w-4" /> },
  severity_floor: { label: "Severity floor (rule-based)", icon: <Gauge className="h-4 w-4" /> },
  trend_guardrail: { label: "Trend guardrail", icon: <TrendingUp className="h-4 w-4" /> },
  triage: { label: "Triage agent", icon: <ClipboardList className="h-4 w-4" /> },
  escalation: { label: "Escalation", icon: <AlertTriangle className="h-4 w-4" /> },
  ehr_retrieval: { label: "EHR retrieval agent", icon: <FileSearch className="h-4 w-4" /> },
  anamnesis: { label: "Anamnesis agent", icon: <MessageSquareText className="h-4 w-4" /> },
  synthesis: { label: "Synthesis agent", icon: <Brain className="h-4 w-4" /> },
  complete: { label: "Complete", icon: <CheckCircle2 className="h-4 w-4" /> },
};

export function PipelineTrace({
  events,
  running = false,
}: {
  events: SessionEvent[];
  running?: boolean;
}) {
  return (
    <ol className="relative space-y-3 pl-2">
      <AnimatePresence initial>
        {events.map((e, i) => {
          const meta = META[e.step] ?? { label: e.step, icon: <CheckCircle2 className="h-4 w-4" /> };
          const isEscalation = e.step === "escalation";
          return (
            <motion.li
              key={`${e.step}-${i}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.35, delay: running ? 0 : i * 0.12 }}
              className="flex gap-3"
            >
              <div
                className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg ${
                  isEscalation
                    ? "bg-urgency-critical/15 text-urgency-critical"
                    : "bg-muted text-primary"
                }`}
              >
                {meta.icon}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium">{meta.label}</div>
                <div className="text-sm text-muted-foreground">{e.summary}</div>
              </div>
            </motion.li>
          );
        })}
      </AnimatePresence>
      {running && (
        <li className="flex items-center gap-3 text-sm text-muted-foreground">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-muted">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          </div>
          Running…
        </li>
      )}
    </ol>
  );
}
