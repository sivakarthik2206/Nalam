"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreatePatient, useAddMedication } from "@/lib/queries";
import { Language, MealTiming, PatientCreate, MedicationCreate } from "@/lib/types";
import { getApiErrorMessage } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { User, Phone, Heart, Languages, Pill, ArrowRight, Sparkles } from "lucide-react";

const AVAILABLE_SLOTS = [
  { id: "morning", label: "Morning (09:00 AM)" },
  { id: "afternoon", label: "Afternoon (02:00 PM)" },
  { id: "evening", label: "Evening (06:00 PM)" },
  { id: "night", label: "Night (09:00 PM)" },
];

export function PatientForm() {
  const router = useRouter();

  // Step 1: Patient details
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("+91");
  const [language, setLanguage] = useState<Language>("hindi");
  const [familyContactName, setFamilyContactName] = useState("");
  const [familyContactPhone, setFamilyContactPhone] = useState("+91");

  // Step 2: First Medication (optional or initial)
  const [medName, setMedName] = useState("");
  const [medDosage, setMedDosage] = useState("1 tablet");
  const [frequency, setFrequency] = useState<string[]>(["morning", "evening"]);
  const [mealRelation, setMealRelation] = useState<MealTiming>("after_meal");
  const [pillsDispensed, setPillsDispensed] = useState<number>(60);
  const [durationDays, setDurationDays] = useState<number>(30);

  const [errorMsg, setErrorMsg] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const createPatient = useCreatePatient();
  const addMedication = useAddMedication("");

  const toggleSlot = (slot: string) => {
    if (frequency.includes(slot)) {
      if (frequency.length > 1) {
        setFrequency(frequency.filter((s) => s !== slot));
      }
    } else {
      setFrequency([...frequency, slot]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    // Phone format check: +91 followed by 10 digits
    const phoneRegex = /^\+91\d{10}$/;
    if (!phoneRegex.test(phone.trim())) {
      setErrorMsg("Patient phone must match +91 followed by 10 digits (e.g. +919876543210)");
      return;
    }

    if (familyContactPhone.trim() && familyContactPhone.trim() !== "+91") {
      if (!phoneRegex.test(familyContactPhone.trim())) {
        setErrorMsg("Family WhatsApp number must match +91 followed by 10 digits");
        return;
      }
    }

    setIsSubmitting(true);

    try {
      // 1. Create Patient
      const patientPayload: PatientCreate = {
        name: name.trim(),
        phone: phone.trim(),
        language,
        family_contact_name: familyContactName.trim() || null,
        family_whatsapp:
          familyContactPhone.trim() !== "+91" ? familyContactPhone.trim() : null,
      };

      const newPatient = await createPatient.mutateAsync(patientPayload);

      // 2. Add First Medication if provided
      if (medName.trim()) {
        const medPayload: MedicationCreate = {
          name: medName.trim(),
          dosage: medDosage.trim() || "1 tablet",
          frequency,
          meal_timing: mealRelation,
          prescription_duration_days: durationDays || 30,
          pills_dispensed: pillsDispensed || 60,
          prescription_start_date: new Date().toISOString().split("T")[0],
        };

        // Add medication through API
        await (await import("@/lib/api")).default.post(
          `/patients/${newPatient.id}/medications`,
          medPayload
        );
      }

      // 3. Redirect to patient detail page
      router.push(`/admin/patients/${newPatient.id}`);
    } catch (err: unknown) {
      setErrorMsg(getApiErrorMessage(err));
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-sm text-rose-800">
          {errorMsg}
        </div>
      )}

      {/* Section 1: Patient Information */}
      <Card className="bg-white border-slate-200 shadow-sm">
        <CardHeader className="pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700">
              <User className="w-5 h-5" />
            </div>
            <div>
              <CardTitle className="text-base font-bold text-slate-900">
                1. Patient Personal Details
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Primary contact details for automated voice call check-ins
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="patient-name" className="text-xs font-semibold text-slate-700">
                Full Name *
              </Label>
              <Input
                id="patient-name"
                placeholder="e.g. Ramesh Patel"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="bg-slate-50/50"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="patient-phone" className="text-xs font-semibold text-slate-700">
                Phone Number (+91XXXXXXXXXX) *
              </Label>
              <Input
                id="patient-phone"
                placeholder="+919876543210"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                className="font-mono bg-slate-50/50"
              />
              <p className="text-[11px] text-slate-400">
                Bolna voice calls will be dialed to this number.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">
                Preferred Language *
              </Label>
              <Select
                value={language}
                onValueChange={(val) => val && setLanguage(val as Language)}
              >
                <SelectTrigger className="bg-slate-50/50">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="hindi">Hindi (हिंदी)</SelectItem>
                  <SelectItem value="tamil">Tamil (தமிழ்)</SelectItem>
                  <SelectItem value="english">English</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="kin-name" className="text-xs font-semibold text-slate-700">
                Family Contact Name
              </Label>
              <Input
                id="kin-name"
                placeholder="e.g. Priya Patel (Daughter)"
                value={familyContactName}
                onChange={(e) => setFamilyContactName(e.target.value)}
                className="bg-slate-50/50"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="kin-phone" className="text-xs font-semibold text-slate-700">
                Family WhatsApp Number
              </Label>
              <Input
                id="kin-phone"
                placeholder="+919876543210"
                value={familyContactPhone}
                onChange={(e) => setFamilyContactPhone(e.target.value)}
                className="font-mono bg-slate-50/50"
              />
              <p className="text-[11px] text-slate-400">
                WhatsApp summaries & side effect alerts will be sent here.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Section 2: First Medication (Optional or Primary) */}
      <Card className="bg-white border-slate-200 shadow-sm">
        <CardHeader className="pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-700">
              <Pill className="w-5 h-5" />
            </div>
            <div>
              <CardTitle className="text-base font-bold text-slate-900">
                2. Primary Medication & Call Schedule
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Voice schedules will automatically activate for the selected daily slots
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5 sm:col-span-1">
              <Label htmlFor="med-first-name" className="text-xs font-semibold text-slate-700">
                Medication Name
              </Label>
              <Input
                id="med-first-name"
                placeholder="e.g. Metformin 500mg"
                value={medName}
                onChange={(e) => setMedName(e.target.value)}
                className="bg-slate-50/50"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="med-first-dosage" className="text-xs font-semibold text-slate-700">
                Dosage
              </Label>
              <Input
                id="med-first-dosage"
                placeholder="1 tablet"
                value={medDosage}
                onChange={(e) => setMedDosage(e.target.value)}
                className="bg-slate-50/50"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">
                Meal Relation
              </Label>
              <Select
                value={mealRelation}
                onValueChange={(val) => val && setMealRelation(val as MealTiming)}
              >
                <SelectTrigger className="bg-slate-50/50">
                  <SelectValue placeholder="Relation" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="before_meal">Before Meal</SelectItem>
                  <SelectItem value="after_meal">After Meal</SelectItem>
                  <SelectItem value="with_meal">With Meal</SelectItem>
                  <SelectItem value="no_relation">No Relation</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Slots Checklist */}
          <div className="space-y-2">
            <Label className="text-xs font-semibold text-slate-700">
              Check Daily Reminder Call Slots
            </Label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {AVAILABLE_SLOTS.map((slot) => {
                const isSelected = frequency.includes(slot.id);
                return (
                  <button
                    type="button"
                    key={slot.id}
                    onClick={() => toggleSlot(slot.id)}
                    className={`p-2.5 rounded-lg border text-left text-xs font-medium transition-all ${
                      isSelected
                        ? "bg-emerald-50 border-emerald-500 text-emerald-900 font-bold"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`w-3 h-3 rounded-full border flex items-center justify-center ${
                          isSelected
                            ? "bg-emerald-600 border-emerald-600"
                            : "border-slate-300"
                        }`}
                      >
                        {isSelected && (
                          <span className="w-1.5 h-1.5 rounded-full bg-white" />
                        )}
                      </span>
                      <span>{slot.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="med-first-dispensed" className="text-xs font-semibold text-slate-700">
                Pills Dispensed
              </Label>
              <Input
                id="med-first-dispensed"
                type="number"
                min={1}
                value={pillsDispensed}
                onChange={(e) => setPillsDispensed(parseInt(e.target.value) || 0)}
                className="bg-slate-50/50"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="med-first-duration" className="text-xs font-semibold text-slate-700">
                Prescription Duration (Days)
              </Label>
              <Input
                id="med-first-duration"
                type="number"
                min={1}
                value={durationDays}
                onChange={(e) => setDurationDays(parseInt(e.target.value) || 0)}
                className="bg-slate-50/50"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Submit Button */}
      <div className="flex items-center justify-end gap-3">
        <Button
          type="button"
          variant="outline"
          onClick={() => router.back()}
          className="border-slate-300"
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={isSubmitting}
          className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2 px-6 shadow-sm"
        >
          <span>{isSubmitting ? "Onboarding Patient..." : "Complete Onboarding"}</span>
          <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </form>
  );
}
