"use client";

import { Medication } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pill, Trash2, Clock, CheckCircle2 } from "lucide-react";
import { useDeactivateMedication } from "@/lib/queries";

interface MedicationListProps {
  patientId: string;
  medications: Medication[];
  isLoading?: boolean;
}

export function MedicationList({
  patientId,
  medications,
  isLoading,
}: MedicationListProps) {
  const deactivate = useDeactivateMedication(patientId);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <div key={i} className="h-20 bg-slate-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (medications.length === 0) {
    return (
      <div className="p-8 text-center border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
        <Pill className="w-8 h-8 text-slate-300 mx-auto mb-2" />
        <h4 className="text-sm font-bold text-slate-700">No Prescriptions Added</h4>
        <p className="text-xs text-slate-400 mt-0.5">
          Use the form above to add medications and trigger voice call schedules.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {medications.map((med) => (
        <div
          key={med.id}
          className="p-4 rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-colors flex items-start justify-between gap-4"
        >
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 shrink-0">
              <Pill className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h4 className="font-bold text-slate-900 text-sm">{med.name}</h4>
                <span className="text-xs text-slate-500 font-medium bg-slate-100 px-2 py-0.5 rounded-md">
                  {med.dosage}
                </span>
                <span className="text-[11px] font-medium text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded-md">
                  {med.meal_timing.replace("_", " ")}
                </span>
              </div>

              {/* Frequencies */}
              <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                <span className="text-[11px] text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Calls:
                </span>
                {(med.frequency || []).map((slot) => (
                  <Badge
                    key={slot}
                    variant="outline"
                    className="capitalize text-[10px] bg-slate-50 border-slate-200 text-slate-700"
                  >
                    {slot}
                  </Badge>
                ))}
              </div>

              {/* Inventory count */}
              {med.pills_dispensed && (
                <p className="text-[11px] text-slate-400 mt-1.5">
                  Dispensed: <strong className="text-slate-600">{med.pills_dispensed} pills</strong>
                  {med.prescription_duration_days && ` (${med.prescription_duration_days} days)`}
                </p>
              )}
            </div>
          </div>

          <Button
            size="sm"
            variant="ghost"
            className="text-slate-400 hover:text-rose-600 hover:bg-rose-50 p-2 h-8 w-8 shrink-0"
            onClick={() => {
              if (confirm(`Remove ${med.name} and stop calling for it?`)) {
                deactivate.mutate(med.id);
              }
            }}
            disabled={deactivate.isPending}
            title="Deactivate Medication"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}
