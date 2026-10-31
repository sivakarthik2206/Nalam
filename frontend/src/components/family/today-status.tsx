"use client";

import { TodayStatus as TodayStatusType } from "@/lib/types";
import { getDoseStatusColor } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { CheckCircle2, Clock, AlertCircle, XCircle, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface TodayStatusProps {
  items: TodayStatusType[];
}

export function TodayStatus({ items }: TodayStatusProps) {
  if (!items || items.length === 0) {
    return (
      <Card className="bg-white border-slate-200">
        <CardContent className="p-6 text-center text-slate-500 text-sm">
          No medication doses scheduled for today.
        </CardContent>
      </Card>
    );
  }

  const takenCount = items.filter((i) => i.status === "taken").length;

  return (
    <Card className="bg-white border-slate-200 shadow-sm overflow-hidden">
      <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
              <span>Today&apos;s Medication Progress</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                {takenCount} of {items.length} Taken
              </span>
            </CardTitle>
            <CardDescription className="text-xs text-slate-500 mt-0.5">
              Live updates recorded during automated phone check-ins
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {items.map((item, idx) => {
            const medName = item.medication_name || item.name || "Medication";
            const statusStyle = getDoseStatusColor(item.status);

            const isTaken = item.status === "taken";
            const isMissed = item.status === "not_taken";

            return (
              <div
                key={`${item.time_slot}-${medName}-${idx}`}
                className={`p-4 rounded-xl border flex flex-col justify-between transition-all ${
                  isTaken
                    ? "bg-emerald-50/60 border-emerald-200"
                    : isMissed
                    ? "bg-rose-50/60 border-rose-200"
                    : "bg-slate-50/70 border-slate-200"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="text-xs uppercase font-bold tracking-wider text-slate-500">
                      {item.time_slot}
                    </span>
                    <Badge
                      variant="outline"
                      className={`text-[10px] font-bold ${statusStyle.badge}`}
                    >
                      {statusStyle.label}
                    </Badge>
                  </div>
                  <h4 className="font-bold text-slate-900 text-sm mt-1.5 leading-snug">
                    {medName}
                  </h4>
                </div>

                <div className="mt-3 flex items-center gap-1.5 text-xs font-medium">
                  {isTaken ? (
                    <span className="flex items-center gap-1 text-emerald-700">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      Confirmed Taken
                    </span>
                  ) : isMissed ? (
                    <span className="flex items-center gap-1 text-rose-700">
                      <XCircle className="w-4 h-4 text-rose-600" />
                      Missed Dose
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-amber-700">
                      <Clock className="w-4 h-4 text-amber-600" />
                      Upcoming / Pending
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
