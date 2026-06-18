"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ProgressionStage } from "@/lib/types";

export function ProgressionChart({ stages }: { stages: ProgressionStage[] }) {
  const data = stages.map((s) => ({
    stage: s.stage,
    "Pass rate": Math.round(s.pass_rate * 100),
    "Urgency accuracy": Math.round(s.urgency_accuracy * 100),
    "Key-fact coverage": Math.round(s.mean_must_include_coverage * 100),
  }));

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 16, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="stage" tick={{ fontSize: 12, fill: "var(--muted-foreground)" }} />
          <YAxis
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
          />
          <Tooltip
            formatter={(v) => `${v}%`}
            contentStyle={{
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              color: "var(--foreground)",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="Pass rate" stroke="#0d9488" strokeWidth={2.5} dot={{ r: 4 }} />
          <Line type="monotone" dataKey="Urgency accuracy" stroke="#0284c7" strokeWidth={2.5} dot={{ r: 4 }} />
          <Line type="monotone" dataKey="Key-fact coverage" stroke="#d97706" strokeWidth={2.5} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
