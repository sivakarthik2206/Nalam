"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useFamilyDashboard } from "@/lib/queries";
import {
  Heart,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Pill,
  Sparkles,
  Calendar,
  ShieldCheck,
  RefreshCw,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { formatDate, formatTime } from "@/lib/utils";

export default function FamilyDashboardPage() {
  const params = useParams();
  const patientId = (params?.patientId as string) || "";

  const { data, isLoading, dataUpdatedAt } = useFamilyDashboard(patientId);

  const [lastUpdatedText, setLastUpdatedText] = useState("Just now");

  useEffect(() => {
    if (dataUpdatedAt) {
      const date = new Date(dataUpdatedAt);
      setLastUpdatedText(
        date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      );
    }
  }, [dataUpdatedAt]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-amber-50/30 py-12 px-4 sm:px-6">
        <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
          <div className="h-28 bg-white rounded-3xl border border-amber-100 shadow-xs" />
          <div className="h-48 bg-white rounded-3xl border border-amber-100 shadow-xs" />
          <div className="h-56 bg-white rounded-3xl border border-amber-100 shadow-xs" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-amber-50/30 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-3xl border border-amber-100 p-8 text-center shadow-sm">
          <div className="w-14 h-14 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
            <Heart className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-slate-800">Care Link Not Found</h2>
          <p className="text-xs text-slate-500 mt-2 leading-relaxed">
            This private family dashboard link is either invalid or inactive. Please contact
            the dispensing clinic or pharmacy.
          </p>
        </div>
      </div>
    );
  }

  // Greeting title based on language
  const greetingTitle =
    data.patient_language === "tamil"
      ? `${data.patient_name} (Amma)'s Health Update`
      : data.patient_language === "hindi"
      ? `${data.patient_name} (Maata) ka Health Update`
      : `${data.patient_name}'s Health Update`;

  // Doses calculation
  const todayList = data.today || [];
  const takenCount = todayList.filter((d) => d.status === "taken").length;
  const totalToday = todayList.length;

  // 7-day bar chart data
  const weeklyData = (data.trend || []).slice(-7).map((d) => {
    return {
      date: formatDate(d.date, "EEE"),
      fullDate: formatDate(d.date, "MMM d"),
      score: d.score,
    };
  });

  // Recent 5 alerts
  const recentAlerts = (data.recent_alerts || []).slice(0, 5);

  return (
    <div className="min-h-screen bg-[#faf8f5] text-slate-800 font-sans py-8 sm:py-12 px-4 sm:px-6 lg:px-8 selection:bg-emerald-100">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* HEADER */}
        <header className="bg-white rounded-3xl border border-emerald-100/70 p-6 sm:p-8 shadow-sm">
          <div className="flex items-center justify-between pb-4 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-2xl bg-emerald-600 flex items-center justify-center text-white shadow-xs">
                <Heart className="w-5 h-5 fill-white text-white" />
              </div>
              <span className="font-bold text-slate-900 text-sm tracking-tight">
                Nalam Care
              </span>
              <span className="text-xs text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-full font-semibold border border-emerald-200">
                Family Dashboard
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Live &bull; {lastUpdatedText}</span>
            </div>
          </div>

          <div className="mt-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                {greetingTitle}
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 font-medium">
                Daily check-ins powered by automated AI voice calls in{" "}
                <span className="capitalize text-emerald-700 font-bold">
                  {data.patient_language}
                </span>
              </p>
            </div>

            {data.next_scheduled_call && (
              <div className="p-3 rounded-2xl bg-emerald-50/70 border border-emerald-200/60 text-xs text-emerald-900 shrink-0">
                <p className="text-[10px] uppercase font-bold text-emerald-700 tracking-wider">
                  Next Phone Check-in
                </p>
                <p className="font-bold text-sm mt-0.5">
                  {formatDate(data.next_scheduled_call, "h:mm a")} today
                </p>
              </div>
            )}
          </div>
        </header>

        {/* SECTION 1: TODAY'S MEDICINES */}
        <section className="space-y-4">
          <div className="flex items-center justify-between px-1">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Today&apos;s Medicines
              </h2>
              <p className="text-xs text-slate-500 font-medium">
                Status reported during today&apos;s scheduled reminder calls
              </p>
            </div>
            {totalToday > 0 && (
              <div className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-100 text-emerald-800">
                {takenCount} of {totalToday} doses taken
              </div>
            )}
          </div>

          {todayList.length === 0 ? (
            <div className="p-8 text-center bg-white rounded-3xl border border-slate-200 text-xs text-slate-400">
              No medications scheduled for today.
            </div>
          ) : (
            <div className="space-y-3">
              {todayList.map((item, index) => {
                const medName = item.medication_name || item.name || "Medicine";
                const isTaken = item.status === "taken";
                const isMissed = item.status === "not_taken";
                const isPending = item.status === "pending";

                return (
                  <Card
                    key={`${item.time_slot}-${medName}-${index}`}
                    className={`rounded-2xl border transition-all ${
                      isTaken
                        ? "bg-white border-emerald-200 shadow-xs"
                        : isMissed
                        ? "bg-rose-50/40 border-rose-200 shadow-xs"
                        : "bg-white border-slate-200 shadow-2xs"
                    }`}
                  >
                    <CardContent className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div className="flex items-start gap-3.5">
                        <div
                          className={`w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 ${
                            isTaken
                              ? "bg-emerald-100 text-emerald-700"
                              : isMissed
                              ? "bg-rose-100 text-rose-700"
                              : "bg-amber-100 text-amber-700"
                          }`}
                        >
                          <Pill className="w-5 h-5" />
                        </div>

                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-base text-slate-900">
                              {medName}
                            </h3>
                            <Badge
                              variant="outline"
                              className="text-[10px] font-semibold bg-slate-50 border-slate-200"
                            >
                              {item.time_slot}
                            </Badge>
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5">
                            Take with water as prescribed
                          </p>
                        </div>
                      </div>

                      {/* Large friendly status badge */}
                      <div className="shrink-0 self-end sm:self-center">
                        {isTaken && (
                          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            <span>Taken Confirmed</span>
                          </div>
                        )}
                        {isMissed && (
                          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-bold">
                            <XCircle className="w-4 h-4 text-rose-600" />
                            <span>Missed Dose</span>
                          </div>
                        )}
                        {isPending && (
                          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-bold">
                            <Clock className="w-4 h-4 text-amber-600" />
                            <span>Upcoming Call</span>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>

        {/* SECTION 2: THIS WEEK (7-Bar Chart) */}
        <section className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-sm space-y-4">
          <div className="flex items-baseline justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">This Week</h2>
              <p className="text-xs text-slate-500 font-medium">
                Last 7 days adherence consistency
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-black text-emerald-700">
                {data.adherence_score_7d}%
              </span>
              <p className="text-[11px] text-slate-400 font-medium">Weekly adherence</p>
            </div>
          </div>

          <div className="h-48 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklyData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={{ stroke: "#f1f5f9" }}
                  tick={{ fill: "#64748b", fontSize: 12, fontWeight: 600 }}
                />
                <YAxis
                  domain={[0, 100]}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "#94a3b8", fontSize: 10 }}
                  tickFormatter={(val) => `${val}%`}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload;
                      return (
                        <div className="bg-slate-900 text-white px-3 py-1.5 rounded-xl text-xs font-semibold shadow-lg">
                          <p className="text-slate-300">{item.fullDate}</p>
                          <p className="text-emerald-400 text-sm font-bold">
                            Score: {item.score}%
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                  {weeklyData.map((entry, index) => {
                    const color =
                      entry.score >= 80
                        ? "#059669"
                        : entry.score >= 60
                        ? "#d97706"
                        : "#e11d48";
                    return <Cell key={`cell-${index}`} fill={color} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block" />
                Good (&#x2265;80%)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
                Moderate (60-79%)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
                Low (&lt;60%)
              </span>
            </div>
            <span className="font-semibold text-slate-800">
              Weekly Adherence: {data.adherence_score_7d}%
            </span>
          </div>
        </section>

        {/* SECTION 3: MEDICATIONS & REMAINING SUPPLY */}
        <section className="space-y-4">
          <div className="px-1">
            <h2 className="text-lg font-bold text-slate-900">Active Prescriptions</h2>
            <p className="text-xs text-slate-500 font-medium">
              Daily dosage instructions and remaining days of supply
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {(data.medications || []).map((med) => {
              const daysLeft = med.days_until_refill ?? 30;
              const isUrgent = daysLeft <= 5;

              return (
                <div
                  key={med.name}
                  className={`p-5 rounded-3xl border bg-white shadow-xs flex flex-col justify-between ${
                    isUrgent ? "border-amber-300 bg-amber-50/20" : "border-slate-200"
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-bold text-slate-900 text-base">
                        {med.name}
                      </h3>
                      {isUrgent && (
                        <Badge variant="outline" className="text-[10px] font-bold bg-amber-100 text-amber-800 border-amber-300">
                          Refill Soon
                        </Badge>
                      )}
                    </div>

                    <p className="text-xs text-slate-600 mt-1">
                      Dosage: <strong>{med.dosage}</strong> &bull; {med.meal_timing.replace("_", " ")}
                    </p>

                    <div className="mt-3 flex items-center gap-1.5 flex-wrap">
                      <span className="text-[11px] text-slate-400 font-medium">Timing:</span>
                      {(med.frequency || []).map((f) => (
                        <Badge
                          key={f}
                          variant="outline"
                          className="capitalize text-[10px] bg-slate-50 text-slate-700 border-slate-200"
                        >
                          {f}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                    <span className="text-slate-500">Estimated Supply:</span>
                    <span className={`font-bold ${isUrgent ? "text-amber-800" : "text-slate-800"}`}>
                      {med.pills_remaining !== null && med.pills_remaining !== undefined
                        ? `${med.pills_remaining} pills (~${daysLeft} days)`
                        : `~${daysLeft} days remaining`}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* SECTION 4: RECENT ALERTS */}
        <section className="space-y-4">
          <div className="px-1">
            <h2 className="text-lg font-bold text-slate-900">Recent Health Notes</h2>
            <p className="text-xs text-slate-500 font-medium">
              Important alerts recorded during daily voice conversations
            </p>
          </div>

          {recentAlerts.length === 0 ? (
            <div className="p-6 rounded-3xl bg-white border border-slate-200 text-center text-xs text-slate-400">
              No recent medical alerts or side effect reports.
            </div>
          ) : (
            <div className="space-y-2.5">
              {recentAlerts.map((alert) => {
                const isSideEffect = alert.alert_type === "side_effect" || alert.severity === "critical";
                const isMissed = alert.alert_type === "missed_dose" || alert.severity === "warning";

                return (
                  <div
                    key={alert.id}
                    className={`p-4 rounded-2xl border flex items-start gap-3 ${
                      isSideEffect
                        ? "bg-rose-50 border-rose-200 text-rose-900"
                        : isMissed
                        ? "bg-amber-50 border-amber-200 text-amber-900"
                        : "bg-white border-slate-200 text-slate-800"
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">
                      {isSideEffect ? (
                        <AlertCircle className="w-5 h-5 text-rose-600" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-amber-600" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold uppercase tracking-wider">
                          {alert.alert_type.replace("_", " ")}
                        </span>
                        <span className="text-[11px] opacity-70">
                          {formatDate(alert.created_at, "MMM d, h:mm a")}
                        </span>
                      </div>
                      <p className="text-xs mt-1 font-medium leading-relaxed">
                        {alert.message}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* FOOTER */}
        <footer className="pt-6 pb-8 border-t border-slate-200/80 text-center space-y-2">
          <div className="flex items-center justify-center gap-1.5 text-xs font-bold text-slate-600">
            <span>Powered by Nalam</span>
            <Heart className="w-3.5 h-3.5 text-emerald-600 fill-emerald-600" />
          </div>
          <p className="text-[11px] text-slate-400">
            Data refreshes automatically every 60 seconds. Voice calls dial directly from
            the Nalam Bolna Agent.
          </p>
        </footer>
      </div>
    </div>
  );
}
