"""Durable medication-adherence domain services.

The engine validates the patient/medication relationship, makes outcome writes
idempotent, updates durable scheduled-dose records, and calculates scores from
actual dose events rather than call counts.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Alert,
    DoseStatusEnum,
    Medication,
    Patient,
    ScheduledDose,
    SeverityEnum,
    TimeSlotEnum,
)

logger = logging.getLogger(__name__)


class AdherenceValidationError(ValueError):
    """Raised when an outcome cannot be safely associated with a dose."""


class RefillPrediction(TypedDict):
    patient_id: str
    medication_id: str
    medication_name: str
    pills_dispensed: int | None
    pills_consumed: int
    pills_remaining: int
    daily_consumption: int
    effective_daily: float
    days_remaining: float
    refill_urgent: bool


@dataclass(frozen=True)
class AdherenceMetrics:
    score: float | None
    expected: int
    taken: int


_OUTCOME_ALIASES: dict[str, str] = {
    "taken": "TAKEN",
    "not_taken": "MISSED",
    "missed": "MISSED",
    "side_effect": "SIDE_EFFECT",
    "no_answer": "NO_ANSWER",
    "stock_out": "STOCK_OUT",
    "callback_requested": "CALLBACK_REQUESTED",
    "rescheduled": "CALLBACK_REQUESTED",
}

_OUTCOME_TO_DOSE_STATUS: dict[AdherenceResponseEnum, DoseStatusEnum] = {
    AdherenceResponseEnum.TAKEN: DoseStatusEnum.taken,
    AdherenceResponseEnum.MISSED: DoseStatusEnum.missed,
    AdherenceResponseEnum.SIDE_EFFECT: DoseStatusEnum.side_effect,
    AdherenceResponseEnum.NO_ANSWER: DoseStatusEnum.no_answer,
    AdherenceResponseEnum.STOCK_OUT: DoseStatusEnum.stock_out,
    AdherenceResponseEnum.CALLBACK_REQUESTED: DoseStatusEnum.callback_requested,
}


def _utc(value: datetime) -> datetime:
    """Return an aware UTC timestamp without relying on machine timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _patient_zone(patient: Patient) -> ZoneInfo:
    try:
        return ZoneInfo(patient.timezone_name)
    except (ZoneInfoNotFoundError, AttributeError) as exc:
        raise AdherenceValidationError("patient has an invalid IANA timezone") from exc


def _normalise_outcome(response: str) -> AdherenceResponseEnum:
    normalized = _OUTCOME_ALIASES.get(response.strip().lower(), response.strip().upper())
    try:
        return AdherenceResponseEnum(normalized)
    except ValueError as exc:
        raise AdherenceValidationError("unsupported adherence outcome") from exc


