"use client";

import { usePathname } from "next/navigation";
import { MobileNav } from "./mobile-nav";

export function Header() {
  const pathname = usePathname();
  // Derive title from pathname
  let title = "Adherence overview";
  let subtitle = "Patient outcomes, alerts, and refill risk from the backend";

  if (pathname.includes("/admin/patients/")) {
    title = "Family medication view";
    subtitle = "Medication schedule, call history, and escalation records";
  } else if (pathname === "/admin/patients") {
    title = "Adherence overview";
    subtitle = "Patient outcomes and daily outreach";
  } else if (pathname === "/admin/alerts") {
    title = "Alert history";
    subtitle = "Recorded side effects, missed doses, and call escalations";
  } else if (pathname === "/admin/refills") {
    title = "Refill watch";
    subtitle = "Backend refill estimates and urgency";
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
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-sky-50 border border-sky-200 text-xs text-sky-800">
          <span className="w-2 h-2 rounded-full bg-sky-600" />
          <span className="font-medium">Backend data refreshes automatically</span>
        </div>
      </div>
    </header>
  );
}
