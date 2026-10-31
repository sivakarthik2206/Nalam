"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Heart,
  Home,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const navItems = [
  {
    name: "Dashboard",
    href: "/admin",
    icon: Home,
  },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "w-[280px] bg-sky-950 text-white flex flex-col shrink-0 border-r border-sky-900 select-none",
        className
      )}
    >
      {/* Brand Logo Header */}
      <div className="h-16 flex items-center px-6 gap-3 border-b border-sky-900">
        <div className="w-10 h-10 rounded-xl bg-sky-600 flex items-center justify-center shadow-lg shadow-sky-950/30">
          <Heart className="w-6 h-6 text-white fill-white" />
        </div>
        <div>
            <span className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
            Nalam
            <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">
              Care
            </span>
          </span>
            <p className="text-[11px] text-sky-200/70 font-medium leading-none">
            Family care operations
          </p>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 py-6 px-4 space-y-1.5 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-sky-200/70">
          Admin screen
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
                  ? "bg-sky-600 text-white shadow-sm shadow-sky-950/40"
                  : "text-sky-100/80 hover:text-white hover:bg-sky-900/70"
              )}
            >
              <Icon
                className={cn(
                  "w-4 h-4",
                  isActive ? "text-white" : "text-sky-200/70"
                )}
              />
              <span>{item.name}</span>
            </Link>
          );
        })}

      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-sky-900">
        <div className="bg-sky-900/60 rounded-xl p-3 border border-sky-800/70 flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-sky-400" />
          <div className="text-xs">
            <p className="font-semibold text-slate-200">Voice AI Agent</p>
            <p className="text-sky-200/70 text-[11px]">Backend status is source of truth</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
