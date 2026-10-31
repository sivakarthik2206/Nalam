"use client";

import { useRefillPredictions } from "@/lib/queries";
import { RefillList } from "@/components/dashboard/refill-list";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Pill, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function RefillsPage() {
  const { data: refills = [], isLoading } = useRefillPredictions();

  const urgentCount = refills.filter((r) => r.refill_urgent).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Refill Predictions & Inventory
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Adherence-weighted pill consumption forecasts to prevent stock-outs
          </p>
        </div>
        {urgentCount > 0 && (
          <Badge variant="outline" className="text-xs bg-amber-50 text-amber-800 border-amber-300 font-bold px-3 py-1">
            <AlertTriangle className="w-3.5 h-3.5 mr-1 text-amber-600" />
            {urgentCount} Refill{urgentCount !== 1 ? "s" : ""} Urgent (&le; 5 Days)
          </Badge>
        )}
      </div>

      <Card className="bg-white border-slate-200 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-bold text-slate-900">
            Upcoming Prescription Depletions
          </CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Calculated based on confirmed voice responses (&quot;taken&quot;) and daily dose frequencies.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RefillList refills={refills} isLoading={isLoading} />
        </CardContent>
      </Card>
    </div>
  );
}
