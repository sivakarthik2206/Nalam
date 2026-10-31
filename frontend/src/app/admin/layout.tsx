import { Suspense } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { WsListener } from "@/components/layout/ws-listener";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-slate-50/50">
      <WsListener />
      {/* Desktop Sidebar (280px fixed width) */}
      <Suspense fallback={<div className="w-[280px] bg-slate-900 hidden md:block" />}>
        <Sidebar className="hidden md:flex" />
      </Suspense>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Suspense fallback={<div className="h-16 bg-white border-b border-slate-200" />}>
          <Header />
        </Suspense>
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Suspense fallback={<div className="p-8 text-sm text-slate-400">Loading...</div>}>
            {children}
          </Suspense>
        </main>
      </div>
    </div>
  );
}
