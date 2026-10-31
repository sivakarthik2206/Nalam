"use client";

import { useState } from "react";
import { useAlerts, useMarkAlertRead } from "@/lib/queries";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AlertsFeed } from "@/components/dashboard/alerts-feed";
import { Bell, Filter, CheckCheck } from "lucide-react";

export default function AlertsPage() {
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [readFilter, setReadFilter] = useState<string>("all");

  const { data: alertsData, isLoading } = useAlerts({
    severity: severityFilter === "all" ? undefined : severityFilter,
    is_read: readFilter === "all" ? undefined : readFilter === "read",
    limit: 50,
  });

  const alerts = alertsData?.data || [];
  const unreadCount = alerts.filter((a) => !a.is_read).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Alerts & Escalations
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time feed of reported side effects, 3x missed doses, and unanswered calls
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs bg-rose-50 text-rose-800 border-rose-200">
            {unreadCount} Unread Alert{unreadCount !== 1 ? "s" : ""}
          </Badge>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="bg-white border-slate-200 shadow-xs">
        <CardContent className="p-4 flex flex-col sm:flex-row items-center gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" /> Severity:
            </span>
            <Select value={severityFilter} onValueChange={(val) => setSeverityFilter(val || "all")}>
              <SelectTrigger className="w-36 bg-slate-50 border-slate-200 text-xs">
                <SelectValue placeholder="All Severities" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Severities</SelectItem>
                <SelectItem value="critical">Critical Only</SelectItem>
                <SelectItem value="warning">Warning Only</SelectItem>
                <SelectItem value="info">Info Only</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <span className="text-xs font-semibold text-slate-500">Status:</span>
            <Select value={readFilter} onValueChange={(val) => setReadFilter(val || "all")}>
              <SelectTrigger className="w-36 bg-slate-50 border-slate-200 text-xs">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="unread">Unread Only</SelectItem>
                <SelectItem value="read">Archived / Read</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Alerts Feed */}
      <Card className="bg-white border-slate-200 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-bold text-slate-900">
            Active Alerts ({alerts.length})
          </CardTitle>
          <CardDescription className="text-xs text-slate-500">
            Click Dismiss to mark an alert as acknowledged once checked.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AlertsFeed alerts={alerts} isLoading={isLoading} />
        </CardContent>
      </Card>
    </div>
  );
}
