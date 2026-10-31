"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import confetti from "canvas-confetti";
import api from "@/lib/api";
import { useTriggerCall } from "@/lib/queries";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  Heart,
  Pill,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2,
  User,
  Clock,
  PhoneCall,
} from "lucide-react";

// ============================================================================
// Types & Schemas
// ============================================================================

const patientSchema = z.object({
  name: z.string().min(2, "Patient name must be at least 2 characters"),
  phone10: z.string().regex(/^\d{10}$/, "Phone number must be exactly 10 digits"),
  language: z.enum(["hindi", "tamil", "english"]),
  familyContactName: z.string().optional(),
  familyContactPhone10: z
    .string()
    .regex(/^\d{10}$/, "Family WhatsApp must be 10 digits")
    .optional()
    .or(z.literal("")),
  pharmacy: z.string().optional(),
});

type PatientFormData = z.infer<typeof patientSchema>;

interface AddedMedication {
  id: string;
  name: string;
  dosage: string;
  frequency: string[];
  meal_timing: "before_meal" | "after_meal" | "with_meal" | "no_relation";
  prescription_duration_days: number;
  pills_dispensed: number;
  prescription_start_date: string;
}

const DEFAULT_SLOT_TIMES: Record<string, string> = {
  morning: "09:00",
  afternoon: "14:00",
  evening: "18:00",
  night: "21:00",
};

