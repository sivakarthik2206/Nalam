"use client";

import { PatientWithMedications } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Phone,
  Heart,
  Globe,
  Share2,
  PhoneCall,
  Calendar,
  AlertTriangle,
} from "lucide-react";
import { getAdherenceColor, formatDate } from "@/lib/utils";
import { useTriggerCall } from "@/lib/queries";
import { useState } from "react";

interface PatientDetailCardProps {
  patient: PatientWithMedications;
}

export function PatientDetailCard({ patient }: PatientDetailCardProps) {
  const [copied, setCopied] = useState(false);
  const triggerCall = useTriggerCall(patient.id);

  const adhColor7d = getAdherenceColor(patient.adherence_score_7d);
  const adhColor30d = getAdherenceColor(patient.adherence_score_30d);

  const shareableFamilyLink = typeof window !== "undefined"
    ? `${window.location.origin}/family/${patient.id}`
    : `/family/${patient.id}`;

  const handleCopyLink = () => {
    if (typeof navigator !== "undefined") {
      navigator.clipboard.writeText(shareableFamilyLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return (
    <Card className="bg-white border-slate-200 shadow-sm overflow-hidden">
      <div className="h-2.5 bg-emerald-600" />
      <CardContent className="p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          {/* Patient Overview */}
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-emerald-100/70 border border-emerald-200 flex items-center justify-center shrink-0">
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
                  <Globe className="w-3 h-3 mr-1" />
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
                <span className="flex items-center gap-1.5 font-mono">
                  <Phone className="w-3.5 h-3.5 text-slate-400" />
                  {patient.phone}
                </span>
                {patient.family_contact_name && (
                  <span className="flex items-center gap-1.5">
                    <Heart className="w-3.5 h-3.5 text-rose-500" />
                    Kin: {patient.family_contact_name} ({patient.family_whatsapp})
                  </span>
                )}
                <span className="flex items-center gap-1.5 text-slate-400">
                  <Calendar className="w-3.5 h-3.5" />
                  Enrolled {formatDate(patient.created_at)}
                </span>
              </div>
            </div>
          </div>

          {/* Quick Stats & Actions */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* 7d Score Pill */}
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col items-center min-w-[90px]">
              <span className="text-[10px] uppercase font-bold text-slate-500">
                7d Score
              </span>
              <span className={`text-xl font-black ${adhColor7d.text}`}>
                {patient.adherence_score_7d}%
              </span>
            </div>

            {/* 30d Score Pill */}
            <div className="p-3 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col items-center min-w-[90px]">
              <span className="text-[10px] uppercase font-bold text-slate-500">
                30d Score
              </span>
              <span className={`text-xl font-black ${adhColor30d.text}`}>
                {patient.adherence_score_30d}%
              </span>
            </div>

            {/* Buttons */}
            <div className="flex flex-col sm:flex-row gap-2">
              <Button
                variant="outline"
                size="sm"
                className="gap-2 border-slate-200 text-xs"
                onClick={handleCopyLink}
              >
                <Share2 className="w-3.5 h-3.5 text-slate-500" />
                <span>{copied ? "Link Copied!" : "Share Family View"}</span>
              </Button>

              <Button
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 text-xs"
                onClick={() => triggerCall.mutate()}
                disabled={triggerCall.isPending}
              >
                <PhoneCall className="w-3.5 h-3.5" />
                <span>{triggerCall.isPending ? "Calling..." : "Test Call (Bolna)"}</span>
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
