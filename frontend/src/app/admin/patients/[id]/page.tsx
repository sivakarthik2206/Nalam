"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  usePatient,
  usePatientMedications,
  useAdherenceScore,
  useAdherenceHistory,
  useAdherenceTrend,
  useDailyStatus,
  useAlerts,
  useMarkAlertRead,
  useTriggerCall,
  useRefillPredictions,
} from "@/lib/queries";
import { MedicationForm } from "@/components/patient/medication-form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  Phone,
  Heart,
  Globe,
  Share2,
  PhoneCall,
  Calendar,
  Flame,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Pill,
  Plus,
  AlertCircle,
  Info,
  Check,
  Bell,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { toast } from "@/components/ui/toast";
import { getAdherenceColor, formatDate, formatTime } from "@/lib/utils";

export default function PatientDetailPage() {
  const params = useParams();
  const patientId = (params?.id as string) || "";

  const [isAddMedOpen, setIsAddMedOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  // Queries
  const { data: patient, isLoading: isPatientLoading } = usePatient(patientId);
  const { data: scoreData, isLoading: isScoreLoading } = useAdherenceScore(patientId, 7);
  const { data: medications = [], isLoading: isMedsLoading } = usePatientMedications(patientId);
  const { data: dailyData, isLoading: isDailyLoading } = useDailyStatus(patientId);
  const { data: historyLogs = [], isLoading: isHistoryLoading } = useAdherenceHistory(patientId, 30);
  const { data: trendData = [], isLoading: isTrendLoading } = useAdherenceTrend(patientId, 30);
  const { data: alertsData, isLoading: isAlertsLoading } = useAlerts({ patient_id: patientId });
  const { data: refillPredictions = [] } = useRefillPredictions();

  // Mutations
  const triggerCall = useTriggerCall(patientId);
  const markRead = useMarkAlertRead();

  const handleTriggerCall = () => {
    triggerCall.mutate(undefined, {
      onSuccess: () => {
        (toast as any).add({
          type: "success",
          title: "Voice Call Initiated",
          description: `Bolna AI is calling ${patient?.name || "the patient"} at ${patient?.phone}...`,
        });
      },
      onError: (err: any) => {
        (toast as any).add({
          type: "error",
          title: "Call Failed",
          description: err?.response?.data?.detail || "Could not connect to Bolna API",
        });
      },
    });
  };

  const handleShareFamilyLink = () => {
    const url = typeof window !== "undefined"
      ? `${window.location.origin}/family/${patientId}`
      : `/family/${patientId}`;

    if (navigator?.clipboard) {
      navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      (toast as any).add({
        type: "success",
        title: "Family Link Copied",
        description: "The public family view URL has been copied to your clipboard.",
      });
    }
  };

  if (isPatientLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-5 bg-slate-200 rounded w-28" />
        <div className="h-44 bg-white rounded-2xl border border-slate-200" />
        <div className="grid grid-cols-3 gap-4">
          <div className="h-28 bg-white rounded-xl border border-slate-200" />
          <div className="h-28 bg-white rounded-xl border border-slate-200" />
          <div className="h-28 bg-white rounded-xl border border-slate-200" />
        </div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="text-center py-20">
        <h3 className="text-xl font-bold text-slate-800">Patient Not Found</h3>
        <p className="text-sm text-slate-500 mt-1">
          The requested record does not exist or has been removed.
        </p>
        <Link href="/admin/patients">
          <Button variant="outline" className="mt-4">
            &larr; Back to Patients Directory
          </Button>
        </Link>
      </div>
    );
  }

  const score7d = scoreData?.score_7d ?? patient.adherence_score_7d ?? 0;
  const score30d = scoreData?.score_30d ?? patient.adherence_score_30d ?? 0;
  const currentStreak = scoreData?.streak_current ?? 0;

  const adhColor7d = getAdherenceColor(score7d);
  const adhColor30d = getAdherenceColor(score30d);

  // Today's logs from history
  const todayLogs = historyLogs.filter((log) => {
    const logDate = new Date(log.call_time).toDateString();
    const todayDate = new Date().toDateString();
    return logDate === todayDate;
  });

  // Map refills by medication
  const refillMap: Record<string, { pills_remaining: number; days_remaining: number }> = {};
  refillPredictions.forEach((r) => {
    if (r.patient_id === patientId) {
      refillMap[r.medication_name] = {
        pills_remaining: r.pills_remaining,
        days_remaining: r.days_remaining,
      };
    }
  });

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb */}
      <div>
        <Link
          href="/admin/patients"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-emerald-700 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to All Patients</span>
        </Link>
      </div>

      {/* 1. TOP SECTION: Patient Info Card */}
      <Card className="bg-white border-slate-200 shadow-sm overflow-hidden">
        <div className="h-2 bg-emerald-600" />
        <CardContent className="p-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center shrink-0">
                <span className="text-xl font-black text-emerald-800">
                  {patient.name.charAt(0).toUpperCase()}
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h2 className="text-2xl font-black text-slate-900 tracking-tight">
                    {patient.name}
                  </h2>
                  <Badge
                    variant="outline"
                    className="bg-emerald-50 text-emerald-800 border-emerald-200 capitalize font-medium text-xs"
                  >
                    <span className="mr-1">🇮🇳</span>
                    {patient.language}
                  </Badge>
                  {patient.is_active ? (
                    <Badge variant="outline" className="bg-slate-100 text-slate-700 text-xs font-semibold">
                      Active
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="text-xs">
                      Inactive
                    </Badge>
                  )}
                </div>

                <div className="flex items-center gap-4 mt-2 text-xs text-slate-600 flex-wrap">
                  <span className="flex items-center gap-1.5 font-mono font-medium text-slate-800">
                    <Phone className="w-3.5 h-3.5 text-slate-400" />
                    {patient.phone}
                  </span>
                  {patient.family_contact_name && (
                    <span className="flex items-center gap-1.5 font-medium">
                      <Heart className="w-3.5 h-3.5 text-rose-500" />
                      Family Contact: {patient.family_contact_name}{" "}
                      <span className="font-mono text-slate-500">
                        ({patient.family_whatsapp || "No WhatsApp"})
                      </span>
                    </span>
                  )}
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Calendar className="w-3.5 h-3.5" />
                    Enrolled {formatDate(patient.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-2.5 flex-wrap">
              <Button
                variant="outline"
                size="sm"
                onClick={handleShareFamilyLink}
                className="gap-2 border-slate-200 text-xs font-medium"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Share2 className="w-3.5 h-3.5 text-slate-500" />}
                <span>{copied ? "Copied Link!" : "Share Family Link"}</span>
              </Button>

              <Button
                size="sm"
                onClick={handleTriggerCall}
                disabled={triggerCall.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 text-xs font-bold shadow-xs"
              >
                <PhoneCall className="w-3.5 h-3.5" />
                <span>{triggerCall.isPending ? "Connecting..." : "Trigger Call Now"}</span>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 2. THREE METRIC CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* 7-Day Adherence */}
        <Card className={`bg-white border-slate-200 border-l-4 ${adhColor7d.border} shadow-sm`}>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                7-Day Adherence
              </p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl sm:text-3xl font-black text-slate-900">
                  {score7d}%
                </span>
                <span className={`text-xs font-semibold ${adhColor7d.text}`}>
                  {score7d >= 75 ? "Optimal" : score7d >= 60 ? "Moderate" : "Low"}
                </span>
              </div>
            </div>
            <div className={`w-10 h-10 rounded-xl ${adhColor7d.bg} flex items-center justify-center ${adhColor7d.text}`}>
              <Activity className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* 30-Day Adherence */}
        <Card className={`bg-white border-slate-200 border-l-4 ${adhColor30d.border} shadow-sm`}>
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                30-Day Adherence
              </p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl sm:text-3xl font-black text-slate-900">
                  {score30d}%
                </span>
                <span className="text-xs text-slate-400 font-medium">Monthly baseline</span>
              </div>
            </div>
            <div className={`w-10 h-10 rounded-xl ${adhColor30d.bg} flex items-center justify-center ${adhColor30d.text}`}>
              <Calendar className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>

        {/* Current Streak */}
        <Card className="bg-white border-slate-200 border-l-4 border-l-amber-500 shadow-sm">
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Current Streak
              </p>
              <div className="flex items-baseline gap-2 mt-1">
                <span className="text-2xl sm:text-3xl font-black text-slate-900">
                  {currentStreak}
                </span>
                <span className="text-xs text-amber-700 font-semibold">Consecutive Days</span>
              </div>
            </div>
            <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600">
              <Flame className="w-5 h-5" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 3. TABS: Today, History, Medications, Alerts */}
      <Tabs defaultValue="today" className="w-full">
        <TabsList className="bg-slate-100 p-1 rounded-xl">
          <TabsTrigger value="today" className="gap-2 text-xs font-semibold">
            <Clock className="w-4 h-4" />
            <span>Today&apos;s Status</span>
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-2 text-xs font-semibold">
            <Activity className="w-4 h-4" />
            <span>Adherence History</span>
          </TabsTrigger>
          <TabsTrigger value="medications" className="gap-2 text-xs font-semibold">
            <Pill className="w-4 h-4" />
            <span>Medications ({medications.length})</span>
          </TabsTrigger>
          <TabsTrigger value="alerts" className="gap-2 text-xs font-semibold">
            <Bell className="w-4 h-4" />
            <span>Alerts ({alertsData?.data?.length || 0})</span>
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: TODAY */}
        <TabsContent value="today" className="mt-4 space-y-6">
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
              <CardTitle className="text-base font-bold text-slate-900">
                Today&apos;s Prescribed Doses
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Status reported during automated outbound voice interactions today
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6">
              {isDailyLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-pulse">
                  <div className="h-28 bg-slate-100 rounded-xl" />
                  <div className="h-28 bg-slate-100 rounded-xl" />
                </div>
              ) : !dailyData?.medications || dailyData.medications.length === 0 ? (
                <div className="text-center py-10 border border-dashed border-slate-200 rounded-xl">
                  <Pill className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700">No Doses Scheduled Today</p>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Add medications in the Medications tab to schedule reminder calls.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {dailyData.medications.map((item, idx) => {
                    const isTaken = item.status === "taken";
                    const isMissed = item.status === "missed";
                    const isSideEffect = item.status === "side_effect";
                    const isPending = item.status === "pending";

                    // Format meal relation badge
                    const mealBadge =
                      item.meal_timing === "before_meal"
                        ? "🍽️ Before Meal"
                        : item.meal_timing === "after_meal"
                        ? "🍽️ After Meal"
                        : item.meal_timing === "with_meal"
                        ? "🍽️ With Meal"
                        : "No Meal Relation";

                    return (
                      <div
                        key={`${item.time_slot}-${item.name}-${idx}`}
                        className={`p-5 rounded-2xl border flex flex-col justify-between transition-all ${
                          isTaken
                            ? "bg-emerald-50/50 border-emerald-200"
                            : isSideEffect
                            ? "bg-rose-50/50 border-rose-300"
                            : isMissed
                            ? "bg-amber-50/50 border-amber-200"
                            : "bg-slate-50/60 border-slate-200"
                        }`}
                      >
                        <div>
                          <div className="flex items-center justify-between gap-1">
                            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                              {item.time_slot} Slot
                            </span>
                            <Badge variant="outline" className="text-[10px] font-semibold bg-white border-slate-200 text-slate-700">
                              {mealBadge}
                            </Badge>
                          </div>

                          <h4 className="text-base font-bold text-slate-900 mt-2">
                            {item.name}
                          </h4>
                        </div>

                        {/* Status indicator */}
                        <div className="mt-4 pt-3 border-t border-slate-200/60">
                          {isTaken && (
                            <span className="flex items-center gap-1.5 text-xs font-bold text-emerald-700">
                              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                              Taken{item.logged_at ? ` at ${formatTime(item.logged_at)}` : ""}
                            </span>
                          )}
                          {isMissed && (
                            <span className="flex items-center gap-1.5 text-xs font-bold text-rose-700">
                              <XCircle className="w-4 h-4 text-rose-600" />
                              Missed
                            </span>
                          )}
                          {isSideEffect && (
                            <span className="flex items-center gap-1.5 text-xs font-bold text-rose-700">
                              <AlertTriangle className="w-4 h-4 text-rose-600" />
                              Side Effect Reported
                            </span>
                          )}
                          {isPending && (
                            <span className="flex items-center gap-1.5 text-xs font-bold text-amber-700">
                              <Clock className="w-4 h-4 text-amber-600" />
                              Pending Reminder Call
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Timeline of calls made today */}
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-base font-bold text-slate-900">
                Today&apos;s Voice Interaction Timeline
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Outbound call logs generated by the AI voice agent for today
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6">
              {todayLogs.length === 0 ? (
                <div className="text-center py-8 text-xs text-slate-400">
                  No automated calls have triggered yet today.
                </div>
              ) : (
                <div className="space-y-3">
                  {todayLogs.map((log) => (
                    <div
                      key={log.id}
                      className="p-3.5 rounded-xl border border-slate-200 bg-slate-50/40 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-lg bg-emerald-100 text-emerald-800">
                          <PhoneCall className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-bold text-slate-800">
                            Voice Check-in:{" "}
                            <span className="capitalize">{log.scheduled_time_slot || "General"}</span>
                          </p>
                          <p className="text-[11px] text-slate-500 mt-0.5">
                            Outcome:{" "}
                            <strong className="text-slate-700 capitalize">
                              {log.outcome.replace("_", " ")}
                            </strong>
                            {log.side_effect_details && (
                              <span className="text-rose-600 font-semibold ml-1">
                                &bull; {log.side_effect_details}
                              </span>
                            )}
                          </p>
                        </div>
                      </div>

                      <span className="text-slate-400 text-[11px] font-mono shrink-0">
                        {formatTime(log.call_time)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 2: HISTORY */}
        <TabsContent value="history" className="mt-4 space-y-6">
          {/* 30-Day Line Chart */}
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-bold text-slate-900">
                30-Day Adherence Trend
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Daily percentage of taken vs expected doses
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isTrendLoading ? (
                <div className="h-64 bg-slate-50 rounded-lg animate-pulse" />
              ) : trendData.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-xs text-slate-400 bg-slate-50 rounded-lg">
                  No historical telemetry recorded.
                </div>
              ) : (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={trendData.map((d) => ({
                        ...d,
                        formattedDate: formatDate(d.date, "MMM d"),
                      }))}
                      margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                      <XAxis
                        dataKey="formattedDate"
                        tickLine={false}
                        axisLine={{ stroke: "#e2e8f0" }}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                      />
                      <YAxis
                        domain={[0, 100]}
                        tickLine={false}
                        axisLine={false}
                        tick={{ fill: "#64748b", fontSize: 11 }}
                        tickFormatter={(v) => `${v}%`}
                      />
                      <Tooltip
                        content={({ active, payload }) => {
                          if (active && payload && payload.length) {
                            const item = payload[0].payload;
                            return (
                              <div className="bg-slate-900 text-white px-3 py-1.5 rounded-lg text-xs shadow-lg">
                                <p className="font-semibold text-slate-200">{item.formattedDate}</p>
                                <p className="text-emerald-400 font-bold">Adherence: {item.score}%</p>
                              </div>
                            );
                          }
                          return null;
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="score"
                        stroke="#059669"
                        strokeWidth={2.5}
                        dot={{ r: 3, fill: "#059669" }}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Scrollable list of adherence logs */}
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-base font-bold text-slate-900">
                Historical Call Records (Last 30 Days)
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Chronological list of all voice calls placed and recorded responses
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {isHistoryLoading ? (
                <div className="p-6 space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : historyLogs.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  No previous call records recorded.
                </div>
              ) : (
                <div className="max-h-96 overflow-y-auto divide-y divide-slate-100">
                  {historyLogs.map((log) => (
                    <div key={log.id} className="p-4 flex items-center justify-between gap-4 hover:bg-slate-50/70 transition-colors">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-bold text-slate-900">
                            {formatDate(log.call_time, "MMM d, yyyy")} &bull; {formatTime(log.call_time)}
                          </span>
                          {log.scheduled_time_slot && (
                            <Badge variant="outline" className="text-[10px] capitalize bg-slate-50">
                              {log.scheduled_time_slot} Slot
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={`text-[10px] capitalize font-bold ${
                              log.outcome.toLowerCase() === "taken"
                                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                                : log.outcome.toLowerCase() === "side_effect"
                                ? "bg-rose-50 text-rose-800 border-rose-200"
                                : "bg-amber-50 text-amber-800 border-amber-200"
                            }`}
                          >
                            {log.outcome.replace("_", " ")}
                          </Badge>
                        </div>

                        {log.side_effect_details && (
                          <p className="text-xs text-rose-700 font-medium mt-1">
                            Symptom: {log.side_effect_details}
                          </p>
                        )}
                      </div>

                      <div className="text-[11px] text-slate-400 text-right shrink-0">
                        {log.call_duration_seconds ? `${log.call_duration_seconds}s` : "Bolna Voice"}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* TAB 3: MEDICATIONS */}
        <TabsContent value="medications" className="mt-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-900">
              Active Prescriptions & Supply Tracker
            </h3>
            <Button
              size="sm"
              onClick={() => setIsAddMedOpen(true)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 font-bold text-xs"
            >
              <Plus className="w-4 h-4" />
              <span>Add Medication</span>
            </Button>
          </div>

          {/* Add Medication Dialog */}
          <Dialog open={isAddMedOpen} onOpenChange={setIsAddMedOpen}>
            <DialogContent className="sm:max-w-xl">
              <DialogHeader>
                <DialogTitle className="text-lg font-bold text-slate-900">
                  Add Prescribed Medication
                </DialogTitle>
                <DialogDescription className="text-xs text-slate-500">
                  Outbound voice calls will be automatically scheduled based on the selected frequencies.
                </DialogDescription>
              </DialogHeader>
              <MedicationForm
                patientId={patientId}
                onSuccess={() => setIsAddMedOpen(false)}
              />
            </DialogContent>
          </Dialog>

          {/* Medication Cards List */}
          {isMedsLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-pulse">
              <div className="h-36 bg-slate-100 rounded-xl" />
              <div className="h-36 bg-slate-100 rounded-xl" />
            </div>
          ) : medications.length === 0 ? (
            <div className="text-center py-12 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
              <Pill className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <h4 className="text-sm font-bold text-slate-700">No Medications Prescribed</h4>
              <p className="text-xs text-slate-500 mt-0.5">
                Click &quot;Add Medication&quot; above to add prescriptions and configure call schedules.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {medications.map((med) => {
                const refillData = refillMap[med.name];
                const pillsRemaining = refillData ? refillData.pills_remaining : (med.pills_dispensed || 60);
                const daysRemaining = refillData ? refillData.days_remaining : (med.prescription_duration_days || 30);

                // Progress color: green >10 days, amber 5-10, red <5
                const progressColor =
                  daysRemaining > 10
                    ? "bg-emerald-500"
                    : daysRemaining >= 5
                    ? "bg-amber-500"
                    : "bg-rose-500";

                const progressPercent = Math.min(100, Math.max(5, (daysRemaining / 30) * 100));

                return (
                  <Card key={med.id} className="border-slate-200 bg-white shadow-xs">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
                            <Pill className="w-5 h-5" />
                          </div>
                          <div>
                            <h4 className="font-bold text-slate-900 text-sm">{med.name}</h4>
                            <p className="text-xs text-slate-500">
                              {med.dosage} &bull; {med.meal_timing.replace("_", " ")}
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Frequency tags */}
                      <div className="mt-3.5 flex items-center gap-1.5 flex-wrap">
                        <span className="text-[11px] text-slate-400 font-medium">Slots:</span>
                        {(med.frequency || []).map((slot) => (
                          <Badge
                            key={slot}
                            variant="outline"
                            className="text-[10px] capitalize bg-slate-50 border-slate-200 text-slate-700"
                          >
                            {slot}
                          </Badge>
                        ))}
                      </div>

                      {/* Refill Progress Bar */}
                      <div className="mt-4 pt-3 border-t border-slate-100">
                        <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                          <span className="text-slate-600">
                            {pillsRemaining} pills remaining
                          </span>
                          <span className={daysRemaining < 5 ? "text-rose-600 font-bold" : "text-slate-500"}>
                            ~{daysRemaining} days left
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${progressColor}`}
                            style={{ width: `${progressPercent}%` }}
                          />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* TAB 4: ALERTS */}
        <TabsContent value="alerts" className="mt-4">
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-base font-bold text-slate-900">
                Patient Alerts ({alertsData?.data?.length || 0})
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Side effects, consecutive missed doses, and unanswered phone calls
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {isAlertsLoading ? (
                <div className="p-6 space-y-3">
                  {[1, 2].map((i) => (
                    <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
                  ))}
                </div>
              ) : !alertsData?.data || alertsData.data.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  No alerts recorded for this patient.
                </div>
              ) : (
                <div className="divide-y divide-slate-100">
                  {alertsData.data.map((alert) => {
                    const isCritical = alert.severity === "critical";
                    const isWarning = alert.severity === "warning";

                    const badgeClass = isCritical
                      ? "bg-rose-100 text-rose-800 border-rose-200"
                      : isWarning
                      ? "bg-amber-100 text-amber-800 border-amber-200"
                      : "bg-sky-100 text-sky-800 border-sky-200";

                    return (
                      <div
                        key={alert.id}
                        onClick={() => !alert.is_read && markRead.mutate(alert.id)}
                        className={`p-4 flex items-start justify-between gap-3 cursor-pointer transition-colors ${
                          !alert.is_read
                            ? isCritical
                              ? "bg-rose-50/40 hover:bg-rose-50/60"
                              : "bg-amber-50/30 hover:bg-amber-50/50"
                            : "hover:bg-slate-50/70"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5 shrink-0">
                            {isCritical ? (
                              <AlertCircle className="w-5 h-5 text-rose-600" />
                            ) : isWarning ? (
                              <AlertTriangle className="w-5 h-5 text-amber-600" />
                            ) : (
                              <Info className="w-5 h-5 text-sky-600" />
                            )}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className={`text-[10px] font-bold uppercase ${badgeClass}`}>
                                {alert.alert_type.replace("_", " ")}
                              </Badge>
                              {!alert.is_read && (
                                <span className="text-[10px] font-bold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded">
                                  Unread
                                </span>
                              )}
                            </div>
                            <p className="text-xs font-semibold text-slate-800 mt-1 leading-snug">
                              {alert.message}
                            </p>
                          </div>
                        </div>

                        <span className="text-[11px] text-slate-400 shrink-0">
                          {formatDate(alert.created_at, "MMM d, h:mm a")}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
