"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Heart,
  Home,
  Users,
  Bell,
  Pill,
  UserPlus,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const navItems = [
  {
    name: "Dashboard",
    href: "/admin",
    icon: Home,
  },
  {
    name: "Patients",
    href: "/admin/patients",
    icon: Users,
  },
  {
    name: "Alerts",
    href: "/admin/alerts",
    icon: Bell,
  },
  {
    name: "Refills",
    href: "/admin/refills",
    icon: Pill,
  },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "w-[280px] bg-slate-900 text-white flex flex-col shrink-0 border-r border-slate-800 select-none",
        className
      )}
    >
      {/* Brand Logo Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-slate-800">
        <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-900/30">
          <Heart className="w-6 h-6 text-white fill-white" />
        </div>
        <div>
          <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
            Nalam
            <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              Care
            </span>
          </span>
          <p className="text-[11px] text-slate-400 font-medium leading-none">
            Adherence Platform
          </p>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          Main Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/admin"
              ? pathname === "/admin"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-emerald-600 text-white shadow-sm shadow-emerald-900/40"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/70"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4",
                  isActive ? "text-white" : "text-slate-400"
                )}
              />
              <span>{item.name}</span>
            </Link>
          );
        })}

        <div className="pt-6 px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          Quick Actions
        </div>

        <Link
          href="/onboard"
          className={cn(
            "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all duration-150",
            pathname === "/onboard"
              ? "bg-emerald-600 text-white"
              : "text-slate-300 hover:text-white hover:bg-slate-800/70"
          )}
        >
          <UserPlus className="w-4 h-4 text-emerald-400" />
          <span>Onboard Patient</span>
        </Link>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-800">
        <div className="bg-slate-800/60 rounded-xl p-3 border border-slate-700/50 flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <div className="text-xs">
            <p className="font-semibold text-slate-200">Voice AI Agent</p>
            <p className="text-slate-400 text-[11px]">Bolna & Twilio active</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
