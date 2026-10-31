import Link from "next/link";
import { PhoneCall, HeartPulse, ShieldCheck, ArrowRight, Activity, Bell, Pill, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col justify-between">
      {/* Top Navbar */}
      <header className="border-b bg-white/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white font-bold text-xl shadow-sm">
              ந
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-teal-900">Nalam</span>
              <span className="text-xs font-semibold text-teal-600 ml-1.5 px-2 py-0.5 bg-teal-50 rounded-full border border-teal-200">
                (நலம்)
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/onboard">
              <Button variant="outline" className="border-teal-200 text-teal-700 hover:bg-teal-50">
                Onboard Patient
              </Button>
            </Link>
            <Link href="/admin">
              <Button className="bg-teal-600 hover:bg-teal-700 text-white shadow-sm">
                Staff Portal
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center">
          <Badge className="bg-teal-100 text-teal-800 hover:bg-teal-100 mb-6 py-1 px-3 text-sm font-medium border-teal-200">
            🎙️ Vernacular Voice AI for Chronic Care in India
          </Badge>

          <h1 className="text-4xl sm:text-6xl font-extrabold text-slate-900 tracking-tight max-w-4xl mx-auto leading-tight sm:leading-none">
            Empathetic Daily Care Calls for Elderly Parents in{" "}
            <span className="text-teal-600 underline decoration-teal-300 decoration-wavy decoration-2">
              Their Native Language
            </span>
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto leading-relaxed">
            Nalam replaces forgotten pill alarms with warm, human-like voice calls in Hindi and Tamil, while instantly keeping sons and daughters updated via WhatsApp.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link href="/admin">
              <Button size="lg" className="bg-teal-600 hover:bg-teal-700 text-white px-8 h-12 text-base shadow-md">
                <Activity className="w-5 h-5 mr-2" />
                Launch Staff Dashboard
              </Button>
            </Link>
            <Link href="/onboard">
              <Button size="lg" variant="outline" className="h-12 px-8 text-base border-slate-300 hover:bg-slate-100">
                <Users className="w-5 h-5 mr-2 text-teal-600" />
                Enroll a Patient
              </Button>
            </Link>
          </div>

          {/* Quick Metrics Bar */}
          <div className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto text-left">
            <div className="bg-white p-5 rounded-2xl border shadow-sm">
              <div className="text-3xl font-black text-teal-600">92%+</div>
              <div className="text-sm font-medium text-slate-600 mt-1">Elderly Call Pick-up Rate</div>
            </div>
            <div className="bg-white p-5 rounded-2xl border shadow-sm">
              <div className="text-3xl font-black text-emerald-600">&lt; 90s</div>
              <div className="text-sm font-medium text-slate-600 mt-1">Average Call Check-in</div>
            </div>
            <div className="bg-white p-5 rounded-2xl border shadow-sm">
              <div className="text-3xl font-black text-amber-600">3 Langs</div>
              <div className="text-sm font-medium text-slate-600 mt-1">Hindi, Tamil & English</div>
            </div>
            <div className="bg-white p-5 rounded-2xl border shadow-sm">
              <div className="text-3xl font-black text-purple-600">100%</div>
              <div className="text-sm font-medium text-slate-600 mt-1">WhatsApp Caregiver Loop</div>
            </div>
          </div>
        </section>

        {/* Feature Highlights */}
        <section className="py-16 bg-white border-y">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-12">
              <h2 className="text-3xl font-bold tracking-tight text-slate-900">
                How Nalam Protects Every Dose
              </h2>
              <p className="mt-3 text-slate-600">
                A closed-loop care ecosystem connecting pharmacies, AI voice agents, patients, and families.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              <Card className="border-teal-100 hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="w-12 h-12 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mb-2">
                    <PhoneCall className="w-6 h-6" />
                  </div>
                  <CardTitle className="text-xl">Empathetic Voice Calls</CardTitle>
                  <CardDescription>
                    Warm, conversational calls addressing patients affectionately as &quot;Maata ji&quot; or &quot;Amma&quot;. Patient and unhurried speech cadence.
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-slate-600">
                  Speaks everyday colloquial Hinglish and Tanglish, explaining medicines before or after meals without clinical jargon.
                </CardContent>
              </Card>

              <Card className="border-emerald-100 hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center mb-2">
                    <Bell className="w-6 h-6" />
                  </div>
                  <CardTitle className="text-xl">Proactive WhatsApp Alerts</CardTitle>
                  <CardDescription>
                    Real-time notifications sent to sons and daughters with full context if a dose is skipped or side effects are reported.
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-slate-600">
                  Includes a one-click WhatsApp call button so caregivers can quickly phone their parent with complete peace of mind.
                </CardContent>
              </Card>

              <Card className="border-blue-100 hover:shadow-md transition-shadow">
                <CardHeader>
                  <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mb-2">
                    <Pill className="w-6 h-6" />
                  </div>
                  <CardTitle className="text-xl">Smart Refill Depletion</CardTitle>
                  <CardDescription>
                    Pill inventory counts decrement automatically upon confirmed doses, triggering pharmacy restocking reminders 5 days prior.
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-slate-600">
                  Helps community chemists and pharmacies retain chronic patients while preventing catastrophic therapy discontinuation.
                </CardContent>
              </Card>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t bg-slate-100 py-8 text-center text-sm text-slate-500">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 font-medium text-slate-700">
            <span>Nalam (நலம்) — AI Voice Health Companion</span>
          </div>
          <div>
            Built with ❤️ by <span className="font-semibold text-slate-800">Siva Karthik</span> | VIT Chennai
          </div>
        </div>
      </footer>
    </div>
  );
}
