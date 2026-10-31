"use client";

import { AlertResponse } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { AlertCircle, AlertTriangle, Info, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface AlertHistoryProps {
  alerts: AlertResponse[];
}

export function AlertHistory({ alerts }: AlertHistoryProps) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl">
        <CheckCircle2 className="w-7 h-7 text-emerald-500 mx-auto mb-1.5" />
        <p className="text-sm font-semibold text-slate-700">No Health Alerts</p>
        <p className="text-xs text-slate-400 mt-0.5">
          Everything is running smoothly with no reported complications.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={`p-4 rounded-xl border flex items-start gap-3 ${
            alert.severity === "critical"
              ? "bg-rose-50/50 border-rose-200"
              : alert.severity === "warning"
              ? "bg-amber-50/50 border-amber-200"
              : "bg-white border-slate-200"
          }`}
        >
          <div className="mt-0.5 shrink-0">
            {alert.severity === "critical" ? (
              <AlertCircle className="w-5 h-5 text-rose-600" />
            ) : alert.severity === "warning" ? (
              <AlertTriangle className="w-5 h-5 text-amber-600" />
            ) : (
              <Info className="w-5 h-5 text-sky-600" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
                {alert.alert_type.replace("_", " ")}
              </span>
              <span className="text-[11px] text-slate-400">
                {formatDate(alert.created_at, "MMM d, h:mm a")}
              </span>
            </div>
            <p className="text-xs text-slate-700 font-medium mt-1 leading-snug">
              {alert.message}
            </p>
            {alert.alert_type === "side_effect" && (
              <p className="text-[11px] text-rose-700 font-bold mt-1.5">
                Doctor consultation recommended.
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
