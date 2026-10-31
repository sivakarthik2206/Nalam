/**
 * TypeScript types matching all backend Pydantic schemas exactly.
 */

export type Language = "hindi" | "tamil" | "english";
export type MealRelation = "before_meal" | "after_meal" | "with_meal" | "no_relation";
export type MealTiming = MealRelation;
export type TimeSlot = "morning" | "afternoon" | "evening" | "night";
export type AdherenceResponse = "taken" | "not_taken" | "side_effect" | "no_answer" | "stock_out" | "callback_requested";
export type AdherenceOutcome = "TAKEN" | "MISSED" | "SIDE_EFFECT" | "NO_ANSWER" | "STOCK_OUT" | "CALLBACK_REQUESTED";
export type AlertType = "missed_dose" | "no_answer" | "side_effect" | "low_adherence" | "stock_out" | "refill_due";
export type AlertSeverity = "info" | "warning" | "critical";
export type AlertChannel = "whatsapp" | "sms" | "dashboard";

// ===== Pagination =====
export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
}

// ===== Pharmacy =====
export interface Pharmacy {
  id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface PharmacyCreate {
  name: string;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
}

// ===== Patient =====
export interface Patient {
  id: string;
  name: string;
  phone: string;
  language: Language;
  family_contact_name?: string | null;
  family_whatsapp?: string | null;
  pharmacy_id?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PatientCreate {
  name: string;
  phone: string;
  language?: Language;
  family_contact_name?: string | null;
  family_whatsapp?: string | null;
  pharmacy_id?: string | null;
}

export interface PatientUpdate {
  name?: string;
  phone?: string;
  language?: Language;
  family_contact_name?: string | null;
  family_whatsapp?: string | null;
  pharmacy_id?: string | null;
  is_active?: boolean;
}

export interface PatientResponse extends Patient {}

export interface PatientWithMedications extends Patient {
  medications: Medication[];
  adherence_score_7d: number;
  adherence_score_30d: number;
  recent_alerts: Alert[];
}

// ===== Medication =====
export interface Medication {
  id: string;
  patient_id: string;
  name: string;
  dosage: string;
  frequency: string[];
  meal_timing: MealTiming;
  prescription_duration_days?: number | null;
  pills_dispensed?: number | null;
  prescription_start_date?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface MedicationCreate {
  name: string;
  dosage: string;
  frequency: string[];
  meal_timing: MealTiming;
  prescription_duration_days?: number | null;
  pills_dispensed?: number | null;
  prescription_start_date?: string | null;
}

export interface MedicationUpdate {
  name?: string;
  dosage?: string;
  frequency?: string[];
  meal_timing?: MealTiming;
  prescription_duration_days?: number | null;
  pills_dispensed?: number | null;
  prescription_start_date?: string | null;
  is_active?: boolean;
}

export interface MedicationResponse extends Medication {}

// ===== AdherenceLog =====
export interface AdherenceLog {
  id: string;
  patient_id: string;
  medication_id: string;
  scheduled_time_slot?: TimeSlot | string | null;
  call_time: string;
  outcome: AdherenceOutcome | string;
  notes?: string | null;
  retry_scheduled?: boolean;
  side_effect_details?: string | null;
  call_duration_seconds?: number | null;
  bolna_call_id?: string | null;
  follow_up_needed: boolean;
  follow_up_completed: boolean;
  created_at: string;
}

export interface AdherenceLogCreate {
  patient_id: string;
  medication_id: string;
  scheduled_time_slot?: string | null;
  call_time: string;
  outcome: string;
  notes?: string | null;
  side_effect_details?: string | null;
  call_duration_seconds?: number | null;
  bolna_call_id?: string | null;
  follow_up_needed?: boolean;
}

export interface AdherenceLogResponse extends AdherenceLog {}

// ===== Alert =====
export interface Alert {
  id: string;
  patient_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  message: string;
  sent_to?: string | null;
  channel: AlertChannel;
  is_read: boolean;
  created_at: string;
}

export interface AlertResponse extends Alert {}

export interface AlertCountsBySeverity {
  critical: number;
  warning: number;
  info: number;
}

// ===== CallSchedule =====
export interface CallSchedule {
  id: string;
  patient_id: string;
  medication_id: string;
  time_slot?: TimeSlot | string | null;
  scheduled_hour: number;
  scheduled_minute: number;
  is_active: boolean;
  last_call_at?: string | null;
  next_call_at?: string | null;
}

export interface CallScheduleCreate {
  patient_id: string;
  medication_id: string;
  time_slot?: string | null;
  scheduled_hour: number;
  scheduled_minute?: number;
}

// ===== Dashboard =====
export interface DashboardSummary {
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  adherence_score_7d: number;
  adherence_score_30d: number;
  last_call_status?: string | null;
  medications_count: number;
  alerts_today: number;
  refill_due_medications: string[];
}

export interface AdminDashboardResponse {
  total_patients: number;
  active_patients: number;
  avg_adherence_7d: number;
  avg_adherence_30d: number;
  alerts_today: AlertCountsBySeverity;
  patients_needing_refill: number;
  patients: DashboardSummary[];
}

// ===== Family Dashboard =====
export interface TodayStatus {
  time_slot: string;
  medication_name: string;
  name?: string;
  status: "taken" | "not_taken" | "pending";
}

export interface FamilyMedicationDetail {
  name: string;
  dosage: string;
  meal_timing: string;
  frequency: string[];
  pills_remaining?: number | null;
  days_until_refill?: number | null;
}

export interface FamilyDashboard {
  patient_name: string;
  patient_language: Language;
  today: TodayStatus[];
  adherence_score_7d: number;
  adherence_score_30d: number;
  trend: TrendPoint[];
  recent_alerts: AlertResponse[];
  medications: FamilyMedicationDetail[];
  next_scheduled_call?: string | null;
  family_contact_name?: string | null;
}

// ===== Adherence Trend & Score =====
export interface AdherenceScoreResponse {
  patient_id: string;
  score_7d: number;
  score_30d: number;
  total_doses_expected: number;
  total_doses_taken: number;
  streak_current: number;
  streak_best: number;
}

export interface DailyDoseItem {
  name: string;
  time_slot: string;
  meal_timing: string;
  status: "taken" | "missed" | "pending" | "side_effect";
  logged_at?: string | null;
  medication_id?: string | null;
  medication_name?: string | null;
}

export interface DailyAdherenceResponse {
  patient_name: string;
  date: string;
  medications: DailyDoseItem[];
}

export interface TrendPoint {
  date: string;
  score: number;
  doses_taken?: number;
  doses_expected?: number;
}

export type AdherenceTrend = TrendPoint[];

// ===== Refills & Actions =====
export interface RefillInfo {
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  medication_name: string;
  pills_remaining: number;
  days_remaining: number;
  refill_urgent: boolean;
}

export interface ManualCallResponse {
  calls_triggered: number;
  call_ids: string[];
}

// ===== Patient Summary =====
export interface PatientSummary {
  patient_name: string;
  patient_language: string;
  today_call_status: string; // e.g. "TAKEN", "MISSED", "pending"
  adherence_score_7d: number;
  medications: Array<{
    name: string;
    dosage: string;
    meal_timing: string;
    frequency: string[];
    last_confirmed_time?: string | null;
  }>;
  recent_alerts: AlertResponse[];
  refill_due: Array<{
    medication_name: string;
    days_remaining: number;
  }>;
}
