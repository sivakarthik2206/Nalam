"use client";

import { useParams } from "next/navigation";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Heart,
  Pill,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useAdherenceHistory, useDailyStatus, useFamilyDashboard } from "@/lib/queries";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getApiErrorMessage, getAdherenceColor, formatDate, formatMealTiming, formatTime } from "@/lib/utils";

type DoseStatus = "taken" | "missed" | "pending" | "side_effect";

interface FamilyDose {
  medicationName: string;
  timeSlot: string;
  mealTiming?: string;
  status: DoseStatus;
  loggedAt?: string | null;
}

function statusCopy(status: DoseStatus): { label: string; className: string; icon: typeof CheckCircle2 } {
  switch (status) {
    case "taken":
      return { label: "Taken confirmed", className: "border-emerald-200 bg-emerald-50 text-emerald-800", icon: CheckCircle2 };
    case "missed":
      return { label: "Missed dose", className: "border-rose-200 bg-rose-50 text-rose-800", icon: XCircle };
    case "side_effect":
      return { label: "Side effect reported", className: "border-violet-200 bg-violet-50 text-violet-800", icon: AlertCircle };
    default:
      return { label: "Awaiting check-in", className: "border-amber-200 bg-amber-50 text-amber-900", icon: Clock3 };
  }
}

function LoadingState() {
  return (
    <main className="min-h-screen bg-sky-50/60 px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-4xl space-y-5" aria-label="Loading family dashboard">
        {["header", "summary", "chart", "medications"].map((key) => (
          <div key={key} className="h-32 animate-pulse rounded-3xl border border-sky-100 bg-white" />
        ))}
      </div>
    </main>
  );
}

