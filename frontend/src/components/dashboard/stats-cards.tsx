"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Users, Activity, AlertTriangle, Pill } from "lucide-react";
import { getAdherenceColor } from "@/lib/utils";

interface StatsCardsProps {
  totalPatients: number;
  avgAdherence7d: number;
  criticalAlertsToday: number;
  refillsDue: number;
  isLoading?: boolean;
}

export function StatsCards({
  totalPatients,
  avgAdherence7d,
  criticalAlertsToday,
  refillsDue,
  isLoading,
}: StatsCardsProps) {
  const adherenceStyle = getAdherenceColor(avgAdherence7d);
  const hasPatients = totalPatients > 0;

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse bg-white border-slate-200">
            <CardContent className="p-6">
              <div className="h-4 bg-slate-100 rounded w-24 mb-3" />
              <div className="h-8 bg-slate-200 rounded w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Patients */}
      <Card className="bg-white border-slate-200 border-l-4 border-l-emerald-600 shadow-sm hover:shadow transition-shadow">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Patients
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {totalPatients}
              </span>
              <span className="text-xs text-emerald-600 font-medium">Enrolled</span>
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600">
            <Users className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>

      {/* Average Adherence (7d) */}
      <Card
        className={`bg-white border-slate-200 border-l-4 ${adherenceStyle.border} shadow-sm hover:shadow transition-shadow`}
      >
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Avg. 7d Adherence
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {hasPatients ? `${avgAdherence7d}%` : "—"}
              </span>
              <span className={`text-xs font-medium ${adherenceStyle.text}`}>
                {!hasPatients
                  ? "No patients"
                  : avgAdherence7d >= 80
                  ? "Optimal"
                  : avgAdherence7d >= 60
                  ? "Moderate"
                  : "Attention"}
              </span>
            </div>
          </div>
          <div
            className={`w-11 h-11 rounded-xl ${adherenceStyle.bg} flex items-center justify-center ${adherenceStyle.text}`}
          >
            <Activity className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>

      {/* Critical Alerts Today */}
      <Card className="bg-white border-slate-200 border-l-4 border-l-rose-500 shadow-sm hover:shadow transition-shadow">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Critical Alerts Today
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {criticalAlertsToday}
              </span>
              <span
                className={`text-xs font-medium ${
                  criticalAlertsToday > 0 ? "text-rose-600 font-semibold" : "text-slate-400"
                }`}
              >
                {criticalAlertsToday > 0 ? "Requires Action" : "None pending"}
              </span>
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-rose-50 flex items-center justify-center text-rose-600">
            <AlertTriangle className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>

      {/* Refills Due */}
      <Card className="bg-white border-slate-200 border-l-4 border-l-amber-500 shadow-sm hover:shadow transition-shadow">
        <CardContent className="p-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Refills Due (&le; 5d)
            </p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl sm:text-3xl font-bold text-slate-900">
                {hasPatients ? refillsDue : "—"}
              </span>
              <span className="text-xs text-amber-600 font-medium">Patients</span>
            </div>
          </div>
          <div className="w-11 h-11 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600">
            <Pill className="w-5 h-5" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
