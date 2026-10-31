"""Pydantic v2 request / response schemas for the Nalam API."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ===== Generic Pagination =====

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T] = []  # type: ignore[misc]
    meta: PaginationMeta


# ===== Pharmacy =====

class PharmacyCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class PharmacyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    is_active: bool
    created_at: datetime


# ===== Medication =====

class MedicationCreate(BaseModel):
    name: str
    dosage: str
    frequency: list[str]  # e.g. ["morning", "evening"]
    meal_relation: str  # before_meal | after_meal | with_meal | no_relation
    prescribed_duration_days: int | None = None
    pills_dispensed: int | None = None
    prescription_start_date: date | None = None


class MedicationUpdate(BaseModel):
    name: str | None = None
    dosage: str | None = None
    frequency: list[str] | None = None
    meal_relation: str | None = None
    prescribed_duration_days: int | None = None
    pills_dispensed: int | None = None
    prescription_start_date: date | None = None
    is_active: bool | None = None


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    dosage: str
    frequency: Any
    meal_relation: str
    prescribed_duration_days: int | None = None
    pills_dispensed: int | None = None
    prescription_start_date: date | None = None
    is_active: bool
    created_at: datetime


# ===== Patient =====

_PHONE_RE = re.compile(r"^\+91\d{10}$")


class PatientCreate(BaseModel):
    name: str
    phone: str  # +91XXXXXXXXXX
    language: str = "hindi"
    family_contact_name: str | None = None
    family_contact_phone: str | None = None
    pharmacy_id: uuid.UUID | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not _PHONE_RE.match(v):
            raise ValueError("Phone must match +91 followed by 10 digits (e.g. +919876543210)")
        return v


class PatientUpdate(BaseModel):
    """All fields optional — partial update."""
    name: str | None = None
    phone: str | None = None
    language: str | None = None
    family_contact_name: str | None = None
    family_contact_phone: str | None = None
    pharmacy_id: uuid.UUID | None = None
    is_active: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not _PHONE_RE.match(v):
            raise ValueError("Phone must match +91 followed by 10 digits")
        return v


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    language: str
    family_contact_name: str | None = None
    family_contact_phone: str | None = None
    pharmacy_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PatientWithMedications(PatientResponse):
    medications: list[MedicationResponse] = []
    adherence_score_7d: float = 0.0
    adherence_score_30d: float = 0.0
    recent_alerts: list[AlertResponse] = []  # forward ref resolved below


# ===== AdherenceLog =====

class AdherenceLogCreate(BaseModel):
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    scheduled_time_slot: str | None = None
    call_time: datetime
    response: str
    side_effect_details: str | None = None
    call_duration_seconds: int | None = None
    bolna_call_id: str | None = None
    follow_up_needed: bool = False


class AdherenceLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    scheduled_time_slot: str | None = None
    call_time: datetime
    response: str
    side_effect_details: str | None = None
    call_duration_seconds: int | None = None
    bolna_call_id: str | None = None
    follow_up_needed: bool
    follow_up_completed: bool
    created_at: datetime


# ===== Alert =====

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    alert_type: str
    severity: str
    message: str
    sent_to: str | None = None
    channel: str
    is_read: bool
    created_at: datetime


# ===== CallSchedule =====

class CallScheduleCreate(BaseModel):
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    time_slot: str | None = None
    scheduled_hour: int = Field(ge=0, le=23)
    scheduled_minute: int = Field(ge=0, le=59, default=0)


class CallScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    time_slot: str | None = None
    scheduled_hour: int
    scheduled_minute: int
    is_active: bool
    last_call_at: datetime | None = None
    next_call_at: datetime | None = None


# ===== Adherence Score / Trend =====

class AdherenceScoreResponse(BaseModel):
    patient_id: uuid.UUID
    score_7d: float
    score_30d: float
    total_doses_expected: int
    total_doses_taken: int
    streak_current: int
    streak_best: int


class DailyDoseItem(BaseModel):
    name: str
    time_slot: str
    meal_relation: str
    status: str  # taken | missed | pending | side_effect
    logged_at: datetime | None = None
    medication_id: uuid.UUID | None = None
    medication_name: str | None = None


class DailyAdherenceResponse(BaseModel):
    patient_name: str
    date: date
    medications: list[DailyDoseItem] = []


class TrendPoint(BaseModel):
    date: date
    score: float
    doses_taken: int
    doses_expected: int


# ===== Dashboard =====

class DashboardSummary(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: str = ""
    adherence_score_7d: float
    adherence_score_30d: float
    last_call_status: str | None = None
    medications_count: int
    alerts_today: int
    refill_due_medications: list[str] = []


class AlertCountsBySeverity(BaseModel):
    critical: int = 0
    warning: int = 0
    info: int = 0


class AdminDashboardResponse(BaseModel):
    total_patients: int
    active_patients: int
    avg_adherence_7d: float
    avg_adherence_30d: float
    alerts_today: AlertCountsBySeverity
    patients_needing_refill: int
    patients: list[DashboardSummary] = []


class MedicationLastTaken(BaseModel):
    medication_name: str
    last_taken_at: datetime | None = None


class TodayStatus(BaseModel):
    time_slot: str
    medication_name: str
    name: str = ""
    status: str  # taken | not_taken | pending


class FamilyMedicationDetail(BaseModel):
    name: str
    dosage: str
    meal_relation: str
    frequency: list[str] = []
    pills_remaining: int | None = None
    days_until_refill: float | None = None


class FamilyDashboard(BaseModel):
    patient_name: str
    patient_language: str = "hindi"
    today: Any = []
    adherence_score_7d: float
    adherence_score_30d: float
    trend: list[TrendPoint] = []
    recent_alerts: list[AlertResponse] = []
    medications: list[FamilyMedicationDetail] = []
    next_scheduled_call: datetime | None = None
    family_contact_name: str | None = None


class RefillInfo(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: str
    medication_name: str
    pills_remaining: int
    days_remaining: float
    refill_urgent: bool


class ManualCallResponse(BaseModel):
    calls_triggered: int
    call_ids: list[str] = []


# ===== Bolna Webhook =====

class BolnaWebhookPayload(BaseModel):
    """Full post-call webhook from Bolna."""
    call_id: str
    agent_id: str
    recipient_phone: str
    call_status: str
    call_duration: int | None = None
    transcript: str | None = None
    extracted_data: dict[str, Any] | None = None


class BolnaFunctionPayload(BaseModel):
    """Real-time function call payload sent BY Bolna DURING a call."""
    patient_id: str
    medication_id: str
    time_slot: str
    response: str
    side_effect_details: str | None = None
    bolna_call_id: str | None = None
    call_duration: int | None = None


class BolnaFunctionResponse(BaseModel):
    status: str
    message: str


# Rebuild forward references
PatientWithMedications.model_rebuild()