class AdherenceEngine:
    """All adherence-related business logic."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    async def _get_patient_and_medication(
        self, patient_id: uuid.UUID, medication_id: uuid.UUID
    ) -> tuple[Patient, Medication]:
        patient = (
            await self.db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is None:
            raise AdherenceValidationError("patient not found")

        medication = (
            await self.db.execute(
                select(Medication).where(
                    Medication.id == medication_id,
                    Medication.patient_id == patient_id,
                )
            )
        ).scalar_one_or_none()
        if medication is None:
            raise AdherenceValidationError("medication does not belong to patient")
        return patient, medication

    async def log_response(
        self,
        patient_id: uuid.UUID,
        medication_id: uuid.UUID,
        time_slot: str,
        response: str,
        side_effect_details: str | None = None,
        bolna_call_id: str | None = None,
        call_duration: int | None = None,
        notes: str | None = None,
        *,
        idempotency_key: str | None = None,
        scheduled_dose_id: uuid.UUID | None = None,
        taken_late: bool | None = None,
        side_effect_severity: SeverityEnum | None = None,
        stock_out: bool | None = None,
        source: str = "voice",
        event_timestamp: datetime | None = None,
    ) -> AdherenceLog:
        """Persist one outcome and return the existing row for a replayed event."""
        patient, medication = await self._get_patient_and_medication(
            patient_id, medication_id
        )
        response_enum = _normalise_outcome(response)
        if not source.strip() or len(source) > 32:
            raise AdherenceValidationError("source must be between 1 and 32 characters")
        if call_duration is not None and (call_duration < 0 or call_duration > 86400):
            raise AdherenceValidationError("call duration is outside the supported range")

        event_at = _utc(event_timestamp or datetime.now(timezone.utc))
        stable_key = idempotency_key
        if stable_key is None and bolna_call_id:
            stable_key = f"bolna:{bolna_call_id}:{patient_id}:{medication_id}"

        if stable_key:
            existing = (
                await self.db.execute(
                    select(AdherenceLog).where(AdherenceLog.idempotency_key == stable_key)
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing

        slot_enum: TimeSlotEnum | None = None
        if time_slot:
            try:
                slot_enum = TimeSlotEnum(time_slot.strip().lower())
            except ValueError as exc:
                raise AdherenceValidationError("unsupported medication time slot") from exc

        scheduled_dose: ScheduledDose | None = None
        if scheduled_dose_id is not None:
            scheduled_dose = (
                await self.db.execute(
                    select(ScheduledDose).where(
                        ScheduledDose.id == scheduled_dose_id,
                        ScheduledDose.patient_id == patient_id,
                        ScheduledDose.medication_id == medication_id,
                    )
                )
            ).scalar_one_or_none()
            if scheduled_dose is None:
                raise AdherenceValidationError("scheduled dose does not belong to medication")

        late = bool(taken_late)
        if response_enum == AdherenceResponseEnum.TAKEN and scheduled_dose is not None:
            late = late or event_at > _utc(scheduled_dose.scheduled_for)

        log = AdherenceLog(
            patient_id=patient.id,
            medication_id=medication.id,
            scheduled_dose_id=scheduled_dose.id if scheduled_dose else None,
            scheduled_time_slot=slot_enum,
            call_time=event_at,
            outcome=response_enum,
            side_effect_details=side_effect_details,
            notes=notes or side_effect_details,
            call_duration_seconds=call_duration,
            bolna_call_id=bolna_call_id,
            follow_up_needed=response_enum
            in (
                AdherenceResponseEnum.MISSED,
                AdherenceResponseEnum.NO_ANSWER,
                AdherenceResponseEnum.CALLBACK_REQUESTED,
            ),
            taken_late=late,
            side_effect_severity=side_effect_severity,
            stock_out=(stock_out is True) or response_enum == AdherenceResponseEnum.STOCK_OUT,
            source=source.strip(),
            idempotency_key=stable_key,
        )

        try:
            # The savepoint makes the unique idempotency constraint safe under
            # concurrent webhook delivery without invalidating the caller's
            # outer transaction when the losing request observes a duplicate.
            async with self.db.begin_nested():
                self.db.add(log)
                await self.db.flush()
        except IntegrityError:
            if stable_key is None:
                raise
            existing = (
                await self.db.execute(
                    select(AdherenceLog).where(AdherenceLog.idempotency_key == stable_key)
                )
            ).scalar_one_or_none()
            if existing is None:
                raise
            return existing

        if scheduled_dose is not None:
            scheduled_dose.attempt_count += 1
            # A confirmed dose must not be downgraded by a later technical event.
            if (
                scheduled_dose.status != DoseStatusEnum.taken
                or response_enum == AdherenceResponseEnum.TAKEN
            ):
                scheduled_dose.status = _OUTCOME_TO_DOSE_STATUS[response_enum]
            scheduled_dose.taken_late = scheduled_dose.taken_late or late
            if response_enum == AdherenceResponseEnum.TAKEN:
                scheduled_dose.confirmed_at = event_at

        await self.db.flush()
        await self.db.refresh(log)
        logger.info(
            "adherence_outcome_persisted event=%s patient=%s medication=%s outcome=%s",
            stable_key or str(log.id),
            patient.id,
            medication.id,
            response_enum.value,
        )
        return log

    async def compute_adherence_metrics(
        self,
        patient_id: uuid.UUID,
        days: int = 7,
        *,
        as_of: datetime | None = None,
    ) -> AdherenceMetrics:
        """Calculate a rolling score from scheduled doses or the legacy schedule."""
        if days < 1:
            raise AdherenceValidationError("days must be positive")

        patient = (
            await self.db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if patient is None:
            raise AdherenceValidationError("patient not found")

        end = _utc(as_of or datetime.now(timezone.utc))
        since = end - timedelta(days=days)
        dose_rows = (
            await self.db.execute(
                select(ScheduledDose).where(
                    ScheduledDose.patient_id == patient_id,
                    ScheduledDose.scheduled_for >= since,
                    ScheduledDose.scheduled_for < end,
                    ScheduledDose.status != DoseStatusEnum.cancelled,
                )
            )
        ).scalars().all()

        if dose_rows:
            expected = len(dose_rows)
            dose_ids = {dose.id for dose in dose_rows}
            taken_rows = (
                await self.db.execute(
                    select(AdherenceLog.scheduled_dose_id).where(
                        AdherenceLog.patient_id == patient_id,
                        AdherenceLog.scheduled_dose_id.in_(dose_ids),
                        AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                    )
                )
            ).scalars().all()
            taken = len({dose_id for dose_id in taken_rows if dose_id is not None})
            if taken == 0:
                taken = sum(1 for dose in dose_rows if dose.status == DoseStatusEnum.taken)
        else:
            medications = (
                await self.db.execute(
                    select(Medication).where(
                        Medication.patient_id == patient_id,
                        Medication.is_active.is_(True),
                    )
                )
            ).scalars().all()
            expected = self._legacy_expected_doses(medications, since, end, _patient_zone(patient))

            taken_rows = (
                await self.db.execute(
                    select(AdherenceLog).where(
                        AdherenceLog.patient_id == patient_id,
                        AdherenceLog.created_at >= since,
                        AdherenceLog.created_at < end,
                        AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                    )
                )
            ).scalars().all()
            # Legacy rows predate ScheduledDose. Collapse replayed confirmations
            # by medication/date/slot so duplicate callbacks cannot inflate scores.
            unique_events: set[tuple[uuid.UUID, date, str | None]] = set()
            zone = _patient_zone(patient)
            for log in taken_rows:
                local_date = _utc(log.call_time).astimezone(zone).date()
                slot = log.scheduled_time_slot.value if log.scheduled_time_slot else None
                unique_events.add((log.medication_id, local_date, slot))
            taken = len(unique_events)

        score = None if expected == 0 else round(min(taken / expected * 100, 100.0), 1)
        return AdherenceMetrics(score=score, expected=expected, taken=taken)

    @staticmethod
    def _legacy_expected_doses(
        medications: list[Medication],
        since: datetime,
        end: datetime,
        zone: ZoneInfo,
    ) -> int:
        start_date = since.astimezone(zone).date()
        end_date = end.astimezone(zone).date()
        expected = 0
        for medication in medications:
            frequency = medication.frequency if isinstance(medication.frequency, list) else []
            first_date = start_date
            last_date = end_date
            if medication.prescription_start_date:
                first_date = max(first_date, medication.prescription_start_date)
            if medication.prescription_duration_days:
                prescription_end = (
                    medication.prescription_start_date or first_date
                ) + timedelta(days=medication.prescription_duration_days)
                last_date = min(last_date, prescription_end)
            eligible_days = max((last_date - first_date).days, 0)
            expected += len(frequency) * eligible_days
        return expected

    async def compute_adherence_score(
        self, patient_id: uuid.UUID, days: int = 7
    ) -> float | None:
        """Compatibility wrapper returning ``None`` when no denominator exists."""
        return (await self.compute_adherence_metrics(patient_id, days)).score

    async def check_escalation_rules(
        self, patient_id: uuid.UUID, latest_log: AdherenceLog
    ) -> list[Alert]:
        """Delegate alert policy to the existing central escalation module."""
        from app.alerts import evaluate_escalations

        return await evaluate_escalations(self.db, patient_id, latest_log)

    async def get_refill_predictions(
        self, patient_id: uuid.UUID | None = None
    ) -> list[RefillPrediction]:
        """Estimate remaining stock from configured quantity and prescribed use."""
        medication_query = select(Medication).where(Medication.is_active.is_(True))
        if patient_id is not None:
            medication_query = medication_query.where(Medication.patient_id == patient_id)
        medications = (await self.db.execute(medication_query)).scalars().all()

        predictions: list[RefillPrediction] = []
        for medication in medications:
            starting_quantity = (
                medication.stock_quantity
                if medication.stock_quantity is not None
                else medication.pills_dispensed
            )
            if starting_quantity is None or starting_quantity < 0:
                continue

            consumed_query = select(AdherenceLog).where(
                and_(
                    AdherenceLog.medication_id == medication.id,
                    AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                )
            )
            if medication.prescription_start_date:
                consumed_query = consumed_query.where(
                    AdherenceLog.call_time
                    >= datetime.combine(
                        medication.prescription_start_date,
                        datetime.min.time(),
                        tzinfo=timezone.utc,
                    )
                )
            consumed_logs = (await self.db.execute(consumed_query)).scalars().all()
            consumed_keys: set[object] = set()
            for log in consumed_logs:
                if log.scheduled_dose_id is not None:
                    consumed_keys.add(("dose", log.scheduled_dose_id))
                elif log.scheduled_time_slot is not None:
                    consumed_keys.add(
                        (
                            "slot",
                            _utc(log.call_time).date(),
                            log.scheduled_time_slot.value,
                        )
                    )
                else:
                    # Legacy records without a slot have no safe logical-dose
                    # key; event idempotency still prevents provider replays.
                    consumed_keys.add(("legacy", log.id))
            consumed = len(consumed_keys)
            units_per_day = len(
                medication.frequency if isinstance(medication.frequency, list) else []
            ) * max(medication.units_per_dose, 1)
            remaining = max(starting_quantity - consumed * max(medication.units_per_dose, 1), 0)
            days_remaining = round(remaining / units_per_day, 1) if units_per_day else 0.0
            predictions.append(
                {
                    "patient_id": str(medication.patient_id),
                    "medication_id": str(medication.id),
                    "medication_name": medication.name,
                    "pills_dispensed": starting_quantity,
                    "pills_consumed": consumed * max(medication.units_per_dose, 1),
                    "pills_remaining": remaining,
                    "daily_consumption": units_per_day,
                    "effective_daily": float(units_per_day),
                    "days_remaining": days_remaining,
                    "refill_urgent": days_remaining <= medication.refill_threshold,
                }
            )
        return predictions

    async def get_daily_summary(self, patient_id: uuid.UUID) -> dict[str, object]:
        """Return today's dose state using the patient's configured timezone."""
        patient = (
            await self.db.execute(
                select(Patient)
                .options(selectinload(Patient.medications))
                .where(Patient.id == patient_id)
            )
        ).scalar_one_or_none()
        if patient is None:
            return {"error": "patient_not_found"}

        zone = _patient_zone(patient)
        local_today = datetime.now(timezone.utc).astimezone(zone).date()
        day_start = datetime.combine(local_today, datetime.min.time(), tzinfo=zone).astimezone(
            timezone.utc
        )
        day_end = day_start + timedelta(days=1)
        logs = (
            await self.db.execute(
                select(AdherenceLog).where(
                    AdherenceLog.patient_id == patient_id,
                    AdherenceLog.call_time >= day_start,
                    AdherenceLog.call_time < day_end,
                )
            )
        ).scalars().all()

        lookup: dict[tuple[uuid.UUID, str | None], str] = {}
        for log in logs:
            slot = log.scheduled_time_slot.value if log.scheduled_time_slot else None
            lookup[(log.medication_id, slot)] = log.outcome.value

        medications_status: list[dict[str, str]] = []
        slot_statuses: dict[str, str] = {}
        total = taken = missed = pending = 0
        for medication in patient.medications:
            if not medication.is_active:
                continue
            frequency = medication.frequency if isinstance(medication.frequency, list) else []
            for slot in frequency:
                total += 1
                raw = lookup.get((medication.id, slot), "pending")
                if raw == AdherenceResponseEnum.TAKEN.value:
                    display = "taken"
                    taken += 1
                elif raw in {
                    AdherenceResponseEnum.MISSED.value,
                    AdherenceResponseEnum.NO_ANSWER.value,
                    AdherenceResponseEnum.STOCK_OUT.value,
                }:
                    display = "not_taken"
                    missed += 1
                else:
                    display = "pending"
                    pending += 1
                medications_status.append(
                    {"medication_name": medication.name, "time_slot": slot, "status": display}
                )
                slot_statuses.setdefault(slot, display)

        metrics = await self.compute_adherence_metrics(patient_id, days=7)
        return {
            "patient_id": str(patient_id),
            "patient_name": patient.name,
            "language": patient.language.value,
            "family_whatsapp": patient.family_whatsapp,
            "family_contact_phone": patient.family_whatsapp,
            "medications": medications_status,
            "slot_statuses": slot_statuses,
            "total_doses_today": total,
            "doses_taken": taken,
            "doses_missed": missed,
            "doses_pending": pending,
            "today_score": round(taken / total * 100, 1) if total else None,
            "adherence_score_7d": metrics.score,
        }

    async def get_follow_up_patients(self) -> list[dict[str, object]]:
        """Return unresolved follow-up logs for the scheduler safety net."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        logs = (
            await self.db.execute(
                select(AdherenceLog)
                .where(
                    AdherenceLog.follow_up_needed.is_(True),
                    AdherenceLog.follow_up_completed.is_(False),
                    AdherenceLog.retry_scheduled.is_(False),
                    AdherenceLog.created_at >= cutoff,
                )
                .order_by(AdherenceLog.created_at.asc())
            )
        ).scalars().all()
        return [
            {
                "adherence_log_id": str(log.id),
                "patient_id": str(log.patient_id),
                "medication_id": str(log.medication_id),
                "time_slot": log.scheduled_time_slot.value
                if log.scheduled_time_slot
                else None,
                "outcome": log.outcome.value,
                "response": log.outcome.value,
                "retry_scheduled": log.retry_scheduled,
                "created_at": _utc(log.created_at).isoformat(),
            }
            for log in logs
        ]
