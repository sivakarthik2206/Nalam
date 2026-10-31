"""APScheduler-based service that orchestrates medication reminder calls,
follow-ups, and daily summary delivery."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    AdherenceLog,
    CallSchedule,
    Medication,
    Patient,
)
from app.services.adherence_engine import AdherenceEngine
from app.services.bolna_service import BolnaService
from app.services.twilio_service import TwilioService
from app.config import settings
from app.utils.language import get_bolna_agent_id

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Max retry attempts before escalating to family alert
_MAX_RETRY_ATTEMPTS = 2


class SchedulerService:
    """Manages recurring jobs: calls, follow-ups, daily summaries."""

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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Register jobs and start the scheduler."""
        self.scheduler.add_job(
            self.check_and_trigger_calls,
            "interval",
            minutes=5,
            id="check_and_trigger_calls",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.process_follow_ups,
            "interval",
            minutes=1,  # Reduced to 1 min as safety net
            id="process_follow_ups",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.send_daily_summaries,
            "cron",
            hour=20,
            minute=0,
            timezone="Asia/Kolkata",
            id="send_daily_summaries",
            replace_existing=True,
        )
        self.scheduler.start()

        # Server-restart recovery: schedule pending retries
        try:
            await self._recover_pending_retries()
        except Exception:
            logger.exception("Failed to recover pending retries on startup")

        logger.info("SchedulerService started — 3 jobs registered")

    async def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("SchedulerService stopped")

    # ------------------------------------------------------------------
    # Retry scheduling (Phase 4)
    # ------------------------------------------------------------------

    async def schedule_retry_call(
        self,
        patient_id: str,
        medication_id: str,
        log_id: str,
        attempt_number: int = 1,
    ) -> None:
        """
        Schedule an exact 30-minute retry call for a patient/medication.

        Caps at _MAX_RETRY_ATTEMPTS. If cap is hit, fires urgent family WhatsApp alert instead.
        Uses idempotent job id so duplicate schedules replace each other.
        """
        try:
            # Count existing retry logs for this patient+medication today
            async with self._session_factory() as db:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                retry_count_q = (
                    select(AdherenceLog)
                    .where(
                        and_(
                            AdherenceLog.patient_id == uuid.UUID(patient_id),
                            AdherenceLog.medication_id == uuid.UUID(medication_id),
                            AdherenceLog.follow_up_needed.is_(True),
                            AdherenceLog.created_at >= today_start,
                        )
                    )
                )
                retry_logs = (await db.execute(retry_count_q)).scalars().all()
                existing_retry_count = len(retry_logs)

                if existing_retry_count >= _MAX_RETRY_ATTEMPTS:
                    # Cap hit — fire urgent family alert instead
                    logger.info(
                        "Retry cap hit for patient %s med %s — firing urgent no_answer alert",
                        patient_id, medication_id,
                    )
                    patient = (
                        await db.execute(
                            select(Patient).where(Patient.id == uuid.UUID(patient_id))
                        )
                    ).scalar_one_or_none()
                    if patient and patient.family_whatsapp:
                        try:
                            from app.alerts import send_no_answer_alert
                            await send_no_answer_alert(self.twilio, patient)
                        except Exception:
                            logger.exception("Failed to send no_answer alert for patient %s", patient_id)
                    return

                # Mark log as retry_scheduled
                log_obj = (
                    await db.execute(
                        select(AdherenceLog).where(AdherenceLog.id == uuid.UUID(log_id))
                    )
                ).scalar_one_or_none()
                if log_obj:
                    log_obj.retry_scheduled = True
                    await db.commit()

            # Schedule APScheduler date job
            run_date = datetime.now(timezone.utc) + timedelta(minutes=30)
            job_id = f"retry-{patient_id}-{medication_id}-{log_id}"

            self.scheduler.add_job(
                self._execute_retry_call,
                "date",
                run_date=run_date,
                id=job_id,
                replace_existing=True,
                kwargs={
                    "patient_id": patient_id,
                    "medication_id": medication_id,
                    "log_id": log_id,
                    "attempt_number": attempt_number,
                },
            )
            logger.info(
                "Retry call scheduled for patient %s at %s (job_id=%s)",
                patient_id, run_date.isoformat(), job_id,
            )

        except Exception:
            logger.exception("schedule_retry_call failed for patient %s", patient_id)

    async def _execute_retry_call(
        self,
        patient_id: str,
        medication_id: str,
        log_id: str,
        attempt_number: int = 1,
    ) -> None:
        """Job function — executes the actual retry Bolna call."""
        try:
            async with self._session_factory() as db:
                patient = (
                    await db.execute(
                        select(Patient).where(Patient.id == uuid.UUID(patient_id))
                    )
                ).scalar_one_or_none()
                medication = (
                    await db.execute(
                        select(Medication).where(Medication.id == uuid.UUID(medication_id))
                    )
                ).scalar_one_or_none()

                if not patient or not patient.is_active:
                    return
                if not medication or not medication.is_active:
                    return

                agent_id = get_bolna_agent_id(patient.language.value)
                if not agent_id:
                    logger.warning("No Bolna agent for patient %s language", patient_id)
                    return

                user_data = {
                    "patient_name": patient.name,
                    "medication_name": medication.name,
                    "dosage": medication.dosage,
                    "meal_timing": medication.meal_timing.value,
                    "language": patient.language.value,
                    "time_slot": "morning",
                    "patient_id": patient_id,
                    "medication_id": medication_id,
                    "is_follow_up": True,
                    "attempt_number": attempt_number,
                }

                await self.bolna.trigger_call(
                    agent_id=agent_id,
                    recipient_phone=patient.phone,
                    user_data=user_data,
                )
                logger.info("Retry call executed for patient %s (attempt %d)", patient_id, attempt_number)
        except Exception:
            logger.exception("_execute_retry_call failed for patient %s", patient_id)

    async def _recover_pending_retries(self) -> None:
        """
        On server restart, find unretried logs from last 2 hours and re-schedule them.
        Idempotency: only reschedule logs where retry_scheduled=False.
        """
        try:
            async with self._session_factory() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
                stmt = (
                    select(AdherenceLog)
                    .where(
                        and_(
                            AdherenceLog.follow_up_needed.is_(True),
                            AdherenceLog.follow_up_completed.is_(False),
                            AdherenceLog.retry_scheduled.is_(False),
                            AdherenceLog.created_at >= cutoff,
                        )
                    )
                )
                pending_logs = (await db.execute(stmt)).scalars().all()

                for log in pending_logs:
                    await self.schedule_retry_call(
                        patient_id=str(log.patient_id),
                        medication_id=str(log.medication_id),
                        log_id=str(log.id),
                        attempt_number=1,
                    )
                logger.info("Recovery: scheduled %d pending retries", len(pending_logs))
        except Exception:
            logger.exception("_recover_pending_retries failed")

    # ------------------------------------------------------------------
    # Job 1 — Check & trigger due calls (every 5 min)
    # ------------------------------------------------------------------

    async def check_and_trigger_calls(self) -> None:
        """Query CallSchedule for due calls and trigger them via Bolna."""
        logger.info("check_and_trigger_calls — starting")
        try:
            async with self._session_factory() as db:
                now = datetime.now(timezone.utc)
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

                stmt = select(CallSchedule).where(
                    and_(
                        CallSchedule.is_active.is_(True),
                        CallSchedule.next_call_at <= now,
                        # Only call once per day
                        (
                            (CallSchedule.last_call_at.is_(None))
                            | (CallSchedule.last_call_at < today_start)
                        ),
                    )
                )
                schedules = (await db.execute(stmt)).scalars().all()

                if not schedules:
                    logger.debug("No due call schedules found")
                    return

                logger.info("Found %d due call schedules", len(schedules))

                for sched in schedules:
                    try:
                        # Load patient + medication
                        patient = (
                            await db.execute(
                                select(Patient).where(Patient.id == sched.patient_id)
                            )
                        ).scalar_one_or_none()
                        medication = (
                            await db.execute(
                                select(Medication).where(Medication.id == sched.medication_id)
                            )
                        ).scalar_one_or_none()

                        if not patient or not patient.is_active:
                            continue
                        if not medication or not medication.is_active:
                            continue

                        agent_id = get_bolna_agent_id(patient.language.value)
                        if not agent_id:
                            logger.warning(
                                "No Bolna agent for language %s (patient %s)",
                                patient.language.value,
                                patient.id,
                            )
                            continue

                        user_data = {
                            "patient_name": patient.name,
                            "medication_name": medication.name,
                            "dosage": medication.dosage,
                            "meal_timing": medication.meal_timing.value,
                            "language": patient.language.value,
                            "time_slot": sched.time_slot.value if sched.time_slot else "morning",
                            "patient_id": str(patient.id),
                            "medication_id": str(medication.id),
                        }

                        result = await self.bolna.trigger_call(
                            agent_id=agent_id,
                            recipient_phone=patient.phone,
                            user_data=user_data,
                        )
                        logger.info(
                            "Call triggered for patient %s → %s",
                            patient.name,
                            result.get("call_id", "no_id"),
                        )

                        # Advance schedule
                        sched.last_call_at = now
                        # Next call tomorrow at the same HH:MM
                        tomorrow = now + timedelta(days=1)
                        sched.next_call_at = tomorrow.replace(
                            hour=sched.scheduled_hour,
                            minute=sched.scheduled_minute,
                            second=0,
                            microsecond=0,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to trigger call for schedule %s", sched.id
                        )

                await db.commit()
        except Exception:
            logger.exception("check_and_trigger_calls — job failed")

    # ------------------------------------------------------------------
    # Job 2 — Process follow-ups (every 1 min — safety net)
    # ------------------------------------------------------------------

    async def process_follow_ups(self) -> None:
        """Safety-net: re-call patients who said not_taken / callback_requested ≥ 30 min ago
        and whose retry_scheduled is still False (i.e., exact APScheduler job was missed)."""
        logger.debug("process_follow_ups — starting")
        try:
            async with self._session_factory() as db:
                engine = AdherenceEngine(db)
                pending = await engine.get_follow_up_patients()

                if not pending:
                    return

                now = datetime.now(timezone.utc)
                thirty_min_ago = now - timedelta(minutes=30)

                for entry in pending:
                    try:
                        # Idempotency: skip if retry already scheduled
                        if entry.get("retry_scheduled"):
                            continue

                        created = datetime.fromisoformat(entry["created_at"])
                        if created > thirty_min_ago:
                            # Not yet 30 minutes old — skip
                            continue

                        patient_id = uuid.UUID(entry["patient_id"])
                        medication_id = uuid.UUID(entry["medication_id"])
                        log_id = entry["adherence_log_id"]

                        patient = (
                            await db.execute(
                                select(Patient).where(Patient.id == patient_id)
                            )
                        ).scalar_one_or_none()
                        medication = (
                            await db.execute(
                                select(Medication).where(Medication.id == medication_id)
                            )
                        ).scalar_one_or_none()

                        if not patient or not patient.is_active:
                            continue
                        if not medication:
                            continue

                        agent_id = get_bolna_agent_id(patient.language.value)
                        if not agent_id:
                            continue

                        user_data = {
                            "patient_name": patient.name,
                            "medication_name": medication.name,
                            "dosage": medication.dosage,
                            "meal_timing": medication.meal_timing.value,
                            "language": patient.language.value,
                            "time_slot": entry.get("time_slot", "morning"),
                            "patient_id": str(patient.id),
                            "medication_id": str(medication.id),
                            "is_follow_up": True,
                        }

                        await self.bolna.trigger_call(
                            agent_id=agent_id,
                            recipient_phone=patient.phone,
                            user_data=user_data,
                        )
                        logger.info("Follow-up (safety net) triggered for patient %s", patient.name)

                        # Mark retry_scheduled and follow_up_completed
                        log_obj = (
                            await db.execute(
                                select(AdherenceLog).where(AdherenceLog.id == uuid.UUID(log_id))
                            )
                        ).scalar_one_or_none()
                        if log_obj:
                            log_obj.follow_up_completed = True
                            log_obj.retry_scheduled = True

                    except Exception:
                        logger.exception(
                            "Follow-up processing failed for entry %s", entry
                        )

                await db.commit()
        except Exception:
            logger.exception("process_follow_ups — job failed")

    # ------------------------------------------------------------------
    # Job 3 — Send daily summaries (8 PM IST)
    # ------------------------------------------------------------------

    async def send_daily_summaries(self) -> None:
        """Send a WhatsApp daily report to each active patient's family contact."""
        logger.info("send_daily_summaries — starting")
        try:
            async with self._session_factory() as db:
                engine = AdherenceEngine(db)

                patients_q = select(Patient).where(
                    and_(
                        Patient.is_active.is_(True),
                        Patient.family_whatsapp.isnot(None),
                    )
                )
                patients = (await db.execute(patients_q)).scalars().all()
                logger.info("Sending daily summaries for %d patients", len(patients))

                for patient in patients:
                    try:
                        summary = await engine.get_daily_summary(patient.id)
                        if summary.get("error"):
                            continue

                        # Add dashboard link
                        if settings.APP_BASE_URL:
                            summary["dashboard_link"] = (
                                f"{settings.APP_BASE_URL}/family/{patient.id}"
                            )

                        language = patient.language.value
                        message = self.twilio.format_daily_summary(summary, language=language)

                        await self.twilio.send_whatsapp(
                            to=patient.family_whatsapp,
                            body=message,
                        )
                        logger.info(
                            "Daily summary sent to %s for patient %s",
                            patient.family_whatsapp,
                            patient.name,
                        )
                    except Exception:
                        logger.exception(
                            "Daily summary failed for patient %s", patient.name
                        )
        except Exception:
            logger.exception("send_daily_summaries — job failed")
