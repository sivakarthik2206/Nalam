"use client";

import { RefillInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pill, Phone, AlertCircle } from "lucide-react";
import Link from "next/link";

interface RefillListProps {
  refills: RefillInfo[];
  isLoading?: boolean;
}

export function RefillList({ refills, isLoading }: RefillListProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-16 bg-slate-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (refills.length === 0) {
    return (
      <div className="text-center py-10 px-4 border border-dashed border-slate-200 rounded-xl bg-slate-50/50">
        <Pill className="w-7 h-7 text-emerald-500 mx-auto mb-2" />
        <h4 className="text-sm font-semibold text-slate-700">Supplies Healthy</h4>
        <p className="text-xs text-slate-500 mt-0.5">
          No patients currently projected to run out of medications within 5 days.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {refills.map((refill) => (
        <div
          key={`${refill.patient_id}-${refill.medication_name}`}
          className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            refill.refill_urgent
              ? "bg-amber-50/50 border-amber-200"
              : "bg-white border-slate-200"
          }`}
        >
          <div className="flex items-start gap-3">
            <div
              className={`p-2.5 rounded-lg shrink-0 ${
                refill.refill_urgent ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"
              }`}
            >
              <Pill className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <Link
                  href={`/family/${refill.patient_id}`}
                  className="font-bold text-slate-900 hover:text-emerald-700 text-sm"
                >
                  {refill.patient_name}
                </Link>
                {refill.refill_urgent && (
                  <Badge variant="outline" className="bg-amber-100 text-amber-800 border-amber-300 text-[10px] font-bold">
                    Urgent (&le; 5 Days)
                  </Badge>
                )}
              </div>
              <p className="text-xs text-slate-600 font-medium mt-0.5">
                {refill.medication_name} &bull;{" "}
                <span className="font-semibold text-slate-800">
                  {refill.pills_remaining} pills left
                </span>{" "}
                (~{refill.days_remaining} days)
              </p>
              <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                {refill.patient_phone}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-center">
            <Link href={`/family/${refill.patient_id}`}>
              <Button size="sm" variant="outline" className="text-xs border-slate-300">
                Family view
              </Button>
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}
