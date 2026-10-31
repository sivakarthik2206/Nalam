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
    UniqueConstraint,
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


class ConsentStatusEnum(str, enum.Enum):
    pending = "pending"
    granted = "granted"
    withdrawn = "withdrawn"


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


class DoseStatusEnum(str, enum.Enum):
    scheduled = "scheduled"
    taken = "taken"
    missed = "missed"
    no_answer = "no_answer"
    side_effect = "side_effect"
    stock_out = "stock_out"
    callback_requested = "callback_requested"
    unknown = "unknown"
    cancelled = "cancelled"


class CallStatusEnum(str, enum.Enum):
    scheduled = "scheduled"
    initiated = "initiated"
    ringing = "ringing"
    answered = "answered"
    in_progress = "in_progress"
    completed = "completed"
    no_answer = "no_answer"
    busy = "busy"
    failed = "failed"
    cancelled = "cancelled"
    disconnected = "disconnected"
    function_call_failed = "function_call_failed"


class RetryStatusEnum(str, enum.Enum):
    pending = "pending"
    claimed = "claimed"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class DeliveryStatusEnum(str, enum.Enum):
    pending = "pending"
    sending = "sending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    retry_scheduled = "retry_scheduled"
    resolved = "resolved"


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
        default=LanguageEnum.tamil,
    )
    timezone_name: Mapped[str] = mapped_column(
        "timezone", String(64), nullable=False, default="Asia/Kolkata"
    )
    consent_status: Mapped[ConsentStatusEnum] = mapped_column(
        Enum(ConsentStatusEnum, name="consent_status_enum"),
        nullable=False,
        default=ConsentStatusEnum.pending,
    )
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    call_window_start_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=480
    )
    call_window_end_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1200
    )
    demo_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    scheduled_doses: Mapped[list["ScheduledDose"]] = relationship(
        "ScheduledDose", back_populates="patient", cascade="all, delete-orphan"
    )
    call_records: Mapped[list["CallRecord"]] = relationship(
        "CallRecord", back_populates="patient", cascade="all, delete-orphan"
    )
    retry_jobs: Mapped[list["RetryJob"]] = relationship(
        "RetryJob", back_populates="patient", cascade="all, delete-orphan"
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
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    refill_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    units_per_dose: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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
    scheduled_doses: Mapped[list["ScheduledDose"]] = relationship(
        "ScheduledDose", back_populates="medication", cascade="all, delete-orphan"
    )


class ScheduledDose(Base):
    """The durable denominator unit for adherence calculations."""

    __tablename__ = "scheduled_doses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[DoseStatusEnum] = mapped_column(
        Enum(DoseStatusEnum, name="dose_status_enum"),
        nullable=False,
        default=DoseStatusEnum.scheduled,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    taken_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduler")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    patient: Mapped["Patient"] = relationship("Patient", back_populates="scheduled_doses")
    medication: Mapped["Medication"] = relationship(
        "Medication", back_populates="scheduled_doses"
    )
    adherence_logs: Mapped[list["AdherenceLog"]] = relationship(
        "AdherenceLog", back_populates="scheduled_dose"
    )

    __table_args__ = (
        UniqueConstraint(
            "medication_id", "scheduled_for", name="uq_scheduled_dose_medication_time"
        ),
        Index("ix_scheduled_doses_patient_time", "patient_id", "scheduled_for"),
    )


class CallRecord(Base):
    """Durable provider call lifecycle record."""

    __tablename__ = "call_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_dose_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_doses.id", ondelete="SET NULL"), nullable=True
    )
    provider_call_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[CallStatusEnum] = mapped_column(
        Enum(CallStatusEnum, name="call_status_enum"),
        nullable=False,
        default=CallStatusEnum.scheduled,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outcome: Mapped[AdherenceResponseEnum | None] = mapped_column(
        Enum(AdherenceResponseEnum, name="adherence_response_enum", create_type=False),
        nullable=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    patient: Mapped["Patient"] = relationship("Patient", back_populates="call_records")
    scheduled_dose: Mapped["ScheduledDose | None"] = relationship("ScheduledDose")
    adherence_logs: Mapped[list["AdherenceLog"]] = relationship(
        "AdherenceLog", back_populates="call_record"
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
    scheduled_dose_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_doses.id", ondelete="SET NULL"), nullable=True
    )
    call_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_records.id", ondelete="SET NULL"), nullable=True
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
    taken_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    side_effect_severity: Mapped[SeverityEnum | None] = mapped_column(
        Enum(SeverityEnum, name="severity_enum", create_type=False), nullable=True
    )
    stock_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="voice")
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
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
    scheduled_dose: Mapped["ScheduledDose | None"] = relationship(
        "ScheduledDose", back_populates="adherence_logs"
    )
    call_record: Mapped["CallRecord | None"] = relationship(
        "CallRecord", back_populates="adherence_logs"
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
    scheduled_dose_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_doses.id", ondelete="SET NULL"), nullable=True
    )
    call_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_records.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    delivery_status: Mapped[DeliveryStatusEnum] = mapped_column(
        Enum(DeliveryStatusEnum, name="delivery_status_enum"),
        nullable=False,
        default=DeliveryStatusEnum.pending,
    )
    delivery_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delivery_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        UniqueConstraint(
            "medication_id",
            "scheduled_hour",
            "scheduled_minute",
            "time_slot",
            name="uq_call_schedule_medication_slot",
        ),
    )


class RetryJob(Base):
    """Durable retry work item; APScheduler is only the execution trigger."""

    __tablename__ = "retry_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_dose_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scheduled_doses.id", ondelete="SET NULL"), nullable=True
    )
    related_call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_records.id", ondelete="SET NULL"), nullable=True
    )
    source_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("adherence_logs.id", ondelete="SET NULL"), nullable=True
    )
    retry_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[RetryStatusEnum] = mapped_column(
        Enum(RetryStatusEnum, name="retry_status_enum"),
        nullable=False,
        default=RetryStatusEnum.pending,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    patient: Mapped["Patient"] = relationship("Patient", back_populates="retry_jobs")
