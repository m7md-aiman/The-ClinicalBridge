"use client";

import { motion } from "framer-motion";
import { Activity, Brain, ClipboardList, FileSearch, ShieldCheck } from "lucide-react";
import * as React from "react";

const node =
  "rounded-2xl border bg-card px-4 py-3 text-center shadow-sm";

function Node({
  icon,
  title,
  subtitle,
  delay,
  accent,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  delay: number;
  accent?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay }}
      className={node}
    >
      <div
        className={`mx-auto mb-1.5 grid h-9 w-9 place-items-center rounded-lg ${
          accent ? "bg-primary text-primary-foreground" : "bg-muted text-primary"
        }`}
      >
        {icon}
      </div>
      <div className="text-sm font-semibold">{title}</div>
      <div className="text-xs text-muted-foreground">{subtitle}</div>
    </motion.div>
  );
}

function Arrow() {
  return <div className="hidden text-2xl text-muted-foreground md:block">→</div>;
}

export function ArchitectureDiagram() {
  return (
    <div className="rounded-2xl border bg-muted/30 p-6">
      <div className="grid items-center gap-4 md:grid-cols-[auto_auto_auto_auto_auto_auto_auto]">
        <Node icon={<Activity className="h-4 w-4" />} title="RPM Alert" subtitle="trigger" delay={0} />
        <Arrow />
        <Node icon={<ClipboardList className="h-4 w-4" />} title="Triage" subtitle="urgency + queries" delay={0.1} accent />
        <Arrow />
        <div className="grid gap-3">
          <Node icon={<FileSearch className="h-4 w-4" />} title="EHR Retrieval" subtitle="RAG over records" delay={0.2} />
          <Node icon={<ClipboardList className="h-4 w-4" />} title="Anamnesis" subtitle="self-report" delay={0.25} />
        </div>
        <Arrow />
        <Node icon={<Brain className="h-4 w-4" />} title="Synthesis" subtitle="cited brief" delay={0.35} accent />
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="mt-5 flex items-center justify-center gap-2 rounded-xl border border-dashed bg-card/60 px-4 py-2 text-xs text-muted-foreground"
      >
        <ShieldCheck className="h-4 w-4 text-primary" />
        Orchestrator — parallel dispatch, deterministic safety guardrails, escalation &amp; audit log
      </motion.div>
    </div>
  );
}
