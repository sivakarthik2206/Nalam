"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { usePatients, useAdminDashboard, useTriggerCall } from "@/lib/queries";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Search,
  UserPlus,
  PhoneCall,
  ChevronRight,
  ExternalLink,
  Users,
  Languages,
} from "lucide-react";
import { getAdherenceColor, getDoseStatusColor } from "@/lib/utils";

export function PatientsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [languageFilter, setLanguageFilter] = useState<string>("all");

  const { data: dashboard, isLoading: isDashboardLoading } = useAdminDashboard();
  const triggerCall = useTriggerCall("");

  const patients = dashboard?.patients || [];

  // Filter patients by name/phone search and language
  const filteredPatients = patients.filter((p) => {
    const matchesSearch =
      p.patient_name.toLowerCase().includes(search.toLowerCase()) ||
      p.patient_phone.includes(search);
    return matchesSearch;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Patient Directory
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Manage voice profiles, adherence telemetry, and manual outbound triggers
          </p>
        </div>
        <Link href="/onboard">
          <Button className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 shadow-xs">
            <UserPlus className="w-4 h-4" />
            <span>Add Patient</span>
          </Button>
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <Card className="bg-white border-slate-200 shadow-xs">
        <CardContent className="p-4 flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              placeholder="Search by patient name or phone number (+91...)"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 bg-slate-50/50 border-slate-200"
            />
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select value={languageFilter} onValueChange={(val) => setLanguageFilter(val || "all")}>
              <SelectTrigger className="w-full sm:w-44 bg-slate-50/50 border-slate-200">
                <div className="flex items-center gap-2">
                  <Languages className="w-4 h-4 text-slate-400" />
                  <SelectValue placeholder="All Languages" />
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Languages</SelectItem>
                <SelectItem value="hindi">Hindi (हिंदी)</SelectItem>
                <SelectItem value="tamil">Tamil (தமிழ்)</SelectItem>
                <SelectItem value="english">English</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Patients Table */}
      <Card className="bg-white border-slate-200 shadow-sm overflow-hidden">
        <CardContent className="p-0">
          {isDashboardLoading ? (
            <div className="p-8 space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : filteredPatients.length === 0 ? (
            <div className="py-16 text-center">
              <Users className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <h4 className="text-base font-bold text-slate-700">No matching patients</h4>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                {search ? "No patients match your search criteria." : "Get started by adding your first patient."}
              </p>
              {!search && (
                <Link href="/onboard">
                  <Button size="sm" className="mt-4 bg-emerald-600 text-white">
                    Onboard Patient
                  </Button>
                </Link>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader className="bg-slate-50/75">
                  <TableRow>
                    <TableHead className="font-semibold text-slate-700">Name</TableHead>
                    <TableHead className="font-semibold text-slate-700">Phone</TableHead>
                    <TableHead className="font-semibold text-slate-700">Medications</TableHead>
                    <TableHead className="font-semibold text-slate-700 text-center">7d Adherence</TableHead>
                    <TableHead className="font-semibold text-slate-700">Last Status</TableHead>
                    <TableHead className="font-semibold text-slate-700 text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPatients.map((p) => {
                    const adhColor = getAdherenceColor(p.adherence_score_7d);
                    const lastStatusColor = p.last_call_status
                      ? getDoseStatusColor(p.last_call_status)
                      : null;

                    return (
                      <TableRow
                        key={p.patient_id}
                        className="cursor-pointer hover:bg-slate-50/80 transition-colors"
                        onClick={() => router.push(`/admin/patients/${p.patient_id}`)}
                      >
                        <TableCell className="font-bold text-slate-900">
                          {p.patient_name}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-slate-600">
                          {p.patient_phone || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-slate-700">
                          <span className="font-semibold">{p.medications_count}</span> active
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge
                            variant="outline"
                            className={`font-semibold border text-xs px-2 py-0.5 ${adhColor.badge}`}
                          >
                            {p.adherence_score_7d}%
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {lastStatusColor ? (
                            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700">
                              <span className={`w-2 h-2 rounded-full ${lastStatusColor.dot}`} />
                              {lastStatusColor.label}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">No calls yet</span>
                          )}
                        </TableCell>
                        <TableCell
                          className="text-right"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-8 gap-1.5 text-xs border-slate-200 hover:border-emerald-500 hover:text-emerald-700"
                              onClick={() => router.push(`/admin/patients/${p.patient_id}`)}
                            >
                              <span>Details</span>
                              <ChevronRight className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default PatientsPage;
