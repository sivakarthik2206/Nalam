"""Pydantic v2 request / response schemas for the Nalam API."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
    meal_timing: str  # before_meal | after_meal | with_meal | no_relation
    prescription_duration_days: int | None = None
    pills_dispensed: int | None = None
    prescription_start_date: date | None = None

    # Accept legacy field name
    @model_validator(mode="before")
    @classmethod
    def _accept_meal_relation_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "meal_relation" in data and "meal_timing" not in data:
            data["meal_timing"] = data.pop("meal_relation")
        if isinstance(data, dict) and "prescribed_duration_days" in data and "prescription_duration_days" not in data:
            data["prescription_duration_days"] = data.pop("prescribed_duration_days")
        return data


class MedicationUpdate(BaseModel):
    name: str | None = None
    dosage: str | None = None
    frequency: list[str] | None = None
    meal_timing: str | None = None
    prescription_duration_days: int | None = None
    pills_dispensed: int | None = None
    prescription_start_date: date | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_meal_relation_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "meal_relation" in data and "meal_timing" not in data:
            data["meal_timing"] = data.pop("meal_relation")
        if isinstance(data, dict) and "prescribed_duration_days" in data and "prescription_duration_days" not in data:
            data["prescription_duration_days"] = data.pop("prescribed_duration_days")
        return data


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    dosage: str
    frequency: Any
    meal_timing: str
    prescription_duration_days: int | None = None
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
    family_whatsapp: str | None = None
    pharmacy_id: uuid.UUID | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not _PHONE_RE.match(v):
            raise ValueError("Phone must match +91 followed by 10 digits (e.g. +919876543210)")
        return v

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_family_phone(cls, data: Any) -> Any:
        if isinstance(data, dict) and "family_contact_phone" in data and "family_whatsapp" not in data:
            data["family_whatsapp"] = data.pop("family_contact_phone")
        return data


class PatientUpdate(BaseModel):
    """All fields optional — partial update."""
    name: str | None = None
    phone: str | None = None
    language: str | None = None
    family_contact_name: str | None = None
    family_whatsapp: str | None = None
    pharmacy_id: uuid.UUID | None = None
    is_active: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is not None and not _PHONE_RE.match(v):
            raise ValueError("Phone must match +91 followed by 10 digits")
        return v

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_family_phone(cls, data: Any) -> Any:
        if isinstance(data, dict) and "family_contact_phone" in data and "family_whatsapp" not in data:
            data["family_whatsapp"] = data.pop("family_contact_phone")
        return data


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    language: str
    family_contact_name: str | None = None
    family_whatsapp: str | None = None
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
    outcome: str
    side_effect_details: str | None = None
    notes: str | None = None
    call_duration_seconds: int | None = None
    bolna_call_id: str | None = None
    follow_up_needed: bool = False
    retry_scheduled: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_response_alias(cls, data: Any) -> Any:
        if isinstance(data, dict) and "response" in data and "outcome" not in data:
            data["outcome"] = data.pop("response")
        return data


class AdherenceLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    scheduled_time_slot: str | None = None
    call_time: datetime
    outcome: str
    side_effect_details: str | None = None
    notes: str | None = None
    call_duration_seconds: int | None = None
    bolna_call_id: str | None = None
    follow_up_needed: bool
    follow_up_completed: bool
    retry_scheduled: bool = False
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
    meal_timing: str
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
    meal_timing: str
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

# Legacy post-call webhook (kept for backward compat)
class BolnaPostCallWebhookPayload(BaseModel):
    """Full post-call webhook from Bolna."""
    call_id: str
    agent_id: str
    recipient_phone: str
    call_status: str
    call_duration: int | None = None
    transcript: str | None = None
    extracted_data: dict[str, Any] | None = None


# Legacy function payload (kept for backward compat)
class BolnaFunctionPayload(BaseModel):
    """Real-time function call payload sent BY Bolna DURING a call (legacy)."""
    patient_id: str
    medication_id: str
    time_slot: str = "morning"
    response: str = "no_answer"
    side_effect_details: str | None = None
    bolna_call_id: str | None = None
    call_duration: int | None = None


# New unified webhook payload
_OUTCOME_LEGACY_MAP: dict[str, str] = {
    "taken": "TAKEN",
    "not_taken": "MISSED",
    "missed": "MISSED",
    "side_effect": "SIDE_EFFECT",
    "no_answer": "NO_ANSWER",
    "stock_out": "STOCK_OUT",
    "callback_requested": "CALLBACK_REQUESTED",
    "rescheduled": "CALLBACK_REQUESTED",
}

_RETRY_OUTCOMES = {"MISSED", "NO_ANSWER"}


class BolnaWebhookPayload(BaseModel):
    """Unified function-call payload — accepts both new spec shape and legacy shape."""

    model_config = ConfigDict(populate_by_name=True)

    # Required
    patient_id: str

    # Spec fields
    outcome: str | None = None
    medication_id: str | None = None
    side_effect_noted: bool | None = None
    retry_required: bool | None = None
    notes: str | None = None

    # Legacy fields
    response: str | None = None
    side_effect_notes: str | None = None
    response_text: str | None = None
    time_slot: str | None = None
    bolna_call_id: str | None = None
    call_duration: int | None = None

    # Internal — populated by validator
    _normalized_outcome: str = ""
    _resolved_notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Resolve raw outcome string
        raw = data.get("outcome") or data.get("response") or "NO_ANSWER"
        normalised = _OUTCOME_LEGACY_MAP.get(str(raw).lower().strip(), str(raw).upper())

        # If side_effect_noted=True, force SIDE_EFFECT
        if data.get("side_effect_noted"):
            normalised = "SIDE_EFFECT"

        data["outcome"] = normalised

        # Resolve notes
        resolved_notes = data.get("notes") or data.get("side_effect_notes") or data.get("response_text")
        data["notes"] = resolved_notes

        # Resolve retry_required
        explicit_retry = data.get("retry_required")
        if explicit_retry is None:
            data["retry_required"] = normalised in _RETRY_OUTCOMES
        else:
            data["retry_required"] = bool(explicit_retry) or (normalised in _RETRY_OUTCOMES)

        return data

    def model_post_init(self, __context: Any) -> None:
        # Store normalised outcome as pseudo-private attribute
        object.__setattr__(self, "_normalized_outcome", self.outcome or "NO_ANSWER")
        object.__setattr__(self, "_resolved_notes", self.notes)


class BolnaFunctionResponse(BaseModel):
    status: str
    message: str


# Rebuild forward references
PatientWithMedications.model_rebuild()
