"use client";

import { useRouter } from "next/navigation";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DashboardSummary } from "@/lib/types";
import { getAdherenceColor, getDoseStatusColor } from "@/lib/utils";
import { PhoneCall, ExternalLink, ChevronRight, User } from "lucide-react";
import { useTriggerCall } from "@/lib/queries";

interface PatientTableProps {
  patients: DashboardSummary[];
  isLoading?: boolean;
}

export function PatientTable({ patients, isLoading }: PatientTableProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (patients.length === 0) {
    return (
      <div className="text-center py-12 px-4 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
        <User className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <h4 className="text-sm font-semibold text-slate-700">No Patients Enrolled</h4>
        <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
          Start onboarding patients to begin automated voice adherence tracking.
        </p>
        <Button
          size="sm"
          className="mt-4 bg-emerald-600 hover:bg-emerald-700 text-white"
          onClick={() => router.push("/onboard")}
        >
          Add Patient
        </Button>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <Table>
        <TableHeader className="bg-slate-50/75">
          <TableRow>
            <TableHead className="font-semibold text-slate-700">Patient</TableHead>
            <TableHead className="font-semibold text-slate-700">Phone</TableHead>
            <TableHead className="font-semibold text-slate-700 text-center">7d Score</TableHead>
            <TableHead className="font-semibold text-slate-700">Last Status</TableHead>
            <TableHead className="font-semibold text-slate-700 text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {patients.map((patient) => {
            const adherenceStyle = getAdherenceColor(patient.adherence_score_7d);
            const statusStyle = patient.last_call_status
              ? getDoseStatusColor(patient.last_call_status)
              : null;

            return (
              <TableRow
                key={patient.patient_id}
                className="cursor-pointer hover:bg-slate-50/80 transition-colors group"
                onClick={() => router.push(`/admin/patients/${patient.patient_id}`)}
              >
                <TableCell className="font-medium text-slate-900">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold group-hover:text-emerald-700 transition-colors">
                      {patient.patient_name}
                    </span>
                    {patient.refill_due_medications &&
                      patient.refill_due_medications.length > 0 && (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-800 bg-amber-100 border border-amber-300 px-1.5 py-0.5 rounded-full"
                          title={patient.refill_due_medications.join(", ")}
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />
                          {patient.refill_due_medications.length} med{patient.refill_due_medications.length !== 1 ? "s" : ""} due
                        </span>
                      )}
                  </div>
                  <span className="text-[11px] text-slate-400">
                    {patient.medications_count} medication{patient.medications_count !== 1 ? "s" : ""}
                  </span>
                </TableCell>
                <TableCell className="text-xs text-slate-600 font-mono">
                  {patient.patient_phone || "—"}
                </TableCell>
                <TableCell className="text-center">
                  <Badge
                    variant="outline"
                    className={`font-semibold border text-xs px-2 py-0.5 ${adherenceStyle.badge}`}
                  >
                    {patient.adherence_score_7d}%
                  </Badge>
                </TableCell>
                <TableCell>
                  {statusStyle ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700">
                      <span className={`w-2 h-2 rounded-full ${statusStyle.dot}`} />
                      {statusStyle.label}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">No calls yet</span>
                  )}
                </TableCell>
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0 text-slate-500 hover:text-emerald-700"
                      onClick={() => router.push(`/admin/patients/${patient.patient_id}`)}
                      title="View Details"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
