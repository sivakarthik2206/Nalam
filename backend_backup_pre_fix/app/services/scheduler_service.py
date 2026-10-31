"""APScheduler-based service that orchestrates medication reminder calls,
follow-ups, and daily summary delivery."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
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
            minutes=15,
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
        logger.info("SchedulerService started — 3 jobs registered")

    async def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("SchedulerService stopped")

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
                            "meal_relation": medication.meal_relation.value,
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
    # Job 2 — Process follow-ups (every 15 min)
    # ------------------------------------------------------------------

    async def process_follow_ups(self) -> None:
        """Re-call patients who said not_taken / callback_requested ≥ 30 min ago."""
        logger.info("process_follow_ups — starting")
        try:
            async with self._session_factory() as db:
                engine = AdherenceEngine(db)
                pending = await engine.get_follow_up_patients()

                if not pending:
                    logger.debug("No follow-ups pending")
                    return

                now = datetime.now(timezone.utc)
                thirty_min_ago = now - timedelta(minutes=30)

                for entry in pending:
                    try:
                        created = datetime.fromisoformat(entry["created_at"])
                        if created > thirty_min_ago:
                            # Not yet 30 minutes old — skip
                            continue

                        patient_id = uuid.UUID(entry["patient_id"])
                        medication_id = uuid.UUID(entry["medication_id"])

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
                            "meal_relation": medication.meal_relation.value,
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
                        logger.info("Follow-up call triggered for patient %s", patient.name)

                        # Mark original log as follow_up_completed
                        from app.models import AdherenceLog

                        log_id = uuid.UUID(entry["adherence_log_id"])
                        original_log = (
                            await db.execute(
                                select(AdherenceLog).where(AdherenceLog.id == log_id)
                            )
                        ).scalar_one_or_none()
                        if original_log:
                            original_log.follow_up_completed = True

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
                        Patient.family_contact_phone.isnot(None),
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
                            to=patient.family_contact_phone,
                            body=message,
                        )
                        logger.info(
                            "Daily summary sent to %s for patient %s",
                            patient.family_contact_phone,
                            patient.name,
                        )
                    except Exception:
                        logger.exception(
                            "Daily summary failed for patient %s", patient.name
                        )
        except Exception:
            logger.exception("send_daily_summaries — job failed")
