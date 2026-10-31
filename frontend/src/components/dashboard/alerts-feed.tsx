"use client";

import { AlertResponse } from "@/lib/types";
import { getAlertSeverityColor, formatDate } from "@/lib/utils";
import {
  AlertCircle,
  AlertTriangle,
  Info,
  PhoneMissed,
  Pill,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useMarkAlertRead } from "@/lib/queries";
import Link from "next/link";

interface AlertsFeedProps {
  alerts: AlertResponse[];
  isLoading?: boolean;
}

export function AlertsFeed({ alerts, isLoading }: AlertsFeedProps) {
  const markRead = useMarkAlertRead();

  function getAlertIcon(type: string, severity: string) {
    switch (type) {
      case "side_effect":
        return <AlertCircle className="w-4 h-4 text-rose-600" />;
      case "no_answer":
        return <PhoneMissed className="w-4 h-4 text-amber-600" />;
      case "stock_out":
      case "refill_due":
        return <Pill className="w-4 h-4 text-amber-600" />;
      default:
        return severity === "critical" ? (
          <AlertCircle className="w-4 h-4 text-rose-600" />
        ) : (
          <AlertTriangle className="w-4 h-4 text-amber-600" />
        );
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="text-center py-12 px-4 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
        <CheckCircle2 className="w-7 h-7 text-emerald-500 mx-auto mb-2" />
        <h4 className="text-sm font-semibold text-slate-700">All Clear</h4>
        <p className="text-xs text-slate-500 mt-0.5">
          No unhandled alerts or urgent escalations right now.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
      {alerts.map((alert) => {
        const sevStyle = getAlertSeverityColor(alert.severity);

        return (
          <div
            key={alert.id}
            className={`p-3 rounded-lg border transition-all ${
              alert.is_read
                ? "bg-slate-50/60 border-slate-200 opacity-70"
                : alert.severity === "critical"
                ? "bg-rose-50/40 border-rose-200 shadow-xs"
                : "bg-white border-slate-200 shadow-xs"
            }`}
          >
            <div className="flex items-start gap-2.5">
              <div className="mt-0.5 shrink-0">
                {getAlertIcon(alert.alert_type, alert.severity)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1">
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-1.5 py-0 font-bold uppercase tracking-wider ${sevStyle.badge}`}
                  >
                    {alert.alert_type.replace("_", " ")}
                  </Badge>
                  <span className="text-[10px] text-slate-400 shrink-0">
                    {formatDate(alert.created_at, "MMM d, h:mm a")}
                  </span>
                </div>
                <p className="text-xs text-slate-800 font-medium mt-1 leading-snug">
                  {alert.message}
                </p>
                <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-100 text-[11px]">
                  <Link
                    href={`/admin/patients/${alert.patient_id}`}
                    className="text-emerald-700 hover:underline font-semibold"
                  >
                    View Patient &rarr;
                  </Link>
                  {!alert.is_read && (
                    <button
                      onClick={() => markRead.mutate(alert.id)}
                      disabled={markRead.isPending}
                      className="text-slate-500 hover:text-slate-800 font-medium"
                    >
                      Dismiss
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
