"use client";

import { FamilyDashboard } from "@/lib/types";
import { getAdherenceColor, formatDate, formatTime } from "@/lib/utils";
import { Heart, Globe, Clock, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface FamilyHeaderProps {
  data: FamilyDashboard;
}

export function FamilyHeader({ data }: FamilyHeaderProps) {
  const weeklyStyle = getAdherenceColor(data.adherence_score_7d);
  const monthlyStyle = getAdherenceColor(data.adherence_score_30d);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        {/* Patient and Kin Info */}
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-2xl bg-emerald-600 flex items-center justify-center text-white shrink-0 shadow-md shadow-emerald-700/20">
            <Heart className="w-7 h-7 fill-white text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                {data.patient_name}
              </h1>
              <Badge variant="outline" className="bg-emerald-50 text-emerald-800 border-emerald-200 text-xs capitalize">
                <Globe className="w-3 h-3 mr-1" />
                {data.patient_language}
              </Badge>
            </div>
            <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              Nalam Family Care Portal &bull; Daily voice check-ins active
            </p>
            {data.next_scheduled_call && (
              <p className="text-xs text-slate-600 font-medium mt-1 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                Next Check-in:{" "}
                <strong className="text-slate-800 font-semibold">
                  {formatDate(data.next_scheduled_call, "EEE, MMM d")} at{" "}
                  {formatTime(data.next_scheduled_call)}
                </strong>
              </p>
            )}
          </div>
        </div>

        {/* 7d & 30d Score Badges */}
        <div className="flex items-center gap-3">
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-center min-w-[105px]">
            <span className="text-[10px] uppercase font-bold text-slate-500">
              7-Day Score
            </span>
            <div className={`text-2xl font-black mt-0.5 ${weeklyStyle.text}`}>
              {data.adherence_score_7d}%
            </div>
            <span className="text-[10px] text-slate-400 font-medium">Weekly</span>
          </div>

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-center min-w-[105px]">
            <span className="text-[10px] uppercase font-bold text-slate-500">
              30-Day Score
            </span>
            <div className={`text-2xl font-black mt-0.5 ${monthlyStyle.text}`}>
              {data.adherence_score_30d}%
            </div>
            <span className="text-[10px] text-slate-400 font-medium">Monthly</span>
          </div>
        </div>
      </div>
    </div>
  );
}