export default function OnboardPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // --- Step 1: Patient Details Form ---
  const {
    register,
    handleSubmit,
    control,
    watch,
    formState: { errors },
  } = useForm<PatientFormData>({
    resolver: zodResolver(patientSchema),
    defaultValues: {
      name: "",
      phone10: "",
      language: "hindi",
      familyContactName: "",
      familyContactPhone10: "",
      pharmacy: "none",
    },
  });

  const selectedLanguage = watch("language");
  const patientNameWatch = watch("name");

  // --- Step 2: Multiple Medications ---
  const [medications, setMedications] = useState<AddedMedication[]>([]);
  const [currentMedName, setCurrentMedName] = useState("");
  const [currentMedDosage, setCurrentMedDosage] = useState("1 tablet");
  const [currentFrequency, setCurrentFrequency] = useState<string[]>(["morning", "evening"]);
  const [currentMealRelation, setCurrentMealRelation] = useState<
    "before_meal" | "after_meal" | "with_meal" | "no_relation"
  >("after_meal");
  const [currentDurationDays, setCurrentDurationDays] = useState(30);
  const [currentPillsDispensed, setCurrentPillsDispensed] = useState(60);
  const [currentStartDate, setCurrentStartDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [medError, setMedError] = useState("");

  // --- Step 3: Call Schedule ---
  const [slotTimes, setSlotTimes] = useState<Record<string, string>>({
    morning: "09:00",
    afternoon: "14:00",
    evening: "18:00",
    night: "21:00",
  });
  const [preferredGreeting, setPreferredGreeting] = useState("Maata");

  // Auto-set greeting based on language
  useEffect(() => {
    if (selectedLanguage === "tamil") {
      setPreferredGreeting("Amma");
    } else if (selectedLanguage === "hindi") {
      setPreferredGreeting("Maata");
    } else {
      setPreferredGreeting(patientNameWatch || "Patient");
    }
  }, [selectedLanguage, patientNameWatch]);

  // --- Submission State ---
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdPatientId, setCreatedPatientId] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [callTriggered, setCallTriggered] = useState(false);

  // Toggle frequency slots for medication form
  const toggleFrequencySlot = (slot: string) => {
    if (currentFrequency.includes(slot)) {
      if (currentFrequency.length > 1) {
        setCurrentFrequency(currentFrequency.filter((s) => s !== slot));
      }
    } else {
      setCurrentFrequency([...currentFrequency, slot]);
    }
  };

  // Add medication to local list
  const handleAddMedication = () => {
    setMedError("");
    if (!currentMedName.trim()) {
      setMedError("Medication name is required (e.g. Metformin 500mg)");
      return;
    }
    if (currentFrequency.length === 0) {
      setMedError("Select at least one reminder time slot");
      return;
    }

    const newMed: AddedMedication = {
      id: Math.random().toString(36).substring(7),
      name: currentMedName.trim(),
      dosage: currentMedDosage.trim() || "1 tablet",
      frequency: [...currentFrequency],
      meal_timing: currentMealRelation,
      prescription_duration_days: currentDurationDays || 30,
      pills_dispensed: currentPillsDispensed || 60,
      prescription_start_date: currentStartDate,
    };

    setMedications([...medications, newMed]);
    // Reset form
    setCurrentMedName("");
    setCurrentMedDosage("1 tablet");
    setCurrentFrequency(["morning", "evening"]);
    setCurrentMealRelation("after_meal");
    setCurrentDurationDays(30);
    setCurrentPillsDispensed(60);
  };

  const removeMedication = (id: string) => {
    setMedications(medications.filter((m) => m.id !== id));
  };

  // Step transitions
  const onStep1Submit = () => {
    setStep(2);
  };

  const onStep2Proceed = () => {
    if (medications.length === 0) {
      setMedError("Please add at least one medication before proceeding");
      return;
    }
    setStep(3);
  };

  // Final Submission
  const handleFinalSubmit = async (patientData: PatientFormData) => {
    setIsSubmitting(true);
    try {
      // 1. Create Patient
      const patientPayload = {
        name: patientData.name.trim(),
        phone: `+91${patientData.phone10.trim()}`,
        language: patientData.language,
        family_contact_name: patientData.familyContactName?.trim() || null,
        family_whatsapp: patientData.familyContactPhone10?.trim()
          ? `+91${patientData.familyContactPhone10.trim()}`
          : null,
      };

      const { data: newPatient } = await api.post("/patients/", patientPayload);

      // 2. Add each medication
      for (const med of medications) {
        await api.post(`/patients/${newPatient.id}/medications`, {
          name: med.name,
          dosage: med.dosage,
          frequency: med.frequency,
          meal_timing: med.meal_timing,
          prescription_duration_days: med.prescription_duration_days,
          pills_dispensed: med.pills_dispensed,
          prescription_start_date: med.prescription_start_date,
        });
      }

      setCreatedPatientId(newPatient.id);
      setStep(4);

      // Launch celebratory confetti
      try {
        confetti({
          particleCount: 120,
          spread: 80,
          origin: { y: 0.6 },
        });
      } catch {}
    } catch (err: any) {
      console.error(err);
      alert(err?.response?.data?.detail || "Failed to onboard patient");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Trigger test call
  const handleTriggerTestCall = async () => {
    if (!createdPatientId) return;
    try {
      await api.post(`/dashboard/trigger-call/${createdPatientId}`);
      setCallTriggered(true);
    } catch (err: any) {
      alert("Could not connect to Bolna API: " + (err?.response?.data?.detail || err.message));
    }
  };

  // Unique slots gathered across all added medications
  const allUsedSlots = Array.from(
    new Set(medications.flatMap((m) => m.frequency))
  );

  return (
    <div className="min-h-screen bg-[#faf8f5] py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center justify-between">
          <Link
            href="/admin/patients"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-emerald-700 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Patients</span>
          </Link>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Automated Voice Enrollment</span>
          </div>
        </div>

        {/* Brand Header */}
        <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-emerald-600 text-white flex items-center justify-center shrink-0 shadow-md shadow-emerald-700/20">
              <Heart className="w-6 h-6 fill-white text-white" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                Patient Onboarding
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Register voice demographics, prescriptions, and custom call slots
              </p>
            </div>
          </div>

          {/* Stepper Pill Indicator */}
          {step <= 3 && (
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-500 bg-slate-100 px-3 py-1.5 rounded-full">
              <span className={step >= 1 ? "text-emerald-600 font-black" : ""}>1</span>
              <span>&rarr;</span>
              <span className={step >= 2 ? "text-emerald-600 font-black" : ""}>2</span>
              <span>&rarr;</span>
              <span className={step === 3 ? "text-emerald-600 font-black" : ""}>3</span>
            </div>
          )}
        </div>

        {/* ================================================================ */}
        {/* STEP 1: PATIENT DETAILS */}
        {/* ================================================================ */}
        {step === 1 && (
          <form onSubmit={handleSubmit(onStep1Submit)} className="space-y-6">
            <Card className="bg-white rounded-3xl border-slate-200 shadow-sm overflow-hidden">
              <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
                <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <User className="w-4 h-4 text-emerald-600" />
                  <span>Step 1: Patient Information</span>
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Primary voice contact and family emergency WhatsApp numbers
                </CardDescription>
              </CardHeader>
              <CardContent className="p-6 sm:p-8 space-y-5">
                {/* Name */}
                <div className="space-y-1.5">
                  <Label htmlFor="name" className="text-xs font-bold text-slate-700">
                    Patient Full Name *
                  </Label>
                  <Input
                    id="name"
                    placeholder="e.g. Ramesh Patel"
                    {...register("name")}
                    className="bg-slate-50/50 text-sm"
                  />
                  {errors.name && (
                    <p className="text-xs text-rose-600 font-medium">{errors.name.message}</p>
                  )}
                </div>

                {/* Phone */}
                <div className="space-y-1.5">
                  <Label htmlFor="phone10" className="text-xs font-bold text-slate-700">
                    Patient Phone Number *
                  </Label>
                  <div className="flex items-center">
                    <span className="inline-flex items-center px-3 py-2 rounded-l-md border border-r-0 border-slate-200 bg-slate-100 text-slate-600 text-sm font-mono font-semibold">
                      +91
                    </span>
                    <Input
                      id="phone10"
                      maxLength={10}
                      placeholder="9876543210"
                      {...register("phone10")}
                      className="rounded-l-none font-mono bg-slate-50/50 text-sm"
                    />
                  </div>
                  {errors.phone10 && (
                    <p className="text-xs text-rose-600 font-medium">{errors.phone10.message}</p>
                  )}
                  <p className="text-[11px] text-slate-400">
                    Bolna AI voice call reminders will be placed to this number.
                  </p>
                </div>

                {/* Language Select */}
                <div className="space-y-1.5">
                  <Label className="text-xs font-bold text-slate-700">
                    Preferred Language *
                  </Label>
                  <Controller
                    name="language"
                    control={control}
                    render={({ field }) => (
                      <Select
                        value={field.value}
                        onValueChange={(val) => val && field.onChange(val)}
                      >
                        <SelectTrigger className="bg-slate-50/50 text-sm">
                          <SelectValue placeholder="Select language" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="hindi">Hindi (हिंदी) — Bolna Agent Active</SelectItem>
                          <SelectItem value="tamil">Tamil (தமிழ்) — Bolna Agent Active</SelectItem>
                          <SelectItem value="english">English</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>

                {/* Family Contact Name & Phone */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
                  <div className="space-y-1.5">
                    <Label htmlFor="familyContactName" className="text-xs font-bold text-slate-700">
                      Family Contact Name
                    </Label>
                    <Input
                      id="familyContactName"
                      placeholder="e.g. Priya (Daughter)"
                      {...register("familyContactName")}
                      className="bg-slate-50/50 text-sm"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="familyContactPhone10" className="text-xs font-bold text-slate-700">
                      Family WhatsApp Number
                    </Label>
                    <div className="flex items-center">
                      <span className="inline-flex items-center px-3 py-2 rounded-l-md border border-r-0 border-slate-200 bg-slate-100 text-slate-600 text-sm font-mono font-semibold">
                        +91
                      </span>
                      <Input
                        id="familyContactPhone10"
                        maxLength={10}
                        placeholder="9876543210"
                        {...register("familyContactPhone10")}
                        className="rounded-l-none font-mono bg-slate-50/50 text-sm"
                      />
                    </div>
                    {errors.familyContactPhone10 && (
                      <p className="text-xs text-rose-600 font-medium">
                        {errors.familyContactPhone10.message}
                      </p>
                    )}
                  </div>
                </div>

                {/* Pharmacy Select */}
                <div className="space-y-1.5 pt-2">
                  <Label className="text-xs font-bold text-slate-700">
                    Dispensing Pharmacy
                  </Label>
                  <Controller
                    name="pharmacy"
                    control={control}
                    render={({ field }) => (
                      <Select
                        value={field.value}
                        onValueChange={(val) => val && field.onChange(val)}
                      >
                        <SelectTrigger className="bg-slate-50/50 text-sm">
                          <SelectValue placeholder="Select pharmacy" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">None / Direct Patient</SelectItem>
                          <SelectItem value="apollo">Apollo Pharmacy - Central</SelectItem>
                          <SelectItem value="medplus">MedPlus Pharmacy - Anna Nagar</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  />
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end">
              <Button
                type="submit"
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2 px-6"
              >
                <span>Continue to Medications</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </form>
        )}

        {/* ================================================================ */}
        {/* STEP 2: MEDICATIONS (MULTIPLE) */}
        {/* ================================================================ */}
        {step === 2 && (
          <div className="space-y-6">
            {/* Added Medications list */}
            {medications.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold text-slate-800">
                  Added Prescriptions ({medications.length})
                </h3>
                <div className="space-y-2.5">
                  {medications.map((m) => (
                    <div
                      key={m.id}
                      className="p-4 rounded-2xl border border-emerald-200 bg-white shadow-xs flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0">
                          <Pill className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-bold text-slate-900 text-sm">{m.name}</h4>
                            <span className="text-xs text-slate-500 font-medium">
                              ({m.dosage})
                            </span>
                            <Badge variant="outline" className="text-[10px] bg-slate-50 capitalize">
                              {m.meal_timing.replace("_", " ")}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-1.5 mt-1">
                            {m.frequency.map((f) => (
                              <Badge key={f} variant="outline" className="text-[9px] capitalize">
                                {f}
                              </Badge>
                            ))}
                            <span className="text-[11px] text-slate-400 ml-2">
                              {m.pills_dispensed} pills dispensed ({m.prescription_duration_days}d)
                            </span>
                          </div>
                        </div>
                      </div>

                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => removeMedication(m.id)}
                        className="text-slate-400 hover:text-rose-600 hover:bg-rose-50 h-8 w-8 p-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Form to add another medication */}
            <Card className="bg-white rounded-3xl border-slate-200 shadow-sm">
              <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
                <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Pill className="w-4 h-4 text-emerald-600" />
                  <span>Step 2: Add Medication</span>
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Prescribe a medication and select reminder intervals
                </CardDescription>
              </CardHeader>
              <CardContent className="p-6 sm:p-8 space-y-4">
                {medError && (
                  <p className="text-xs text-rose-600 font-semibold p-2 bg-rose-50 rounded-lg border border-rose-200">
                    {medError}
                  </p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold text-slate-700">
                      Medication Name *
                    </Label>
                    <Input
                      placeholder="e.g. Metformin 500mg, Telmisartan 40mg"
                      value={currentMedName}
                      onChange={(e) => setCurrentMedName(e.target.value)}
                      className="bg-slate-50/50 text-sm"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold text-slate-700">
                      Dosage *
                    </Label>
                    <Input
                      placeholder="e.g. 1 tablet, 5ml"
                      value={currentMedDosage}
                      onChange={(e) => setCurrentMedDosage(e.target.value)}
                      className="bg-slate-50/50 text-sm"
                    />
                  </div>
                </div>

                {/* Frequency multi-checkboxes */}
                <div className="space-y-2">
                  <Label className="text-xs font-bold text-slate-700">
                    Frequency Checkboxes *
                  </Label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {["morning", "afternoon", "evening", "night"].map((slot) => {
                      const isSelected = currentFrequency.includes(slot);
                      return (
                        <button
                          key={slot}
                          type="button"
                          onClick={() => toggleFrequencySlot(slot)}
                          className={`p-2.5 rounded-xl border text-xs font-semibold capitalize text-center transition-all ${
                            isSelected
                              ? "bg-emerald-50 border-emerald-500 text-emerald-900 font-bold"
                              : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          {slot}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Meal relation radio buttons */}
                <div className="space-y-2">
                  <Label className="text-xs font-bold text-slate-700">
                    Meal Relation
                  </Label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    {[
                      { id: "before_meal", label: "Before Meal" },
                      { id: "after_meal", label: "After Meal" },
                      { id: "with_meal", label: "With Meal" },
                      { id: "no_relation", label: "No Relation" },
                    ].map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => setCurrentMealRelation(m.id as any)}
                        className={`p-2.5 rounded-xl border text-xs font-semibold text-center transition-all ${
                          currentMealRelation === m.id
                            ? "bg-emerald-50 border-emerald-500 text-emerald-900 font-bold"
                            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                        }`}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Duration, Pills, Start date */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold text-slate-700">
                      Prescription Days
                    </Label>
                    <Input
                      type="number"
                      min={1}
                      value={currentDurationDays}
                      onChange={(e) => setCurrentDurationDays(parseInt(e.target.value) || 0)}
                      className="bg-slate-50/50 text-sm"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold text-slate-700">
                      Pills Dispensed
                    </Label>
                    <Input
                      type="number"
                      min={1}
                      value={currentPillsDispensed}
                      onChange={(e) => setCurrentPillsDispensed(parseInt(e.target.value) || 0)}
                      className="bg-slate-50/50 text-sm"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs font-bold text-slate-700">
                      Start Date
                    </Label>
                    <Input
                      type="date"
                      value={currentStartDate}
                      onChange={(e) => setCurrentStartDate(e.target.value)}
                      className="bg-slate-50/50 text-sm"
                    />
                  </div>
                </div>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleAddMedication}
                  className="w-full mt-2 border-emerald-300 text-emerald-800 hover:bg-emerald-50 font-bold text-xs gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add This Medication to List</span>
                </Button>
              </CardContent>
            </Card>

            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep(1)}
                className="border-slate-300 text-xs font-semibold"
              >
                &larr; Back to Patient Details
              </Button>

              <Button
                type="button"
                onClick={onStep2Proceed}
                disabled={medications.length === 0}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2 text-xs px-6"
              >
                <span>Continue to Call Schedule ({medications.length})</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* STEP 3: CALL SCHEDULE & REVIEW */}
        {/* ================================================================ */}
        {step === 3 && (
          <div className="space-y-6">
            <Card className="bg-white rounded-3xl border-slate-200 shadow-sm overflow-hidden">
              <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
                <CardTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-emerald-600" />
                  <span>Step 3: Call Schedule & Voice Greeting</span>
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Review automated call times generated for the patient&apos;s daily medication slots
                </CardDescription>
              </CardHeader>
              <CardContent className="p-6 sm:p-8 space-y-6">
                {/* Greeting Setting */}
                <div className="space-y-1.5">
                  <Label className="text-xs font-bold text-slate-700">
                    Preferred AI Voice Greeting
                  </Label>
                  <Input
                    value={preferredGreeting}
                    onChange={(e) => setPreferredGreeting(e.target.value)}
                    placeholder="e.g. Amma, Maata, Uncle"
                    className="bg-slate-50/50 text-sm font-medium"
                  />
                  <p className="text-[11px] text-slate-400">
                    The Bolna agent will address the patient as &quot;Namaste {preferredGreeting}&quot;
                    or &quot;Vanakkam {preferredGreeting}&quot;.
                  </p>
                </div>

                {/* Editable Slot Times */}
                <div className="space-y-3">
                  <Label className="text-xs font-bold text-slate-700">
                    Daily Voice Check-in Times (Auto-generated from medications)
                  </Label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {allUsedSlots.map((slot) => (
                      <div
                        key={slot}
                        className="p-3.5 rounded-2xl border border-slate-200 bg-slate-50/60 flex items-center justify-between"
                      >
                        <div>
                          <p className="font-bold text-sm text-slate-900 capitalize">
                            {slot} Call
                          </p>
                          <p className="text-[11px] text-slate-400">
                            Default: {DEFAULT_SLOT_TIMES[slot] || "09:00"}
                          </p>
                        </div>
                        <Input
                          type="time"
                          value={slotTimes[slot] || DEFAULT_SLOT_TIMES[slot] || "09:00"}
                          onChange={(e) =>
                            setSlotTimes({ ...slotTimes, [slot]: e.target.value })
                          }
                          className="w-28 text-xs font-mono bg-white"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Summary Box */}
                <div className="p-4 rounded-2xl border border-emerald-200 bg-emerald-50/40 space-y-2 text-xs">
                  <p className="font-bold text-emerald-950 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Ready for Enrollment
                  </p>
                  <p className="text-emerald-800">
                    Patient <strong>{watch("name")}</strong> will receive {allUsedSlots.length} daily
                    voice reminder call{allUsedSlots.length !== 1 ? "s" : ""} in{" "}
                    <strong className="capitalize">{selectedLanguage}</strong> for{" "}
                    <strong>{medications.length}</strong> prescribed medication{medications.length !== 1 ? "s" : ""}.
                  </p>
                </div>
              </CardContent>
            </Card>

            <div className="flex items-center justify-between pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep(2)}
                className="border-slate-300 text-xs font-semibold"
              >
                &larr; Back to Medications
              </Button>

              <Button
                type="button"
                disabled={isSubmitting}
                onClick={handleSubmit(handleFinalSubmit)}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2 text-sm px-8 shadow-md shadow-emerald-700/20"
              >
                <span>{isSubmitting ? "Creating Voice Profile..." : "Confirm & Enroll Patient"}</span>
                <Check className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* STEP 4: SUCCESS BANNER & IMMEDIATE TEST CALL */}
        {/* ================================================================ */}
        {step === 4 && createdPatientId && (
          <Card className="bg-white rounded-3xl border-emerald-200 shadow-md p-6 sm:p-8 space-y-6 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-9 h-9" />
            </div>

            <div>
              <h2 className="text-2xl font-black text-slate-900 tracking-tight">
                Patient Successfully Enrolled!
              </h2>
              <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
                Voice schedules are active. The Bolna AI voice agent will call at the scheduled
                times and automatically log adherence responses.
              </p>
            </div>

            {/* Shareable Family Link */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 text-left space-y-2">
              <Label className="text-xs font-bold text-slate-700">
                Shareable Family Dashboard Link
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  readOnly
                  value={
                    typeof window !== "undefined"
                      ? `${window.location.origin}/family/${createdPatientId}`
                      : `/family/${createdPatientId}`
                  }
                  className="bg-white text-xs font-mono"
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 gap-1.5 text-xs font-bold"
                  onClick={() => {
                    const url = `${window.location.origin}/family/${createdPatientId}`;
                    navigator.clipboard.writeText(url);
                    setCopiedLink(true);
                    setTimeout(() => setCopiedLink(false), 2000);
                  }}
                >
                  {copiedLink ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedLink ? "Copied" : "Copy"}</span>
                </Button>
              </div>
            </div>

            {/* Test Call Action */}
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button
                onClick={handleTriggerTestCall}
                disabled={callTriggered}
                className={`font-bold gap-2 text-xs px-6 ${
                  callTriggered
                    ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-100"
                    : "bg-emerald-600 hover:bg-emerald-700 text-white"
                }`}
              >
                <PhoneCall className="w-4 h-4" />
                <span>{callTriggered ? "Calling Now via Bolna..." : "Trigger Immediate Test Call"}</span>
              </Button>

              <Button
                variant="outline"
                onClick={() => router.push(`/admin/patients/${createdPatientId}`)}
                className="text-xs font-bold border-slate-300"
              >
                Go to Patient Profile &rarr;
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
