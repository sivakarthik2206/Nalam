"use client";

import { useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, PhoneCall } from "lucide-react";
import { useTriggerCall } from "@/lib/queries";
import { DashboardSummary } from "@/lib/types";
import { getApiErrorMessage } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface DemoCallPanelProps {
  patients: DashboardSummary[];
  isLoading?: boolean;
}

export function DemoCallPanel({ patients, isLoading = false }: DemoCallPanelProps) {
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const effectivePatientId = patients.some((patient) => patient.patient_id === selectedPatientId)
    ? selectedPatientId
    : patients[0]?.patient_id ?? "";
  const triggerCall = useTriggerCall(effectivePatientId);

  const selectedPatient = patients.find((patient) => patient.patient_id === effectivePatientId);
  const callResult = triggerCall.data;
  const callSucceeded = callResult !== undefined && callResult.calls_triggered > 0;

  return (
    <Card className="border-sky-200 bg-white shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-sky-100 p-2.5 text-sky-700" aria-hidden="true">
            <PhoneCall className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-base text-slate-900">Manual demo call</CardTitle>
            <CardDescription className="mt-1 text-xs leading-relaxed text-slate-600">
              Choose the patient explicitly. The button only reports success after the backend returns a triggered call.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <label htmlFor="demo-patient" className="text-xs font-semibold text-slate-700">
          Patient to call
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            id="demo-patient"
            value={effectivePatientId}
            onChange={(event) => {
              setSelectedPatientId(event.target.value);
              triggerCall.reset();
            }}
            disabled={isLoading || patients.length === 0 || triggerCall.isPending}
            className="h-9 min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-sky-600 focus:ring-2 focus:ring-sky-200 disabled:cursor-not-allowed disabled:bg-slate-100"
          >
            {patients.length === 0 ? (
              <option value="">No active patients available</option>
            ) : (
              patients.map((patient) => (
                <option key={patient.patient_id} value={patient.patient_id}>
                  {patient.patient_name} · {patient.medications_count} medication{patient.medications_count === 1 ? "" : "s"}
                </option>
              ))
            )}
          </select>
          <Button
            type="button"
            onClick={() => triggerCall.mutate()}
            disabled={!selectedPatientId || triggerCall.isPending || patients.length === 0}
            className="h-9 bg-sky-700 text-white hover:bg-sky-800 sm:min-w-36"
          >
            {triggerCall.isPending ? (
              <>
                <Loader2 className="animate-spin" aria-hidden="true" />
                Calling…
              </>
            ) : (
              <>
                <PhoneCall aria-hidden="true" />
                Trigger call
              </>
            )}
          </Button>
        </div>

        {selectedPatient && (
          <p className="text-xs text-slate-500">
            Patient contact: <span className="font-medium text-slate-700">{selectedPatient.patient_phone || "Not provided"}</span>
          </p>
        )}

        {triggerCall.isError && (
          <div role="alert" className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{getApiErrorMessage(triggerCall.error)}</span>
          </div>
        )}

        {callResult && (
          <div
            role={callSucceeded ? "status" : "alert"}
            className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs ${
              callSucceeded
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-amber-200 bg-amber-50 text-amber-900"
            }`}
          >
            {callSucceeded ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            )}
            <span>
              {callSucceeded
                ? `${callResult.calls_triggered} call${callResult.calls_triggered === 1 ? "" : "s"} accepted by the backend.`
                : "The backend did not accept a call. No success is shown; check provider configuration and try again."}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
