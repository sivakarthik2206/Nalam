"""Core adherence logic — logging, scoring, escalation, refill prediction."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Alert,
    AlertTypeEnum,
    ChannelEnum,
    Medication,
    Patient,
    SeverityEnum,
    TimeSlotEnum,
)

logger = logging.getLogger(__name__)


class AdherenceEngine:
    """All adherence-related business logic."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db = db_session

    # ------------------------------------------------------------------
    # 1. Log a patient response
    # ------------------------------------------------------------------

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
    ) -> AdherenceLog:
        """Create an adherence log entry and return it."""
        try:
            # Resolve enums
            slot_enum: TimeSlotEnum | None = None
            try:
                slot_enum = TimeSlotEnum(time_slot)
            except ValueError:
                logger.warning("Unknown time_slot '%s', storing as None", time_slot)

            # Normalise aliases: lowercase → uppercase canonical
            _RESPONSE_ALIASES: dict[str, str] = {
                "taken": "TAKEN",
                "not_taken": "MISSED",
                "missed": "MISSED",
                "side_effect": "SIDE_EFFECT",
                "no_answer": "NO_ANSWER",
                "stock_out": "STOCK_OUT",
                "callback_requested": "CALLBACK_REQUESTED",
                "rescheduled": "CALLBACK_REQUESTED",
            }
            normalised = _RESPONSE_ALIASES.get(response.lower().strip(), response.upper().strip())
            response_enum = AdherenceResponseEnum(normalised)

            follow_up = response_enum in (
                AdherenceResponseEnum.MISSED,
                AdherenceResponseEnum.NO_ANSWER,
                AdherenceResponseEnum.CALLBACK_REQUESTED,
            )

            log = AdherenceLog(
                patient_id=patient_id,
                medication_id=medication_id,
                scheduled_time_slot=slot_enum,
                call_time=datetime.now(timezone.utc),
                outcome=response_enum,
                side_effect_details=side_effect_details,
                notes=notes or side_effect_details,
                call_duration_seconds=call_duration,
                bolna_call_id=bolna_call_id,
                follow_up_needed=follow_up,
            )
            self.db.add(log)
            await self.db.flush()
            await self.db.refresh(log)
            logger.info(
                "Adherence log created id=%s patient=%s outcome=%s follow_up=%s",
                log.id, patient_id, normalised, follow_up,
            )
            return log
        except Exception:
            logger.exception("Failed to create adherence log for patient %s", patient_id)
            raise

    # ------------------------------------------------------------------
    # 2. Compute adherence score
    # ------------------------------------------------------------------

    async def compute_adherence_score(self, patient_id: uuid.UUID, days: int = 7) -> float:
        """
        Score = (taken logs) / (total expected doses in period) × 100.

        Total expected doses = Σ(len(med.frequency) for each active med) × days.
        """
        try:
            since = datetime.now(timezone.utc) - timedelta(days=days)

            # Count taken logs in period
            taken_q = (
                select(func.count())
                .select_from(AdherenceLog)
                .where(
                    and_(
                        AdherenceLog.patient_id == patient_id,
                        AdherenceLog.created_at >= since,
                        AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                    )
                )
            )
            taken = (await self.db.execute(taken_q)).scalar() or 0

            # Compute expected doses
            meds_q = select(Medication).where(
                and_(
                    Medication.patient_id == patient_id,
                    Medication.is_active.is_(True),
                )
            )
            meds = (await self.db.execute(meds_q)).scalars().all()

            total_expected = 0
            for med in meds:
                freq = med.frequency if isinstance(med.frequency, list) else []
                total_expected += len(freq) * days

            if total_expected == 0:
                return 0.0

            score = round((taken / total_expected) * 100, 1)
            return min(score, 100.0)  # cap at 100
        except Exception:
            logger.exception("Failed to compute adherence score for patient %s", patient_id)
            return 0.0

    # ------------------------------------------------------------------
    # 3. Escalation rules
    # ------------------------------------------------------------------

    async def check_escalation_rules(
        self, patient_id: uuid.UUID, latest_log: AdherenceLog
    ) -> list[Alert]:
        """Evaluate all escalation rules and return created alerts.

        Thin wrapper — delegates to alerts.evaluate_escalations for actual logic.
        """
        try:
            from app.alerts import evaluate_escalations
            return await evaluate_escalations(self.db, patient_id, latest_log)
        except ImportError:
            # Fallback to inline logic if alerts module not available
            return await self._check_escalation_rules_inline(patient_id, latest_log)

    async def _check_escalation_rules_inline(
        self, patient_id: uuid.UUID, latest_log: AdherenceLog
    ) -> list[Alert]:
        """Inline escalation logic (used as fallback)."""
        alerts_created: list[Alert] = []

        try:
            patient = (
                await self.db.execute(select(Patient).where(Patient.id == patient_id))
            ).scalar_one_or_none()
            if not patient:
                return alerts_created

            medication = (
                await self.db.execute(
                    select(Medication).where(Medication.id == latest_log.medication_id)
                )
            ).scalar_one_or_none()
            med_name = medication.name if medication else "Unknown"
            outcome = latest_log.outcome

            family_contact = patient.family_whatsapp
            channel = ChannelEnum.whatsapp if family_contact else ChannelEnum.dashboard

            # Rule 1: SIDE_EFFECT → CRITICAL
            if outcome == AdherenceResponseEnum.SIDE_EFFECT:
                alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.side_effect,
                    severity=SeverityEnum.critical,
                    message=(
                        f"{patient.name} reported a side effect for {med_name}"
                        f"{': ' + (latest_log.side_effect_details or latest_log.notes or 'symptom not specified') if (latest_log.side_effect_details or latest_log.notes) else '.'}"
                    ),
                    sent_to=family_contact,
                    channel=channel,
                )
                self.db.add(alert)
                alerts_created.append(alert)

            # Rule 2: NO_ANSWER — consecutive
            if outcome == AdherenceResponseEnum.NO_ANSWER:
                prev_q = (
                    select(AdherenceLog)
                    .where(
                        and_(
                            AdherenceLog.patient_id == patient_id,
                            AdherenceLog.id != latest_log.id,
                        )
                    )
                    .order_by(AdherenceLog.created_at.desc())
                    .limit(1)
                )
                prev_log = (await self.db.execute(prev_q)).scalar_one_or_none()
                if prev_log and prev_log.outcome == AdherenceResponseEnum.NO_ANSWER:
                    alert = Alert(
                        patient_id=patient_id,
                        alert_type=AlertTypeEnum.no_answer,
                        severity=SeverityEnum.warning,
                        message=f"{patient.name} has not answered the last 2 medication check-in calls.",
                        sent_to=family_contact,
                        channel=channel,
                    )
                    self.db.add(alert)
                    alerts_created.append(alert)

            # Rule 3: STOCK_OUT
            if outcome == AdherenceResponseEnum.STOCK_OUT:
                stock_alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.stock_out,
                    severity=SeverityEnum.warning,
                    message=f"{patient.name} has run out of {med_name}.",
                    sent_to=family_contact,
                    channel=channel,
                )
                self.db.add(stock_alert)
                alerts_created.append(stock_alert)

                refill_alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.refill_due,
                    severity=SeverityEnum.warning,
                    message=f"Refill needed for {patient.name} — {med_name}.",
                    sent_to=None,
                    channel=ChannelEnum.dashboard,
                )
                self.db.add(refill_alert)
                alerts_created.append(refill_alert)

            # Rule 4: low adherence < 60%
            score_7d = await self.compute_adherence_score(patient_id, days=7)
            if score_7d < 60.0:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                existing_q = (
                    select(func.count())
                    .select_from(Alert)
                    .where(
                        and_(
                            Alert.patient_id == patient_id,
                            Alert.alert_type == AlertTypeEnum.low_adherence,
                            Alert.created_at >= today_start,
                        )
                    )
                )
                existing = (await self.db.execute(existing_q)).scalar() or 0
                if existing == 0:
                    alert = Alert(
                        patient_id=patient_id,
                        alert_type=AlertTypeEnum.low_adherence,
                        severity=SeverityEnum.warning,
                        message=f"{patient.name}'s 7-day medication adherence is {score_7d}%. Needs attention.",
                        sent_to=family_contact,
                        channel=channel,
                    )
                    self.db.add(alert)
                    alerts_created.append(alert)

            # Rule 5: 3 consecutive MISSED for same medication
            if outcome == AdherenceResponseEnum.MISSED:
                recent_q = (
                    select(AdherenceLog.outcome)
                    .where(
                        and_(
                            AdherenceLog.patient_id == patient_id,
                            AdherenceLog.medication_id == latest_log.medication_id,
                        )
                    )
                    .order_by(AdherenceLog.created_at.desc())
                    .limit(3)
                )
                recent = (await self.db.execute(recent_q)).scalars().all()
                if (
                    len(recent) >= 3
                    and all(r == AdherenceResponseEnum.MISSED for r in recent)
                ):
                    alert = Alert(
                        patient_id=patient_id,
                        alert_type=AlertTypeEnum.missed_dose,
                        severity=SeverityEnum.warning,
                        message=f"{patient.name} has missed {med_name} for 3 consecutive doses.",
                        sent_to=family_contact,
                        channel=channel,
                    )
                    self.db.add(alert)
                    alerts_created.append(alert)

            await self.db.flush()
        except Exception:
            logger.exception("Escalation rule check failed for patient %s", patient_id)

        return alerts_created

    # ------------------------------------------------------------------
    # 4. Refill predictions
    # ------------------------------------------------------------------

    async def get_refill_predictions(
        self, patient_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        """Return refill prediction data for active medications."""
        results: list[dict[str, Any]] = []
        try:
            med_q = select(Medication).where(Medication.is_active.is_(True))
            if patient_id:
                med_q = med_q.where(Medication.patient_id == patient_id)

            medications = (await self.db.execute(med_q)).scalars().all()

            for med in medications:
                if not med.pills_dispensed or not med.prescription_start_date:
                    continue

                # Count taken logs since prescription start
                taken_q = (
                    select(func.count())
                    .select_from(AdherenceLog)
                    .where(
                        and_(
                            AdherenceLog.medication_id == med.id,
                            AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                            AdherenceLog.created_at >= datetime.combine(
                                med.prescription_start_date,
                                datetime.min.time(),
                                tzinfo=timezone.utc,
                            ),
                        )
                    )
                )
                pills_consumed = (await self.db.execute(taken_q)).scalar() or 0
                pills_remaining = max(med.pills_dispensed - pills_consumed, 0)

                freq = med.frequency if isinstance(med.frequency, list) else []
                daily_consumption = len(freq)

                # Adjust for actual adherence rate
                adherence = await self.compute_adherence_score(med.patient_id, days=7)
                effective_daily = daily_consumption * (adherence / 100) if adherence > 0 else 0

                days_remaining = (
                    round(pills_remaining / effective_daily, 1)
                    if effective_daily > 0
                    else 0
                )

                results.append(
                    {
                        "patient_id": str(med.patient_id),
                        "medication_id": str(med.id),
                        "medication_name": med.name,
                        "pills_dispensed": med.pills_dispensed,
                        "pills_consumed": pills_consumed,
                        "pills_remaining": pills_remaining,
                        "daily_consumption": daily_consumption,
                        "effective_daily": round(effective_daily, 2),
                        "days_remaining": days_remaining,
                        "refill_urgent": days_remaining <= 5,
                    }
                )
        except Exception:
            logger.exception("Refill prediction failed")

        return results

    # ------------------------------------------------------------------
    # 5. Daily summary for one patient
    # ------------------------------------------------------------------

    async def get_daily_summary(self, patient_id: uuid.UUID) -> dict[str, Any]:
        """
        Today's adherence summary for a single patient.

        Returns dict with patient_name, medications status list,
        overall counts (total, taken, missed, pending), and today score.
        """
        try:
            patient = (
                await self.db.execute(
                    select(Patient)
                    .options(selectinload(Patient.medications))
                    .where(Patient.id == patient_id)
                )
            ).scalar_one_or_none()
            if not patient:
                return {"error": "patient_not_found"}

            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # Today's logs
            today_logs_q = select(AdherenceLog).where(
                and_(
                    AdherenceLog.patient_id == patient_id,
                    AdherenceLog.created_at >= today_start,
                )
            )
            today_logs = (await self.db.execute(today_logs_q)).scalars().all()

            # Build lookup: (medication_id, slot) → outcome
            log_lookup: dict[tuple[uuid.UUID, str | None], str] = {}
            for log in today_logs:
                slot_val = log.scheduled_time_slot.value if log.scheduled_time_slot else None
                log_lookup[(log.medication_id, slot_val)] = log.outcome.value

            medications_status: list[dict[str, str]] = []
            total_doses = 0
            doses_taken = 0
            doses_missed = 0
            doses_pending = 0
            slot_statuses: dict[str, str] = {}

            for med in patient.medications:
                if not med.is_active:
                    continue
                freq = med.frequency if isinstance(med.frequency, list) else []
                for slot in freq:
                    total_doses += 1
                    status = log_lookup.get((med.id, slot), "pending")
                    if status == "TAKEN":
                        doses_taken += 1
                        status = "taken"
                    elif status in ("MISSED", "NO_ANSWER", "STOCK_OUT"):
                        doses_missed += 1
                        status = "not_taken"
                    else:
                        doses_pending += 1
                        status = "pending"

                    medications_status.append(
                        {"medication_name": med.name, "time_slot": slot, "status": status}
                    )
                    # Keep first status per slot for summary formatting
                    if slot not in slot_statuses:
                        slot_statuses[slot] = status

            today_score = round((doses_taken / total_doses) * 100, 1) if total_doses > 0 else 0.0
            score_7d = await self.compute_adherence_score(patient_id, days=7)

            return {
                "patient_id": str(patient_id),
                "patient_name": patient.name,
                "language": patient.language.value,
                "family_whatsapp": patient.family_whatsapp,
                # Keep legacy key for backward compat with scheduler
                "family_contact_phone": patient.family_whatsapp,
                "medications": medications_status,
                "slot_statuses": slot_statuses,
                "total_doses_today": total_doses,
                "doses_taken": doses_taken,
                "doses_missed": doses_missed,
                "doses_pending": doses_pending,
                "today_score": today_score,
                "adherence_score_7d": score_7d,
            }
        except Exception:
            logger.exception("Failed to build daily summary for patient %s", patient_id)
            return {"error": "summary_failed"}

    # ------------------------------------------------------------------
    # 6. Follow-up patients
    # ------------------------------------------------------------------

    async def get_follow_up_patients(self) -> list[dict[str, Any]]:
        """
        Return logs where follow_up_needed=True, follow_up_completed=False,
        and created within the last 2 hours.
        """
        results: list[dict[str, Any]] = []
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            stmt = (
                select(AdherenceLog)
                .where(
                    and_(
                        AdherenceLog.follow_up_needed.is_(True),
                        AdherenceLog.follow_up_completed.is_(False),
                        AdherenceLog.created_at >= cutoff,
                    )
                )
                .order_by(AdherenceLog.created_at.asc())
            )
            logs = (await self.db.execute(stmt)).scalars().all()
            for log in logs:
                results.append(
                    {
                        "adherence_log_id": str(log.id),
                        "patient_id": str(log.patient_id),
                        "medication_id": str(log.medication_id),
                        "time_slot": log.scheduled_time_slot.value if log.scheduled_time_slot else None,
                        "outcome": log.outcome.value,
                        # Legacy key
                        "response": log.outcome.value,
                        "retry_scheduled": log.retry_scheduled,
                        "created_at": log.created_at.isoformat(),
                    }
                )
        except Exception:
            logger.exception("Failed to query follow-up patients")
        return results