export default function FamilyDashboardPage() {
  const params = useParams<{ patientId: string }>();
  const patientId = params?.patientId ?? "";
  const familyQuery = useFamilyDashboard(patientId);
  const dailyQuery = useDailyStatus(patientId);
  const historyQuery = useAdherenceHistory(patientId, 7);
  const lastUpdatedText = familyQuery.dataUpdatedAt
    ? formatTime(new Date(familyQuery.dataUpdatedAt).toISOString())
    : "Not updated yet";

  if (familyQuery.isLoading) return <LoadingState />;

  if (familyQuery.isError || !familyQuery.data) {
    return (
      <main className="min-h-screen bg-sky-50/60 px-4 py-12 sm:px-6">
        <div className="mx-auto max-w-xl">
          <Alert variant="destructive">
            <AlertTitle>Family dashboard unavailable</AlertTitle>
            <AlertDescription className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <span>{getApiErrorMessage(familyQuery.error)}</span>
              <Button type="button" variant="outline" size="sm" onClick={() => familyQuery.refetch()}>
                <RefreshCw aria-hidden="true" />
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        </div>
      </main>
    );
  }

  const data = familyQuery.data;
  const dailyDoses: FamilyDose[] = dailyQuery.data?.medications.map((dose) => ({
    medicationName: dose.medication_name ?? dose.name,
    timeSlot: dose.time_slot,
    mealTiming: dose.meal_timing,
    status: dose.status,
    loggedAt: dose.logged_at,
  })) ?? data.today.map((dose) => ({
    medicationName: dose.medication_name || dose.name || "Medicine",
    timeSlot: dose.time_slot,
    status: dose.status === "not_taken" ? "missed" : dose.status,
  }));
  const takenCount = dailyDoses.filter((dose) => dose.status === "taken").length;
  const adherenceStyle = getAdherenceColor(data.adherence_score_7d);
  const recentAlerts = data.recent_alerts.slice(0, 8);
  const history = historyQuery.data ?? [];
  const latestTaken = history.find((log) => log.outcome.toUpperCase() === "TAKEN");
  const latestLog = history[0];
  const weeklyData = data.trend.slice(-7).map((point) => ({
    ...point,
    shortDate: formatDate(point.date, "EEE"),
    fullDate: formatDate(point.date, "MMM d, yyyy"),
  }));
  const todaySummary = dailyDoses.length === 0
    ? "No doses scheduled today"
    : dailyDoses.every((dose) => dose.status === "taken")
      ? "All scheduled doses confirmed"
      : dailyDoses.some((dose) => dose.status === "missed" || dose.status === "side_effect")
        ? "Follow-up needed"
        : "Check-ins still pending";

  return (
    <main className="min-h-screen bg-sky-50/60 px-4 py-6 text-slate-900 sm:px-6 sm:py-10">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="rounded-3xl border border-sky-200 bg-white p-5 shadow-sm sm:p-8">
          <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-sky-700 text-white" aria-hidden="true">
                <Heart className="h-5 w-5 fill-white" />
              </div>
              <div>
                <p className="text-lg font-bold tracking-tight text-slate-950">Nalam</p>
                <p className="text-xs text-slate-600">Family medication update</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-600" aria-live="polite">
              <span className="h-2 w-2 rounded-full bg-sky-600" aria-hidden="true" />
              Updated {lastUpdatedText}
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">Family view</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
                {data.patient_name}&apos;s medication update
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
                A simple view of today&apos;s check-ins, recent adherence, supplies, and alerts recorded by Nalam.
              </p>
            </div>
            <div className={`rounded-2xl border px-4 py-3 ${adherenceStyle.bg} ${adherenceStyle.border}`}>
              <p className="text-xs font-semibold text-slate-700">Seven-day adherence</p>
              <p className={`mt-1 text-3xl font-bold ${adherenceStyle.text}`}>{data.adherence_score_7d}%</p>
            </div>
          </div>
        </header>

        <section className="grid gap-4 sm:grid-cols-3" aria-label="Patient overview">
          <Card className="border-sky-200 bg-white shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Today&apos;s call status</p>
              <p className="mt-2 text-base font-semibold text-slate-950">{todaySummary}</p>
              <p className="mt-1 text-xs text-slate-600">{takenCount} of {dailyDoses.length} scheduled doses confirmed</p>
            </CardContent>
          </Card>
          <Card className="border-sky-200 bg-white shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Last successful confirmation</p>
              <p className="mt-2 text-base font-semibold text-slate-950">{formatDate(latestTaken?.call_time, "MMM d, h:mm a")}</p>
              <p className="mt-1 text-xs text-slate-600">Taken responses recorded in the last 7 days</p>
            </CardContent>
          </Card>
          <Card className="border-sky-200 bg-white shadow-sm">
            <CardContent className="p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Latest call record</p>
              <p className="mt-2 text-base font-semibold text-slate-950">
                {latestLog ? `${latestLog.outcome.replaceAll("_", " ")}` : "No call logged"}
              </p>
              <p className="mt-1 text-xs text-slate-600">{formatDate(latestLog?.call_time, "MMM d, h:mm a")}</p>
            </CardContent>
          </Card>
        </section>

        {dailyQuery.isError && (
          <Alert>
            <AlertTriangle aria-hidden="true" />
            <AlertTitle>Today&apos;s detailed dose status is unavailable</AlertTitle>
            <AlertDescription>{getApiErrorMessage(dailyQuery.error)} The summary above is from the family dashboard response.</AlertDescription>
          </Alert>
        )}

        <section className="space-y-3" aria-labelledby="today-heading">
          <div>
            <h2 id="today-heading" className="text-xl font-bold text-slate-950">Today&apos;s medicines</h2>
            <p className="mt-1 text-sm text-slate-600">Statuses come from today&apos;s recorded adherence events.</p>
          </div>
          {dailyDoses.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">
              No active medication doses were returned for today.
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {dailyDoses.map((dose, index) => {
                const status = statusCopy(dose.status);
                const StatusIcon = status.icon;
                return (
                  <Card key={`${dose.medicationName}-${dose.timeSlot}-${index}`} className="border-slate-200 bg-white shadow-sm">
                    <CardContent className="flex items-start justify-between gap-4 p-5">
                      <div className="flex min-w-0 items-start gap-3">
                        <div className="rounded-xl bg-sky-100 p-2.5 text-sky-700" aria-hidden="true"><Pill className="h-5 w-5" /></div>
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold text-slate-950">{dose.medicationName}</h3>
                          <p className="mt-1 text-xs capitalize text-slate-600">
                            {dose.timeSlot}{dose.mealTiming ? ` · ${formatMealTiming(dose.mealTiming)}` : ""}
                          </p>
                          {dose.loggedAt && <p className="mt-1 text-[11px] text-slate-500">Recorded {formatTime(dose.loggedAt)}</p>}
                        </div>
                      </div>
                      <span className={`inline-flex shrink-0 items-center gap-1 rounded-xl border px-2 py-1 text-[11px] font-semibold ${status.className}`}>
                        <StatusIcon className="h-3.5 w-3.5" aria-hidden="true" />
                        <span className="sr-only">{dose.medicationName}: </span>{status.label}
                      </span>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>

        <section aria-labelledby="history-heading">
          <Card className="border-slate-200 bg-white shadow-sm">
            <CardHeader className="border-b border-slate-100 pb-4">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <CardTitle id="history-heading" className="text-xl text-slate-950">Seven-day adherence history</CardTitle>
                  <p className="mt-1 text-sm text-slate-600">One backend-calculated score per day; no client-side percentage is invented.</p>
                </div>
                <Badge variant="outline" className={`${adherenceStyle.badge} w-fit`}>{data.adherence_score_7d}% this week</Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-5">
              {weeklyData.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600">
                  No adherence history is available yet.
                </div>
              ) : (
                <div className="h-56 w-full" role="img" aria-label="Seven-day adherence bar chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={weeklyData} margin={{ top: 10, right: 10, left: -22, bottom: 0 }}>
                      <XAxis dataKey="shortDate" tickLine={false} axisLine={{ stroke: "#cbd5e1" }} tick={{ fill: "#475569", fontSize: 12 }} />
                      <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: "#64748b", fontSize: 11 }} tickFormatter={(value: number) => `${value}%`} />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const point = payload[0]?.payload as (typeof weeklyData)[number];
                          return (
                            <div className="rounded-xl bg-slate-950 px-3 py-2 text-xs text-white shadow-lg">
                              <p className="text-slate-300">{point.fullDate}</p>
                              <p className="mt-1 font-bold text-sky-300">{point.score}% adherence</p>
                              <p className="mt-1 text-slate-400">{point.doses_taken} of {point.doses_expected} doses</p>
                            </div>
                          );
                        }}
                      />
                      <Bar dataKey="score" radius={[6, 6, 0, 0]} isAnimationActive={false}>
                        {weeklyData.map((point) => (
                          <Cell key={point.date} fill={point.score >= 80 ? "#0284c7" : point.score >= 60 ? "#d97706" : "#e11d48"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 border-t border-slate-100 pt-4 text-xs text-slate-600">
                <span><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-sky-600" aria-hidden="true" />Good: 80% or higher</span>
                <span><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-amber-500" aria-hidden="true" />Moderate: 60–79%</span>
                <span><span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-rose-600" aria-hidden="true" />Low: below 60%</span>
              </div>
            </CardContent>
          </Card>
        </section>

        <section className="space-y-3" aria-labelledby="medications-heading">
          <div>
            <h2 id="medications-heading" className="text-xl font-bold text-slate-950">Active prescriptions</h2>
            <p className="mt-1 text-sm text-slate-600">Prescription directions and refill estimates supplied by the backend.</p>
          </div>
          {data.medications.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">No active medications found.</div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {data.medications.map((medication, index) => {
                const hasSupply = medication.pills_remaining !== null && medication.pills_remaining !== undefined;
                const daysUntilRefill = medication.days_until_refill;
                const hasRefillEstimate = typeof daysUntilRefill === "number" && Number.isFinite(daysUntilRefill);
                const isUrgent = hasRefillEstimate && daysUntilRefill <= 5;
                return (
                  <Card key={`${medication.name}-${index}`} className={`border bg-white shadow-sm ${isUrgent ? "border-amber-300" : "border-slate-200"}`}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-slate-950">{medication.name}</h3>
                          <p className="mt-1 text-sm text-slate-700">{medication.dosage}</p>
                        </div>
                        {isUrgent && <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-900">Refill soon</Badge>}
                      </div>
                      <p className="mt-3 text-xs text-slate-600">{formatMealTiming(medication.meal_timing)}</p>
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {medication.frequency.map((slot) => <Badge key={slot} variant="outline" className="border-sky-200 bg-sky-50 text-sky-800">{slot}</Badge>)}
                      </div>
                      <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-600">
                        Supply: <span className="font-semibold text-slate-900">{hasSupply ? `${medication.pills_remaining} pills` : "Not available"}</span>
                        {hasRefillEstimate && <span> · about {Math.ceil(daysUntilRefill)} days</span>}
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </section>

        <section className="space-y-3" aria-labelledby="alerts-heading">
          <div>
            <h2 id="alerts-heading" className="text-xl font-bold text-slate-950">Recent alerts</h2>
            <p className="mt-1 text-sm text-slate-600">Escalations recorded from medication check-ins.</p>
          </div>
          {recentAlerts.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">No recent alerts.</div>
          ) : (
            <div className="space-y-3">
              {recentAlerts.map((alert) => (
                <div key={alert.id} className={`rounded-2xl border bg-white p-4 ${alert.severity === "critical" ? "border-rose-200" : alert.severity === "warning" ? "border-amber-200" : "border-slate-200"}`}>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex items-start gap-3">
                      {alert.severity === "critical" ? <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" aria-hidden="true" /> : <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" aria-hidden="true" />}
                      <div>
                        <p className="text-xs font-bold uppercase tracking-wide text-slate-800">{alert.alert_type.replaceAll("_", " ")}</p>
                        <p className="mt-1 text-sm leading-relaxed text-slate-700">{alert.message}</p>
                      </div>
                    </div>
                    <p className="shrink-0 text-xs text-slate-500">{formatDate(alert.created_at, "MMM d, h:mm a")}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <footer className="border-t border-sky-200 pt-5 pb-6 text-xs leading-relaxed text-slate-600">
          <div className="flex items-center gap-2 font-semibold text-slate-800"><ShieldCheck className="h-4 w-4 text-sky-700" aria-hidden="true" />Privacy and demo data</div>
          <p className="mt-2">Nalam records medication responses to calculate adherence and generate configured family alerts. Use synthetic patient records in this demo workspace. Confirm backend recording, transcript, consent, and opt-out configuration before using real health information.</p>
          {historyQuery.isError && <p className="mt-2 text-amber-800">Seven-day call history could not be loaded: {getApiErrorMessage(historyQuery.error)}</p>}
        </footer>
      </div>
    </main>
  );
}
