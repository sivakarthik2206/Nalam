import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, parseISO, isValid } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format ISO or Date string into readable format.
 */
export function formatDate(
  dateString?: string | null,
  pattern: string = "MMM d, yyyy"
): string {
  if (!dateString) return "—";
  try {
    const parsed = typeof dateString === "string" ? parseISO(dateString) : dateString;
    if (!isValid(parsed)) return "—";
    return format(parsed, pattern);
  } catch {
    return "—";
  }
}

/**
 * Format relative or time string (e.g. 09:30 AM).
 */
export function formatTime(dateString?: string | null): string {
  if (!dateString) return "—";
  try {
    const parsed = parseISO(dateString);
    if (!isValid(parsed)) return "—";
    return format(parsed, "h:mm a");
  } catch {
    return "—";
  }
}

/**
 * Get adherence score color classification:
 * >= 80% -> green (emerald)
 * 60% - 79% -> amber
 * < 60% -> red
 */
export function getAdherenceColor(score: number): {
  text: string;
  bg: string;
  border: string;
  badge: string;
} {
  if (score >= 80) {
    return {
      text: "text-emerald-700",
      bg: "bg-emerald-50",
      border: "border-emerald-500",
      badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
    };
  }
  if (score >= 60) {
    return {
      text: "text-amber-700",
      bg: "bg-amber-50",
      border: "border-amber-500",
      badge: "bg-amber-100 text-amber-800 border-amber-200",
    };
  }
  return {
    text: "text-rose-700",
    bg: "bg-rose-50",
    border: "border-rose-500",
    badge: "bg-rose-100 text-rose-800 border-rose-200",
  };
}

/**
 * Status color for dose responses: taken, missed, pending, side_effect
 */
export function getDoseStatusColor(status: string): {
  badge: string;
  dot: string;
  label: string;
} {
  switch (status.toLowerCase()) {
    case "taken":
      return {
        badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
        dot: "bg-emerald-500",
        label: "Taken",
      };
    case "missed":
    case "not_taken":
      return {
        badge: "bg-rose-100 text-rose-800 border-rose-200",
        dot: "bg-rose-500",
        label: "Missed",
      };
    case "side_effect":
      return {
        badge: "bg-purple-100 text-purple-800 border-purple-200",
        dot: "bg-purple-500",
        label: "Side Effect",
      };
    case "stock_out":
      return {
        badge: "bg-orange-100 text-orange-800 border-orange-200",
        dot: "bg-orange-500",
        label: "Out of Stock",
      };
    case "no_answer":
      return {
        badge: "bg-slate-100 text-slate-800 border-slate-200",
        dot: "bg-slate-400",
        label: "No Answer",
      };
    case "pending":
    default:
      return {
        badge: "bg-amber-50 text-amber-800 border-amber-200",
        dot: "bg-amber-400",
        label: "Pending",
      };
  }
}

/**
 * Severity color for alerts: critical (red), warning (amber), info (blue)
 */
export function getAlertSeverityColor(severity: string): {
  badge: string;
  iconColor: string;
} {
  switch (severity.toLowerCase()) {
    case "critical":
      return {
        badge: "bg-rose-100 text-rose-800 border-rose-200",
        iconColor: "text-rose-600",
      };
    case "warning":
      return {
        badge: "bg-amber-100 text-amber-800 border-amber-200",
        iconColor: "text-amber-600",
      };
    case "info":
    default:
      return {
        badge: "bg-sky-100 text-sky-800 border-sky-200",
        iconColor: "text-sky-600",
      };
  }
}
