"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, Heart, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { navItems } from "./sidebar";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        className="md:hidden inline-flex items-center justify-center rounded-lg border border-slate-200 h-9 w-9 text-slate-700 hover:bg-slate-100 transition-colors"
        aria-label="Open Navigation Menu"
      >
        <Menu className="w-5 h-5" />
      </SheetTrigger>
      <SheetContent side="left" className="w-[280px] p-0 bg-slate-900 border-slate-800 text-white">
        <SheetHeader className="h-16 flex flex-row items-center px-6 gap-3 border-b border-slate-800 space-y-0 text-left">
          <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center">
            <Heart className="w-5 h-5 text-white fill-white" />
          </div>
          <div>
            <SheetTitle className="text-lg font-bold text-white leading-tight">
              Nalam Care
            </SheetTitle>
            <p className="text-[11px] text-slate-400">Adherence Platform</p>
          </div>
        </SheetHeader>

        <div className="py-6 px-4 space-y-1.5">
          <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Navigation
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
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all",
                  isActive
                    ? "bg-emerald-600 text-white"
                    : "text-slate-300 hover:text-white hover:bg-slate-800"
                )}
              >
                <Icon className="w-4 h-4" />
                <span>{item.name}</span>
              </Link>
            );
          })}

          <div className="pt-4 px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Actions
          </div>
          <Link
            href="/onboard"
            onClick={() => setOpen(false)}
            className="flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium text-emerald-400 hover:bg-slate-800 transition-all"
          >
            <UserPlus className="w-4 h-4" />
            <span>Onboard Patient</span>
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
