"""Durable database-backed scheduling for Nalam calls and follow-ups.

APScheduler is used only as an execution timer. The adherence log remains the
source of truth for pending retries, so a process restart can reconstruct jobs.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.alerts import send_daily_summary, send_no_answer_alert
from app.config import settings
from app.models import AdherenceLog, CallSchedule, Medication, Patient
from app.services.adherence_engine import AdherenceEngine
from app.services.bolna_service import BolnaService
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

_MAX_RETRY_ATTEMPTS = 2
_DEFAULT_RETRY_DELAY_SECONDS = 30 * 60
_RETRY_RECOVERY_WINDOW = timedelta(hours=2)


def _retry_delay() -> timedelta:
    raw_value = os.getenv("DEMO_RETRY_DELAY_SECONDS", "")
    if not raw_value:
        return timedelta(seconds=_DEFAULT_RETRY_DELAY_SECONDS)
    try:
        seconds = int(raw_value)
    except ValueError:
        logger.warning("Invalid DEMO_RETRY_DELAY_SECONDS; using 1800 seconds")
        return timedelta(seconds=_DEFAULT_RETRY_DELAY_SECONDS)
    if seconds < 0:
        logger.warning("Negative DEMO_RETRY_DELAY_SECONDS; using 1800 seconds")
        return timedelta(seconds=_DEFAULT_RETRY_DELAY_SECONDS)
    return timedelta(seconds=seconds)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _provider_call_succeeded(result: object) -> bool:
    if not isinstance(result, Mapping):
        return False
    if result.get("error"):
        return False
    execution_id = result.get("execution_id") or result.get("call_id")
    return isinstance(execution_id, str) and bool(execution_id.strip())


def _has_call_consent(patient: Patient) -> bool:
    consent = getattr(patient, "consent_status", None)
    return consent is not None and getattr(consent, "value", consent) == "granted"


class SchedulerService:
    """Manage daily calls, durable retry timers, and WhatsApp summaries."""

    def __init__(
        self,
        bolna_service: BolnaService,
        twilio_service: TwilioService,
        db_session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        self.bolna = bolna_service
        self.twilio = twilio_service
        self._session_factory = db_session_factory

    async def start(self) -> None:
        """Register recurring jobs and reconstruct persisted retry work."""
        self.scheduler.add_job(
            self.check_and_trigger_calls,
            "interval",
            minutes=5,
            id="check_and_trigger_calls",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            self.process_follow_ups,
            "interval",
            minutes=1,
            id="process_follow_ups",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            self.send_daily_summaries,
            "cron",
            hour=20,
            minute=0,
            timezone="Asia/Kolkata",
            id="send_daily_summaries",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        await self._recover_pending_retries()
        logger.info("SchedulerService started with durable retry recovery")

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("SchedulerService stopped")

    async def _set_retry_marker(self, log_id: uuid.UUID, scheduled: bool) -> None:
        try:
            async with self._session_factory() as db:
                log = (
                    await db.execute(select(AdherenceLog).where(AdherenceLog.id == log_id))
                ).scalar_one_or_none()
                if log:
                    log.retry_scheduled = scheduled
                    await db.commit()
        except Exception:
            logger.exception("Could not update retry marker log_id=%s", log_id)

    async def schedule_retry_call(
        self,
        patient_id: str,
        medication_id: str,
        log_id: str,
        attempt_number: int = 1,
        run_at: datetime | None = None,
    ) -> None:
        """Reserve and schedule one retry, with persisted restart recovery."""
        patient_uuid = uuid.UUID(patient_id)
        medication_uuid = uuid.UUID(medication_id)
        log_uuid = uuid.UUID(log_id)
        try:
            async with self._session_factory() as db:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                retry_count_q = select(AdherenceLog).where(
                    and_(
                        AdherenceLog.patient_id == patient_uuid,
                        AdherenceLog.medication_id == medication_uuid,
                        AdherenceLog.follow_up_needed.is_(True),
                        AdherenceLog.created_at >= today_start,
                    )
                )
                retry_logs = (await db.execute(retry_count_q)).scalars().all()
                if len(retry_logs) >= _MAX_RETRY_ATTEMPTS:
                    patient = (
                        await db.execute(select(Patient).where(Patient.id == patient_uuid))
                    ).scalar_one_or_none()
                    if patient and patient.family_whatsapp:
                        delivered = await send_no_answer_alert(self.twilio, patient)
                        logger.info(
                            "Retry cap reached patient=%s alert_delivered=%s",
                            patient_uuid,
                            delivered,
                        )
                    return

                log_obj = (
                    await db.execute(select(AdherenceLog).where(AdherenceLog.id == log_uuid))
                ).scalar_one_or_none()
                if not log_obj:
                    logger.error("Cannot schedule retry for missing log_id=%s", log_uuid)
                    return
                log_obj.retry_scheduled = True
                await db.commit()

            due_at = _as_utc(run_at) if run_at else datetime.now(timezone.utc) + _retry_delay()
            if due_at < datetime.now(timezone.utc):
                due_at = datetime.now(timezone.utc)
            job_id = f"retry-{patient_uuid}-{medication_uuid}-{log_uuid}"
            self.scheduler.add_job(
                self._execute_retry_call,
                "date",
                run_date=due_at,
                id=job_id,
                replace_existing=True,
                kwargs={
                    "patient_id": str(patient_uuid),
                    "medication_id": str(medication_uuid),
                    "log_id": str(log_uuid),
                    "attempt_number": attempt_number,
                },
            )
            logger.info(
                "Retry reserved patient=%s log_id=%s run_at=%s",
                patient_uuid,
                log_uuid,
                due_at.isoformat(),
            )
        except Exception:
            logger.exception("Retry scheduling failed patient=%s log_id=%s", patient_uuid, log_uuid)
            await self._set_retry_marker(log_uuid, scheduled=False)

    async def _execute_retry_call(
        self,
        patient_id: str,
        medication_id: str,
        log_id: str,
        attempt_number: int = 1,
    ) -> None:
        """Execute a reserved retry; the callback completes the original log."""
        log_uuid = uuid.UUID(log_id)
        try:
            async with self._session_factory() as db:
                patient = (
                    await db.execute(select(Patient).where(Patient.id == uuid.UUID(patient_id)))
                ).scalar_one_or_none()
                medication = (
                    await db.execute(select(Medication).where(Medication.id == uuid.UUID(medication_id)))
                ).scalar_one_or_none()
                if (
                    not patient
                    or not patient.is_active
                    or not _has_call_consent(patient)
                    or patient.language.value != "tamil"
                ):
                    logger.warning("Retry skipped for inactive or non-Tamil patient=%s", patient_id)
                    return
                if not medication or not medication.is_active:
                    logger.warning("Retry skipped for inactive medication=%s", medication_id)
                    return

                agent_id = settings.BOLNA_AGENT_ID_TAMIL
                if not agent_id:
                    logger.error("Retry blocked because BOLNA_AGENT_ID_TAMIL is not configured")
                    await self._set_retry_marker(log_uuid, scheduled=False)
                    return
                user_data = {
                    "patient_name": patient.name,
                    "medication_name": medication.name,
                    "dosage": medication.dosage,
                    "meal_timing": medication.meal_timing.value,
                    "language": "tamil",
                    "time_slot": "morning",
                    "patient_id": patient_id,
                    "medication_id": medication_id,
                    "is_follow_up": True,
                    "attempt_number": attempt_number,
                    "retry_log_id": log_id,
                }
                result = await self.bolna.trigger_call(
                    agent_id=agent_id,
                    recipient_phone=patient.phone,
                    user_data=user_data,
                )
                if not _provider_call_succeeded(result):
                    logger.error("Retry provider did not accept call patient=%s", patient_id)
                    await self._set_retry_marker(log_uuid, scheduled=False)
                    return
                logger.info(
                    "Retry call accepted patient=%s execution_id=%s attempt=%d",
                    patient_id,
                    result.get("execution_id") or result.get("call_id"),
                    attempt_number,
                )
        except Exception:
            logger.exception("Retry execution failed patient=%s", patient_id)
            await self._set_retry_marker(log_uuid, scheduled=False)

    async def _recover_pending_retries(self) -> None:
        """Rebuild retry timers from logs after a process restart."""
        try:
            cutoff = datetime.now(timezone.utc) - _RETRY_RECOVERY_WINDOW
            async with self._session_factory() as db:
                stmt = select(AdherenceLog).where(
                    and_(
                        AdherenceLog.follow_up_needed.is_(True),
                        AdherenceLog.follow_up_completed.is_(False),
                        AdherenceLog.created_at >= cutoff,
                    )
                )
                pending = (await db.execute(stmt)).scalars().all()
                recovery_items = [
                    (
                        str(log.patient_id),
                        str(log.medication_id),
                        str(log.id),
                        _as_utc(log.created_at) + _retry_delay(),
                    )
                    for log in pending
                ]
            for patient_id, medication_id, log_id, due_at in recovery_items:
                await self.schedule_retry_call(
                    patient_id=patient_id,
                    medication_id=medication_id,
                    log_id=log_id,
                    attempt_number=1,
                    run_at=due_at,
                )
            logger.info("Retry recovery reconstructed count=%d", len(recovery_items))
        except Exception:
            logger.exception("Retry recovery failed")

    async def check_and_trigger_calls(self) -> None:
        """Trigger due Tamil schedules and advance them only after acceptance."""
        try:
            async with self._session_factory() as db:
                now = datetime.now(timezone.utc)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                stmt = select(CallSchedule).where(
                    and_(
                        CallSchedule.is_active.is_(True),
                        CallSchedule.next_call_at <= now,
                        (CallSchedule.last_call_at.is_(None) | (CallSchedule.last_call_at < today_start)),
                    )
                )
                schedules = (await db.execute(stmt)).scalars().all()
                for schedule in schedules:
                    patient = (
                        await db.execute(select(Patient).where(Patient.id == schedule.patient_id))
                    ).scalar_one_or_none()
                    medication = (
                        await db.execute(select(Medication).where(Medication.id == schedule.medication_id))
                    ).scalar_one_or_none()
                    if (
                        not patient
                        or not patient.is_active
                        or not _has_call_consent(patient)
                        or patient.language.value != "tamil"
                    ):
                        continue
                    if not medication or not medication.is_active:
                        continue
                    agent_id = settings.BOLNA_AGENT_ID_TAMIL
                    if not agent_id:
                        logger.error("Scheduled call blocked because BOLNA_AGENT_ID_TAMIL is not configured")
                        continue
                    user_data = {
                        "patient_name": patient.name,
                        "medication_name": medication.name,
                        "dosage": medication.dosage,
                        "meal_timing": medication.meal_timing.value,
                        "language": "tamil",
                        "time_slot": schedule.time_slot.value if schedule.time_slot else "morning",
                        "patient_id": str(patient.id),
                        "medication_id": str(medication.id),
                    }
                    result = await self.bolna.trigger_call(
                        agent_id=agent_id,
                        recipient_phone=patient.phone,
                        user_data=user_data,
                    )
                    if not _provider_call_succeeded(result):
                        logger.error("Scheduled call not accepted schedule_id=%s", schedule.id)
                        continue
                    schedule.last_call_at = now
                    next_day = now + timedelta(days=1)
                    schedule.next_call_at = next_day.replace(
                        hour=schedule.scheduled_hour,
                        minute=schedule.scheduled_minute,
                        second=0,
                        microsecond=0,
                    )
                await db.commit()
        except Exception:
            logger.exception("Scheduled call check failed")

    async def process_follow_ups(self) -> None:
        """Convert due unreserved follow-ups into the same durable retry job."""
        try:
            async with self._session_factory() as db:
                pending = await AdherenceEngine(db).get_follow_up_patients()
            threshold = datetime.now(timezone.utc) - _retry_delay()
            for entry in pending:
                if entry.get("retry_scheduled"):
                    continue
                created = _as_utc(datetime.fromisoformat(str(entry["created_at"])))
                if created > threshold:
                    continue
                await self.schedule_retry_call(
                    patient_id=str(entry["patient_id"]),
                    medication_id=str(entry["medication_id"]),
                    log_id=str(entry["adherence_log_id"]),
                    attempt_number=1,
                    run_at=datetime.now(timezone.utc),
                )
        except Exception:
            logger.exception("Follow-up processing failed")

    async def send_daily_summaries(self) -> None:
        """Send summaries only for the supported Tamil patient workflow."""
        try:
            async with self._session_factory() as db:
                patients_q = select(Patient).where(
                    and_(Patient.is_active.is_(True), Patient.family_whatsapp.isnot(None))
                )
                patients = (await db.execute(patients_q)).scalars().all()
                for patient in patients:
                    if patient.language.value != "tamil" or not _has_call_consent(patient):
                        logger.warning("Daily summary skipped for non-Tamil patient=%s", patient.id)
                        continue
                    delivered = await send_daily_summary(
                        db=db,
                        twilio=self.twilio,
                        patient=patient,
                        app_base_url=settings.APP_BASE_URL,
                    )
                    logger.info("Daily summary patient=%s delivered=%s", patient.id, delivered)
        except Exception:
            logger.exception("Daily summary job failed")
