import { Badge } from "@/components/ui/badge";
import { cn, urgencyClasses, urgencyDot } from "@/lib/utils";

export function UrgencyBadge({ level, className }: { level: string; className?: string }) {
  return (
    <Badge className={cn(urgencyClasses(level), "font-semibold", className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", urgencyDot(level))} />
      {level}
    </Badge>
  );
}
