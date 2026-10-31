"""Pydantic v2 request / response schemas for the Nalam API."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import (
    ConsentStatusEnum,
    LanguageEnum,
    MealTimingEnum,
    SeverityEnum,
)


# ===== Generic Pagination =====

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T] = Field(default_factory=list)
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
    name: str = Field(min_length=1, max_length=255)
    dosage: str = Field(min_length=1, max_length=100)
    frequency: list[str] = Field(min_length=1, max_length=8)  # e.g. ["morning", "evening"]
    meal_timing: MealTimingEnum  # before_meal | after_meal | with_meal | no_relation
    prescription_duration_days: int | None = Field(default=None, gt=0)
    pills_dispensed: int | None = Field(default=None, ge=0)
    prescription_start_date: date | None = None

    # Accept legacy field name
    @model_validator(mode="before")
    @classmethod
    def _accept_meal_relation_alias(cls, data: object) -> object:
        if isinstance(data, dict) and "meal_relation" in data and "meal_timing" not in data:
            data["meal_timing"] = data.pop("meal_relation")
        if isinstance(data, dict) and "prescribed_duration_days" in data and "prescription_duration_days" not in data:
            data["prescription_duration_days"] = data.pop("prescribed_duration_days")
        return data

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, values: list[str]) -> list[str]:
        allowed = {"morning", "afternoon", "evening", "night"}
        normalized = [value.strip().lower() for value in values]
        if any(value not in allowed for value in normalized):
            raise ValueError("frequency must contain only morning, afternoon, evening, or night")
        if len(set(normalized)) != len(normalized):
            raise ValueError("frequency cannot contain duplicate time slots")
        return normalized


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    dosage: str | None = Field(default=None, min_length=1, max_length=100)
    frequency: list[str] | None = Field(default=None, min_length=1, max_length=8)
    meal_timing: MealTimingEnum | None = None
    prescription_duration_days: int | None = Field(default=None, gt=0)
    pills_dispensed: int | None = Field(default=None, ge=0)
    prescription_start_date: date | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_meal_relation_alias(cls, data: object) -> object:
        if isinstance(data, dict) and "meal_relation" in data and "meal_timing" not in data:
            data["meal_timing"] = data.pop("meal_relation")
        if isinstance(data, dict) and "prescribed_duration_days" in data and "prescription_duration_days" not in data:
            data["prescription_duration_days"] = data.pop("prescribed_duration_days")
        return data

    @field_validator("frequency")
    @classmethod
    def validate_frequency(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        allowed = {"morning", "afternoon", "evening", "night"}
        normalized = [value.strip().lower() for value in values]
        if any(value not in allowed for value in normalized):
            raise ValueError("frequency must contain only morning, afternoon, evening, or night")
        if len(set(normalized)) != len(normalized):
            raise ValueError("frequency cannot contain duplicate time slots")
        return normalized


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    dosage: str
    frequency: list[str]
    meal_timing: str
    prescription_duration_days: int | None = None
    pills_dispensed: int | None = None
    prescription_start_date: date | None = None
    is_active: bool
    created_at: datetime


# ===== Patient =====

_PHONE_RE = re.compile(r"^\+91\d{10}$")


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str  # +91XXXXXXXXXX
    language: LanguageEnum = LanguageEnum.tamil
    timezone_name: str = Field(
        default="Asia/Kolkata", validation_alias="timezone", serialization_alias="timezone"
    )
    consent_status: ConsentStatusEnum = ConsentStatusEnum.pending
    consent_at: datetime | None = None
    demo_only: bool = False
    family_contact_name: str | None = Field(default=None, max_length=255)
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
    def _accept_legacy_family_phone(cls, data: object) -> object:
        if isinstance(data, dict) and "family_contact_phone" in data and "family_whatsapp" not in data:
            data["family_whatsapp"] = data.pop("family_contact_phone")
        return data

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_consent_timestamp(self) -> "PatientCreate":
        if self.consent_status == ConsentStatusEnum.granted and self.consent_at is None:
            raise ValueError("consent_at is required when consent_status is granted")
        if self.consent_status != ConsentStatusEnum.granted and self.consent_at is not None:
            raise ValueError("consent_at is only valid for granted consent")
        return self


class PatientUpdate(BaseModel):
    """All fields optional — partial update."""
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = None
    language: LanguageEnum | None = None
    timezone_name: str | None = Field(
        default=None, validation_alias="timezone", serialization_alias="timezone"
    )
    consent_status: ConsentStatusEnum | None = None
    consent_at: datetime | None = None
    demo_only: bool | None = None
    family_contact_name: str | None = Field(default=None, max_length=255)
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
    def _accept_legacy_family_phone(cls, data: object) -> object:
        if isinstance(data, dict) and "family_contact_phone" in data and "family_whatsapp" not in data:
            data["family_whatsapp"] = data.pop("family_contact_phone")
        return data

    @field_validator("timezone_name")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    language: LanguageEnum
    timezone_name: str = Field(serialization_alias="timezone")
    consent_status: ConsentStatusEnum
    consent_at: datetime | None = None
    demo_only: bool
    family_contact_name: str | None = None
    family_whatsapp: str | None = None
    pharmacy_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PatientWithMedications(PatientResponse):
    medications: list[MedicationResponse] = Field(default_factory=list)
    adherence_score_7d: float | None = None
    adherence_score_30d: float | None = None
    recent_alerts: list[AlertResponse] = Field(default_factory=list)  # forward ref resolved below


# ===== AdherenceLog =====

class AdherenceLogCreate(BaseModel):
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    scheduled_time_slot: str | None = None
    call_time: datetime
    outcome: str
    side_effect_details: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    call_duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    bolna_call_id: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    scheduled_dose_id: uuid.UUID | None = None
    taken_late: bool = False
    source: str = Field(default="voice", min_length=1, max_length=32)
    follow_up_needed: bool = False
    retry_scheduled: bool = False

    @model_validator(mode="before")
    @classmethod
    def _accept_response_alias(cls, data: object) -> object:
        if isinstance(data, dict) and "response" in data and "outcome" not in data:
            data["outcome"] = data.pop("response")
        return data


class AdherenceLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    medication_id: uuid.UUID
    scheduled_dose_id: uuid.UUID | None = None
    call_record_id: uuid.UUID | None = None
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
    taken_late: bool = False
    side_effect_severity: str | None = None
    stock_out: bool = False
    source: str = "voice"
    idempotency_key: str | None = None
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
    scheduled_dose_id: uuid.UUID | None = None
    call_record_id: uuid.UUID | None = None
    delivery_status: str
    delivery_attempt_count: int
    provider_message_id: str | None = None
    delivered_at: datetime | None = None
    delivery_failure_reason: str | None = None
    resolved_at: datetime | None = None
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
    score_7d: float | None
    score_30d: float | None
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
    medications: list[DailyDoseItem] = Field(default_factory=list)


class TrendPoint(BaseModel):
    date: date
    score: float | None
    doses_taken: int
    doses_expected: int


# ===== Dashboard =====

class DashboardSummary(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    patient_phone: str = ""
    adherence_score_7d: float | None
    adherence_score_30d: float | None
    last_call_status: str | None = None
    medications_count: int
    alerts_today: int
    refill_due_medications: list[str] = Field(default_factory=list)


class AlertCountsBySeverity(BaseModel):
    critical: int = 0
    warning: int = 0
    info: int = 0


class AdminDashboardResponse(BaseModel):
    total_patients: int
    active_patients: int
    avg_adherence_7d: float | None
    avg_adherence_30d: float | None
    alerts_today: AlertCountsBySeverity
    patients_needing_refill: int
    patients: list[DashboardSummary] = Field(default_factory=list)


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
    patient_language: str = "tamil"
    today: list[TodayStatus] = Field(default_factory=list)
    adherence_score_7d: float | None
    adherence_score_30d: float | None
    trend: list[TrendPoint] = Field(default_factory=list)
    recent_alerts: list[AlertResponse] = Field(default_factory=list)
    medications: list[FamilyMedicationDetail] = Field(default_factory=list)
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
    call_ids: list[str] = Field(default_factory=list)


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
    extracted_data: dict[str, object] | None = None


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

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

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
    event_id: str | None = Field(default=None, min_length=1, max_length=255)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    scheduled_dose_id: str | None = None
    taken_late: bool | None = None
    side_effect_severity: SeverityEnum | None = None
    stock_out: bool | None = None
    patient_callback_requested: bool | None = None
    event_timestamp: datetime | None = None

    # Internal — populated by validator
    from pydantic import PrivateAttr

    _normalized_outcome: str = PrivateAttr(default="")
    _resolved_notes: str | None = PrivateAttr(default=None)

    @model_validator(mode="before")
    @classmethod
    def _normalise(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        # Resolve raw outcome string
        raw = data.get("outcome") or data.get("response") or "NO_ANSWER"
        normalised = _OUTCOME_LEGACY_MAP.get(str(raw).lower().strip(), str(raw).upper())
        if normalised not in {
            "TAKEN",
            "MISSED",
            "SIDE_EFFECT",
            "NO_ANSWER",
            "STOCK_OUT",
            "CALLBACK_REQUESTED",
        }:
            raise ValueError("outcome is not a supported medication response")

        # If side_effect_noted=True, force SIDE_EFFECT
        if data.get("side_effect_noted"):
            normalised = "SIDE_EFFECT"

        data["outcome"] = normalised

        patient_id = data.get("patient_id")
        try:
            uuid.UUID(str(patient_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("patient_id must be a valid UUID") from exc

        medication_id = data.get("medication_id")
        if medication_id is not None:
            try:
                uuid.UUID(str(medication_id))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("medication_id must be a valid UUID") from exc

        scheduled_dose_id = data.get("scheduled_dose_id")
        if scheduled_dose_id is not None:
            try:
                uuid.UUID(str(scheduled_dose_id))
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("scheduled_dose_id must be a valid UUID") from exc

        if not data.get("bolna_call_id"):
            stable_event_id = data.get("idempotency_key") or data.get("event_id") or data.get("call_id")
            if stable_event_id:
                data["bolna_call_id"] = str(stable_event_id)

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

    def model_post_init(self, __context: object) -> None:
        # Store normalised outcome as pseudo-private attribute
        object.__setattr__(self, "_normalized_outcome", self.outcome or "NO_ANSWER")
        object.__setattr__(self, "_resolved_notes", self.notes)


class BolnaFunctionResponse(BaseModel):
    status: str
    message: str


# Rebuild forward references
PatientWithMedications.model_rebuild()
