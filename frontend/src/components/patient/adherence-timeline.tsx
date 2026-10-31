"use client";

import { AdherenceLogResponse } from "@/lib/types";
import { getDoseStatusColor, formatDate, formatTime } from "@/lib/utils";
import { Clock, Phone, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface AdherenceTimelineProps {
  logs: AdherenceLogResponse[];
  isLoading?: boolean;
}

export function AdherenceTimeline({ logs, isLoading }: AdherenceTimelineProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="p-8 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
        <Clock className="w-8 h-8 text-slate-300 mx-auto mb-2" />
        <h4 className="text-sm font-bold text-slate-700">No Call History</h4>
        <p className="text-xs text-slate-400 mt-0.5">
          Outbound call records and voice transcripts will appear here in chronological order.
        </p>
      </div>
    );
  }

  return (
    <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
      {logs.map((log) => {
        const statusStyle = getDoseStatusColor(log.outcome);

        return (
          <div key={log.id} className="relative group">
            {/* Dot Indicator on line */}
            <span
              className={`absolute -left-6 top-1.5 w-4 h-4 rounded-full border-2 border-white ${statusStyle.dot} shadow-xs`}
            />

            <div className="p-3.5 rounded-xl border border-slate-200 bg-white shadow-2xs">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className={`text-xs px-2 py-0.5 font-bold ${statusStyle.badge}`}
                  >
                    {statusStyle.label}
                  </Badge>
                  {log.scheduled_time_slot && (
                    <span className="text-xs font-semibold text-slate-700 capitalize">
                      {log.scheduled_time_slot} Slot
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                  <Clock className="w-3 h-3" />
                  <span>
                    {formatDate(log.call_time, "MMM d, yyyy")} at{" "}
                    {formatTime(log.call_time)}
                  </span>
                </div>
              </div>

              {/* Side effect details if any */}
              {log.side_effect_details && (
                <div className="mt-2.5 p-2 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold">Reported Symptom: </span>
                    {log.side_effect_details}
                  </div>
                </div>
              )}

              {/* Call metadata */}
              <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span>
                  {log.call_duration_seconds
                    ? `Duration: ${log.call_duration_seconds}s`
                    : "Bolna Voice Call"}
                </span>
                {log.follow_up_needed && (
                  <span className="text-amber-600 font-semibold">
                    {log.follow_up_completed ? "✓ Follow-up completed" : "⚠ Follow-up scheduled"}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
