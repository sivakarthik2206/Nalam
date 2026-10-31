"use client";

import Link from "next/link";
import { AlertTriangle, ChevronRight, UserRound } from "lucide-react";
import { AlertResponse, DashboardSummary } from "@/lib/types";
import { getAdherenceColor, getDoseStatusColor, formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface PatientTableProps {
  patients: DashboardSummary[];
  alerts?: AlertResponse[];
  isLoading?: boolean;
}

export function PatientTable({ patients, alerts = [], isLoading = false }: PatientTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-3 p-5" aria-label="Loading patients">
        {["one", "two", "three", "four"].map((key) => (
          <div key={key} className="h-12 animate-pulse rounded-lg bg-slate-100" />
        ))}
      </div>
    );
  }

  if (patients.length === 0) {
    return (
      <div className="border border-dashed border-slate-200 bg-slate-50/60 px-4 py-14 text-center">
        <UserRound className="mx-auto mb-2 h-8 w-8 text-slate-400" aria-hidden="true" />
        <h4 className="text-sm font-semibold text-slate-800">No active patients</h4>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-600">
          The backend returned no active patient records for this pharmacy.
        </p>
      </div>
    );
  }

  const latestAlertByPatient = new Map<string, AlertResponse>();
  for (const alert of alerts) {
    if (!latestAlertByPatient.has(alert.patient_id)) latestAlertByPatient.set(alert.patient_id, alert);
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader className="bg-sky-50/60">
          <TableRow>
            <TableHead className="whitespace-nowrap text-xs font-semibold text-slate-700">Patient</TableHead>
            <TableHead className="whitespace-nowrap text-xs font-semibold text-slate-700">Contact</TableHead>
            <TableHead className="whitespace-nowrap text-center text-xs font-semibold text-slate-700">7d adherence</TableHead>
            <TableHead className="whitespace-nowrap text-xs font-semibold text-slate-700">Last call status</TableHead>
            <TableHead className="whitespace-nowrap text-xs font-semibold text-slate-700">Refill</TableHead>
            <TableHead className="whitespace-nowrap text-xs font-semibold text-slate-700">Latest alert</TableHead>
            <TableHead className="text-right text-xs font-semibold text-slate-700">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {patients.map((patient) => {
            const adherenceStyle = getAdherenceColor(patient.adherence_score_7d);
            const callStyle = patient.last_call_status ? getDoseStatusColor(patient.last_call_status) : null;
            const patientAlert = latestAlertByPatient.get(patient.patient_id);

            return (
              <TableRow key={patient.patient_id} className="align-top hover:bg-sky-50/30">
                <TableCell>
                  <div className="min-w-36">
                    <p className="font-semibold text-slate-950">{patient.patient_name}</p>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      {patient.medications_count} medication{patient.medications_count === 1 ? "" : "s"}
                    </p>
                  </div>
                </TableCell>
                <TableCell className="text-xs text-slate-700">
                  <span className="whitespace-nowrap font-mono">{patient.patient_phone || "Not provided"}</span>
                  <span className="mt-1 block text-[11px] text-slate-500">Patient contact on file</span>
                </TableCell>
                <TableCell className="text-center">
                  <Badge variant="outline" className={`text-xs font-semibold ${adherenceStyle.badge}`}>
                    {patient.adherence_score_7d}%
                  </Badge>
                </TableCell>
                <TableCell>
                  {callStyle ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700">
                      <span className={`h-2 w-2 rounded-full ${callStyle.dot}`} aria-hidden="true" />
                      {callStyle.label}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-500">No call logged</span>
                  )}
                </TableCell>
                <TableCell>
                  {patient.refill_due_medications.length > 0 ? (
                    <div className="flex items-start gap-1.5 text-xs font-medium text-amber-900">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" aria-hidden="true" />
                      <span>{patient.refill_due_medications.join(", ")}</span>
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500">No refill flag</span>
                  )}
                </TableCell>
                <TableCell className="max-w-52">
                  {patientAlert ? (
                    <div>
                      <p className="truncate text-xs font-medium text-slate-800">{patientAlert.message}</p>
                      <p className="mt-1 text-[11px] text-slate-500">
                        {formatDate(patientAlert.created_at, "MMM d, h:mm a")} · {patientAlert.is_read ? "Acknowledged" : "Open"}
                      </p>
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500">No alert history</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <Link href={`/family/${patient.patient_id}`}>
                    <Button type="button" variant="outline" size="sm" className="gap-1 border-sky-200 text-sky-800 hover:bg-sky-50">
                      Family view
                      <ChevronRight aria-hidden="true" />
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
