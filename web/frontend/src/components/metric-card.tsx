import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";

export function MetricCard({
  icon,
  value,
  label,
  sub,
  good,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
  sub?: string;
  good?: boolean;
}) {
  return (
    <Card className="h-full">
      <CardContent className="pt-6">
        <div className={good ? "text-ok" : "text-primary"}>{icon}</div>
        <div className="mt-3 text-3xl font-semibold tracking-tight">{value}</div>
        <div className="text-sm font-medium">{label}</div>
        {sub && <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>}
      </CardContent>
    </Card>
  );
}
