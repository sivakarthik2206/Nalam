"use client";

import { useState } from "react";
import { useAddMedication } from "@/lib/queries";
import { MedicationCreate, MealTiming } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
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
import { Pill, Plus } from "lucide-react";

interface MedicationFormProps {
  patientId: string;
  onSuccess?: () => void;
}

const AVAILABLE_SLOTS = [
  { id: "morning", label: "Morning (09:00 AM)" },
  { id: "afternoon", label: "Afternoon (02:00 PM)" },
  { id: "evening", label: "Evening (06:00 PM)" },
  { id: "night", label: "Night (09:00 PM)" },
];

export function MedicationForm({ patientId, onSuccess }: MedicationFormProps) {
  const [name, setName] = useState("");
  const [dosage, setDosage] = useState("1 tablet");
  const [frequency, setFrequency] = useState<string[]>(["morning", "evening"]);
  const [mealRelation, setMealRelation] = useState<MealTiming>("after_meal");
  const [durationDays, setDurationDays] = useState<number>(30);
  const [pillsDispensed, setPillsDispensed] = useState<number>(60);
  const [startDate, setStartDate] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [errorMsg, setErrorMsg] = useState("");

  const addMedication = useAddMedication(patientId);

  const toggleSlot = (slot: string) => {
    if (frequency.includes(slot)) {
      if (frequency.length > 1) {
        setFrequency(frequency.filter((s) => s !== slot));
      }
    } else {
      setFrequency([...frequency, slot]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (!name.trim()) {
      setErrorMsg("Medication name is required (e.g. Metformin 500mg)");
      return;
    }

    const payload: MedicationCreate = {
      name: name.trim(),
      dosage: dosage.trim() || "1 tablet",
      frequency,
      meal_timing: mealRelation,
      prescription_duration_days: durationDays || 30,
      pills_dispensed: pillsDispensed || 60,
      prescription_start_date: startDate || null,
    };

    addMedication.mutate(payload, {
      onSuccess: () => {
        setName("");
        setDosage("1 tablet");
        if (onSuccess) onSuccess();
      },
      onError: (err: any) => {
        setErrorMsg(err?.response?.data?.detail || "Failed to add medication");
      },
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {errorMsg && (
        <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-700 rounded-lg">
          {errorMsg}
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="med-name" className="text-xs font-semibold text-slate-700">
          Medication Name *
        </Label>
        <Input
          id="med-name"
          placeholder="e.g. Metformin 500mg, Amlodipine 5mg"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="text-sm bg-slate-50/50"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="med-dosage" className="text-xs font-semibold text-slate-700">
            Dosage *
          </Label>
          <Input
            id="med-dosage"
            placeholder="e.g. 1 tablet, 5ml"
            value={dosage}
            onChange={(e) => setDosage(e.target.value)}
            required
            className="text-sm bg-slate-50/50"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-slate-700">
            Meal Relation *
          </Label>
          <Select
            value={mealRelation}
            onValueChange={(val) => val && setMealRelation(val as MealTiming)}
          >
            <SelectTrigger className="text-sm bg-slate-50/50">
              <SelectValue placeholder="Select relation" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="before_meal">Before Meal (भोजन से पहले / உணவுக்கு முன்)</SelectItem>
              <SelectItem value="after_meal">After Meal (भोजन के बाद / உணவுக்கு பின்)</SelectItem>
              <SelectItem value="with_meal">With Meal (भोजन के साथ)</SelectItem>
              <SelectItem value="no_relation">No Relation</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Schedule Frequency Checklist */}
      <div className="space-y-2">
        <Label className="text-xs font-semibold text-slate-700">
          Daily Frequency & Call Times (Voice AI will call at these slots)
        </Label>
        <div className="grid grid-cols-2 gap-2">
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

      {/* Inventory & Duration */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="med-dispensed" className="text-xs font-semibold text-slate-700">
            Pills Dispensed
          </Label>
          <Input
            id="med-dispensed"
            type="number"
            min={1}
            value={pillsDispensed}
            onChange={(e) => setPillsDispensed(parseInt(e.target.value) || 0)}
            className="text-sm bg-slate-50/50"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="med-days" className="text-xs font-semibold text-slate-700">
            Duration (Days)
          </Label>
          <Input
            id="med-days"
            type="number"
            min={1}
            value={durationDays}
            onChange={(e) => setDurationDays(parseInt(e.target.value) || 0)}
            className="text-sm bg-slate-50/50"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="med-start" className="text-xs font-semibold text-slate-700">
            Start Date
          </Label>
          <Input
            id="med-start"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="text-sm bg-slate-50/50"
          />
        </div>
      </div>

      <Button
        type="submit"
        disabled={addMedication.isPending}
        className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-sm mt-2"
      >
        <Plus className="w-4 h-4 mr-2" />
        {addMedication.isPending ? "Creating Schedule..." : "Add Medication & Auto-Schedule Calls"}
      </Button>
    </form>
  );
}
