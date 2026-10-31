"""SQLAlchemy ORM models for the Nalam medication-adherence platform."""

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LanguageEnum(str, enum.Enum):
    hindi = "hindi"
    tamil = "tamil"
    english = "english"


class MealTimingEnum(str, enum.Enum):
    before_meal = "before_meal"
    after_meal = "after_meal"
    with_meal = "with_meal"
    no_relation = "no_relation"


# Backwards-compat alias
MealRelationEnum = MealTimingEnum


class TimeSlotEnum(str, enum.Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"
    night = "night"


class AdherenceResponseEnum(str, enum.Enum):
    TAKEN = "TAKEN"
    MISSED = "MISSED"
    SIDE_EFFECT = "SIDE_EFFECT"
    NO_ANSWER = "NO_ANSWER"
    STOCK_OUT = "STOCK_OUT"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"

    # Backwards-compat aliases (old lowercase names)
    @classmethod
    def _missing_(cls, value: object):
        """Allow legacy lowercase values to resolve to their uppercase equivalents."""
        _legacy_map = {
            "taken": cls.TAKEN,
            "not_taken": cls.MISSED,
            "missed": cls.MISSED,
            "side_effect": cls.SIDE_EFFECT,
            "no_answer": cls.NO_ANSWER,
            "stock_out": cls.STOCK_OUT,
            "callback_requested": cls.CALLBACK_REQUESTED,
            "rescheduled": cls.CALLBACK_REQUESTED,
        }
        if isinstance(value, str):
            return _legacy_map.get(value.lower())
        return None


class AlertTypeEnum(str, enum.Enum):
    missed_dose = "missed_dose"
    no_answer = "no_answer"
    side_effect = "side_effect"
    low_adherence = "low_adherence"
    stock_out = "stock_out"
    refill_due = "refill_due"


class SeverityEnum(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class ChannelEnum(str, enum.Enum):
    whatsapp = "whatsapp"
    sms = "sms"
    dashboard = "dashboard"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    language: Mapped[LanguageEnum] = mapped_column(
        Enum(LanguageEnum, name="language_enum"),
        nullable=False,
        default=LanguageEnum.hindi,
    )
    family_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    family_whatsapp: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pharmacy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacies.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    pharmacy: Mapped["Pharmacy | None"] = relationship(
        "Pharmacy", back_populates="patients"
    )
    medications: Mapped[list["Medication"]] = relationship(
        "Medication", back_populates="patient", cascade="all, delete-orphan"
    )
    adherence_logs: Mapped[list["AdherenceLog"]] = relationship(
        "AdherenceLog", back_populates="patient", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="patient", cascade="all, delete-orphan"
    )
    call_schedules: Mapped[list["CallSchedule"]] = relationship(
        "CallSchedule", back_populates="patient", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_patients_phone", "phone"),
    )


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[dict] = mapped_column(JSON, nullable=False)
    meal_timing: Mapped[MealTimingEnum] = mapped_column(
        Enum(MealTimingEnum, name="meal_relation_enum"), nullable=False
    )
    prescription_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pills_dispensed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prescription_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="medications")
    adherence_logs: Mapped[list["AdherenceLog"]] = relationship(
        "AdherenceLog", back_populates="medication", cascade="all, delete-orphan"
    )
    call_schedules: Mapped[list["CallSchedule"]] = relationship(
        "CallSchedule", back_populates="medication", cascade="all, delete-orphan"
    )


class AdherenceLog(Base):
    __tablename__ = "adherence_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medications.id"), nullable=False
    )
    scheduled_time_slot: Mapped[TimeSlotEnum | None] = mapped_column(
        Enum(TimeSlotEnum, name="time_slot_enum"), nullable=True
    )
    call_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    outcome: Mapped[AdherenceResponseEnum] = mapped_column(
        Enum(AdherenceResponseEnum, name="adherence_response_enum"), nullable=False
    )
    side_effect_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    call_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bolna_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient", back_populates="adherence_logs"
    )
    medication: Mapped["Medication"] = relationship(
        "Medication", back_populates="adherence_logs"
    )

    # Indexes
    __table_args__ = (
        Index("ix_adherence_logs_patient_created", "patient_id", "created_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    alert_type: Mapped[AlertTypeEnum] = mapped_column(
        Enum(AlertTypeEnum, name="alert_type_enum"), nullable=False
    )
    severity: Mapped[SeverityEnum] = mapped_column(
        Enum(SeverityEnum, name="severity_enum"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_to: Mapped[str | None] = mapped_column(String(20), nullable=True)
    channel: Mapped[ChannelEnum] = mapped_column(
        Enum(ChannelEnum, name="channel_enum"), default=ChannelEnum.whatsapp
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="alerts")


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    patients: Mapped[list["Patient"]] = relationship(
        "Patient", back_populates="pharmacy"
    )


class CallSchedule(Base):
    __tablename__ = "call_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medications.id"), nullable=False
    )
    time_slot: Mapped[TimeSlotEnum | None] = mapped_column(
        Enum(TimeSlotEnum, name="time_slot_enum", create_type=False), nullable=True
    )
    scheduled_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_call_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_call_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient", back_populates="call_schedules"
    )
    medication: Mapped["Medication"] = relationship(
        "Medication", back_populates="call_schedules"
    )

    # Indexes
    __table_args__ = (
        Index("ix_call_schedules_next_call_at", "next_call_at"),
    )
