"use client";

import { usePathname } from "next/navigation";
import { MobileNav } from "./mobile-nav";
import { Badge } from "@/components/ui/badge";
import { Bell, HeartHandshake } from "lucide-react";
import Link from "next/link";
import { useAlerts } from "@/lib/queries";

export function Header() {
  const pathname = usePathname();
  const { data: alertsData } = useAlerts({ is_read: false, limit: 5 });

  const unreadCount = alertsData?.meta?.total || 0;

  // Derive title from pathname
  let title = "Dashboard";
  let subtitle = "Overview of elderly patient medication adherence";

  if (pathname.includes("/admin/patients/")) {
    title = "Patient Profile";
    subtitle = "Medication schedule, call logs and escalation history";
  } else if (pathname === "/admin/patients") {
    title = "Patients Directory";
    subtitle = "Manage enrolled patients and daily outreach";
  } else if (pathname === "/admin/alerts") {
    title = "Alerts & Escalations";
    subtitle = "Real-time side effect reports and missed dose notifications";
  } else if (pathname === "/admin/refills") {
    title = "Refill Tracker";
    subtitle = "Predictive inventory and prescription replenishment";
  }

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-4 sm:px-8 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <MobileNav />
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-slate-900 tracking-tight leading-none">
            {title}
          </h1>
          <p className="hidden sm:block text-xs text-slate-500 mt-0.5">
            {subtitle}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-medium">Live Voice Engine</span>
        </div>

        <Link
          href="/admin/alerts"
          className="relative p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
          aria-label="Alerts"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 flex items-center justify-center w-4 h-4 rounded-full bg-rose-600 text-[10px] font-bold text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}
