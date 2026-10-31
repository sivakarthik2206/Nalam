"use client";

import { RefreshCw, ShieldCheck } from "lucide-react";
import { useAdminDashboard, useAlerts, useRefillPredictions } from "@/lib/queries";
import { AlertsFeed } from "@/components/dashboard/alerts-feed";
import { DemoCallPanel } from "@/components/dashboard/demo-call-panel";
import { PatientTable } from "@/components/dashboard/patient-table";
import { RefillList } from "@/components/dashboard/refill-list";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getApiErrorMessage } from "@/lib/utils";

function LoadingBlock() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Loading dashboard">
      {["one", "two", "three", "four"].map((key) => (
        <div key={key} className="h-28 animate-pulse rounded-2xl border border-slate-200 bg-white" />
      ))}
    </div>
  );
}

export default function AdminDashboardPage() {
  const dashboardQuery = useAdminDashboard();
  const alertsQuery = useAlerts({ limit: 100 });
  const refillsQuery = useRefillPredictions();

  const dashboard = dashboardQuery.data;
  const patients = dashboard?.patients ?? [];
  const alerts = alertsQuery.data?.data ?? [];

  if (dashboardQuery.isLoading) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <div>
          <div className="h-8 w-64 animate-pulse rounded bg-slate-200" />
          <div className="mt-2 h-4 w-96 max-w-full animate-pulse rounded bg-slate-100" />
        </div>
        <LoadingBlock />
        <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
          <div className="h-72 animate-pulse rounded-2xl border border-slate-200 bg-white" />
          <div className="h-72 animate-pulse rounded-2xl border border-slate-200 bg-white" />
        </div>
      </div>
    );
  }

  if (dashboardQuery.isError || !dashboard) {
    return (
      <div className="mx-auto max-w-2xl py-12">
        <Alert variant="destructive">
          <AlertTitle>Admin dashboard unavailable</AlertTitle>
          <AlertDescription className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{getApiErrorMessage(dashboardQuery.error)}</span>
            <Button type="button" variant="outline" size="sm" onClick={() => dashboardQuery.refetch()}>
              <RefreshCw aria-hidden="true" />
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">Pharmacy operations</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">Adherence overview</h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600">
            Review actual call outcomes, seven-day adherence, refill risk, and alerts from the Nalam backend.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="h-4 w-4 text-sky-700" aria-hidden="true" />
          <span>Demo workspace: use synthetic patient records only.</span>
        </div>
      </header>

      <StatsCards
        totalPatients={dashboard.total_patients}
        avgAdherence7d={dashboard.avg_adherence_7d}
        criticalAlertsToday={dashboard.alerts_today.critical}
        refillsDue={dashboard.patients_needing_refill}
        isLoading={false}
      />

      <DemoCallPanel patients={patients} isLoading={dashboardQuery.isFetching} />

      <section className="grid items-start gap-6 lg:grid-cols-[1.35fr_0.65fr]" aria-label="Patient operations and alerts">
        <Card className="overflow-hidden border-slate-200 bg-white shadow-sm">
          <CardHeader className="border-b border-slate-100 pb-4">
            <CardTitle className="text-lg text-slate-950">Monitored patients</CardTitle>
            <CardDescription className="text-xs text-slate-600">
              Scores and statuses are returned by the backend. Open a patient for the family view.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <PatientTable patients={patients} alerts={alerts} isLoading={false} />
          </CardContent>
        </Card>

        <Card className="border-slate-200 bg-white shadow-sm">
          <CardHeader className="border-b border-slate-100 pb-4">
            <CardTitle className="text-lg text-slate-950">Alert history</CardTitle>
            <CardDescription className="text-xs text-slate-600">
              Recent escalation records, including delivery channel and acknowledgement state.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {alertsQuery.isError ? (
              <Alert variant="destructive">
                <AlertTitle>Alerts unavailable</AlertTitle>
                <AlertDescription className="mt-2 flex flex-col gap-3">
                  <span>{getApiErrorMessage(alertsQuery.error)}</span>
                  <Button type="button" variant="outline" size="sm" onClick={() => alertsQuery.refetch()}>
                    Retry alerts
                  </Button>
                </AlertDescription>
              </Alert>
            ) : (
              <AlertsFeed alerts={alerts} isLoading={alertsQuery.isLoading} />
            )}
          </CardContent>
        </Card>
      </section>

      <Card className="border-slate-200 bg-white shadow-sm">
        <CardHeader className="border-b border-slate-100 pb-4">
          <CardTitle className="text-lg text-slate-950">Refill watch</CardTitle>
          <CardDescription className="text-xs text-slate-600">
            Forecasts returned by the backend. Unknown stock is not displayed as zero.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          {refillsQuery.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Refill data unavailable</AlertTitle>
              <AlertDescription className="mt-2 flex flex-col gap-3">
                <span>{getApiErrorMessage(refillsQuery.error)}</span>
                <Button type="button" variant="outline" size="sm" onClick={() => refillsQuery.refetch()}>
                  Retry refills
                </Button>
              </AlertDescription>
            </Alert>
          ) : (
            <RefillList refills={refillsQuery.data ?? []} isLoading={refillsQuery.isLoading} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
