import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type UrgencyLevel = "Critical" | "Urgent" | "Routine" | "Informational";

/** Tailwind classes for an urgency level (text + subtle background + border). */
export function urgencyClasses(level: string): string {
  switch (level) {
    case "Critical":
      return "text-urgency-critical border-urgency-critical/30 bg-urgency-critical/10";
    case "Urgent":
      return "text-urgency-urgent border-urgency-urgent/30 bg-urgency-urgent/10";
    case "Routine":
      return "text-urgency-routine border-urgency-routine/30 bg-urgency-routine/10";
    default:
      return "text-urgency-informational border-urgency-informational/30 bg-urgency-informational/10";
  }
}

export function urgencyDot(level: string): string {
  switch (level) {
    case "Critical":
      return "bg-urgency-critical";
    case "Urgent":
      return "bg-urgency-urgent";
    case "Routine":
      return "bg-urgency-routine";
    default:
      return "bg-urgency-informational";
  }
}
