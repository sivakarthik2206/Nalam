"use client";

import { FamilyMedicationDetail } from "@/lib/types";
import { Pill, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface MedicationCardsProps {
  medications: FamilyMedicationDetail[];
}

export function MedicationCards({ medications }: MedicationCardsProps) {
  if (!medications || medications.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-50 border border-dashed border-slate-200 rounded-xl text-slate-400 text-xs">
        No active medications recorded for this profile.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {medications.map((med) => {
        const isUrgent =
          med.days_until_refill !== null &&
          med.days_until_refill !== undefined &&
          med.days_until_refill <= 5;

        return (
          <Card
            key={med.name}
            className={`border shadow-xs transition-all ${
              isUrgent ? "border-amber-300 bg-amber-50/20" : "border-slate-200 bg-white"
            }`}
          >
            <CardContent className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
                    <Pill className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 text-sm leading-tight">
                      {med.name}
                    </h4>
                    <span className="text-xs text-slate-500 font-medium">
                      {med.dosage} &bull; {med.meal_timing.replace("_", " ")}
                    </span>
                  </div>
                </div>

                {isUrgent && (
                  <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300 text-[10px] font-bold shrink-0">
                    Refill Soon
                  </Badge>
                )}
              </div>

              {/* Frequencies */}
              <div className="mt-4 flex items-center gap-1.5 flex-wrap">
                <span className="text-[11px] text-slate-400 font-medium">Times:</span>
                {(med.frequency || []).map((f) => (
                  <Badge
                    key={f}
                    variant="outline"
                    className="capitalize text-[10px] bg-slate-50 border-slate-200 text-slate-700 font-medium"
                  >
                    {f}
                  </Badge>
                ))}
              </div>

              {/* Refill projections */}
              {med.pills_remaining !== null && med.pills_remaining !== undefined && (
                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                  <span className="text-slate-500">Remaining Stock:</span>
                  <span className="font-bold text-slate-800">
                    {med.pills_remaining} pills{" "}
                    {med.days_until_refill !== null && (
                      <span className="text-slate-500 font-normal">
                        (~{med.days_until_refill} days left)
                      </span>
                    )}
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
