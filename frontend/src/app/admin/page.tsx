"use client";

import { useAdminDashboard, useAlerts, useAdherenceTrend } from "@/lib/queries";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { AdherenceChart } from "@/components/dashboard/adherence-chart";
import { PatientTable } from "@/components/dashboard/patient-table";
import { AlertsFeed } from "@/components/dashboard/alerts-feed";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { UserPlus, Bell, ArrowRight } from "lucide-react";
import Link from "next/link";

export default function AdminDashboardPage() {
  const { data: dashboard, isLoading: isDashboardLoading } = useAdminDashboard();
  const { data: alertsData, isLoading: isAlertsLoading } = useAlerts({ limit: 10 });

  // Compute a 14-day aggregated trend placeholder from available data or empty list
  // If we have patients, query trend for the first patient or synthesize
  const firstPatientId = dashboard?.patients?.[0]?.patient_id;
  const { data: trendData, isLoading: isTrendLoading } = useAdherenceTrend(
    firstPatientId || "",
    14
  );

  const totalPatients = dashboard?.total_patients || 0;
  const avgAdherence7d = dashboard?.avg_adherence_7d || 0;
  const criticalAlertsToday = dashboard?.alerts_today?.critical || 0;
  const refillsDue = dashboard?.patients_needing_refill || 0;
  const patients = dashboard?.patients || [];
  const alerts = alertsData?.data || [];

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Adherence Operations
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Voice-automated elderly patient outreach & escalation center
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/onboard">
            <Button className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 shadow-xs">
              <UserPlus className="w-4 h-4" />
              <span>Enroll Patient</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Row 1: 4 Stat Cards */}
      <StatsCards
        totalPatients={totalPatients}
        avgAdherence7d={avgAdherence7d}
        criticalAlertsToday={criticalAlertsToday}
        refillsDue={refillsDue}
        isLoading={isDashboardLoading}
      />

      {/* Row 2: Adherence Trend Chart */}
      <AdherenceChart
        data={trendData || []}
        isLoading={isTrendLoading && !dashboard}
      />

      {/* Row 3 Split: Left 60% Patient Table | Right 40% Alerts Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 60%: Patient Table */}
        <div className="lg:col-span-7 xl:col-span-8">
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle className="text-base sm:text-lg font-bold text-slate-900">
                  Monitored Patients
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Sorted worst adherence first for priority intervention
                </CardDescription>
              </div>
              <Link href="/admin/patients">
                <Button variant="ghost" size="sm" className="text-xs text-emerald-700 hover:text-emerald-800 gap-1">
                  View All <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              <PatientTable
                patients={patients}
                isLoading={isDashboardLoading}
              />
            </CardContent>
          </Card>
        </div>

        {/* Right 40%: Recent Alerts Feed */}
        <div className="lg:col-span-5 xl:col-span-4">
          <Card className="bg-white border-slate-200 shadow-sm">
            <CardHeader className="pb-3 flex flex-row items-center justify-between space-y-0">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-rose-50 text-rose-600">
                  <Bell className="w-4 h-4" />
                </div>
                <div>
                  <CardTitle className="text-base font-bold text-slate-900">
                    Live Alerts Feed
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-500">
                    Automated voice call escalations
                  </CardDescription>
                </div>
              </div>
              <Link href="/admin/alerts">
                <Button variant="ghost" size="sm" className="text-xs text-slate-500 hover:text-slate-800">
                  History
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              <AlertsFeed alerts={alerts} isLoading={isAlertsLoading} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
