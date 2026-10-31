"""Centralised alert evaluation and dispatch module."""

import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Alert,
    AlertTypeEnum,
    ChannelEnum,
    DeliveryStatusEnum,
    Medication,
    Patient,
    SeverityEnum,
)

if TYPE_CHECKING:
    from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

_DEDUP_HOURS = 6


def _delivery_succeeded(result: object) -> bool:
    return isinstance(result, Mapping) and not result.get("error") and bool(result.get("sid"))


def _delivery_retryable(result: object) -> bool:
    return isinstance(result, Mapping) and bool(result.get("retryable", False))


async def _recent_alert_exists(
    db: AsyncSession,
    patient_id: uuid.UUID,
    alert_type: AlertTypeEnum,
    hours: int = _DEDUP_HOURS,
) -> bool:
    """Return True if an alert of this type was created for patient in the last `hours` hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = (
        select(func.count())
        .select_from(Alert)
        .where(
            and_(
                Alert.patient_id == patient_id,
                Alert.alert_type == alert_type,
                Alert.created_at >= cutoff,
            )
        )
    )
    count = (await db.execute(q)).scalar() or 0
    return count > 0


async def evaluate_escalations(
    db: AsyncSession,
    patient_id: uuid.UUID,
    latest_log: AdherenceLog,
) -> list[Alert]:
    """
    Evaluate all 5 escalation rules for a given adherence log.
    Returns a list of Alert objects added to the session (not yet committed).

    Uses 6-hour deduplication: skips creating an alert if one of the same type
    was already created for this patient in the last 6 hours.
    """
    alerts_created: list[Alert] = []

    try:
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if not patient:
            return alerts_created

        medication = (
            await db.execute(
                select(Medication).where(Medication.id == latest_log.medication_id)
            )
        ).scalar_one_or_none()
        med_name = medication.name if medication else "Unknown"
        outcome = latest_log.outcome

        family_contact = patient.family_whatsapp
        channel = ChannelEnum.whatsapp if family_contact else ChannelEnum.dashboard

        # Rule 1: SIDE_EFFECT → CRITICAL
        if outcome == AdherenceResponseEnum.SIDE_EFFECT:
            if not await _recent_alert_exists(db, patient_id, AlertTypeEnum.side_effect):
                symptom = latest_log.side_effect_details or latest_log.notes or "symptom not specified"
                alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.side_effect,
                    severity=SeverityEnum.critical,
                    message=(
                        f"{patient.name} reported a side effect for {med_name}: {symptom}"
                    ),
                    sent_to=family_contact,
                    channel=channel,
                )
                db.add(alert)
                alerts_created.append(alert)
                logger.info("CRITICAL side_effect alert created for patient %s", patient_id)

        # Rule 2: NO_ANSWER — consecutive
        if outcome == AdherenceResponseEnum.NO_ANSWER:
            if not await _recent_alert_exists(db, patient_id, AlertTypeEnum.no_answer):
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
                prev_log = (await db.execute(prev_q)).scalar_one_or_none()
                if prev_log and prev_log.outcome == AdherenceResponseEnum.NO_ANSWER:
                    alert = Alert(
                        patient_id=patient_id,
                        alert_type=AlertTypeEnum.no_answer,
                        severity=SeverityEnum.warning,
                        message=f"{patient.name} has not answered the last 2 medication check-in calls.",
                        sent_to=family_contact,
                        channel=channel,
                    )
                    db.add(alert)
                    alerts_created.append(alert)
                    logger.info("WARNING no_answer alert (consecutive) for patient %s", patient_id)

        # Rule 3: STOCK_OUT → stock_out alert + refill_due alert
        if outcome == AdherenceResponseEnum.STOCK_OUT:
            if not await _recent_alert_exists(db, patient_id, AlertTypeEnum.stock_out):
                stock_alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.stock_out,
                    severity=SeverityEnum.warning,
                    message=f"{patient.name} has run out of {med_name}.",
                    sent_to=family_contact,
                    channel=channel,
                )
                db.add(stock_alert)
                alerts_created.append(stock_alert)

            if not await _recent_alert_exists(db, patient_id, AlertTypeEnum.refill_due):
                refill_alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.refill_due,
                    severity=SeverityEnum.warning,
                    message=f"Refill needed for {patient.name} — {med_name}.",
                    sent_to=None,
                    channel=ChannelEnum.dashboard,
                )
                db.add(refill_alert)
                alerts_created.append(refill_alert)
                logger.info("WARNING stock_out + refill_due alerts for patient %s", patient_id)

        # Rule 4: low adherence (< 60% over 7 days)
        from app.services.adherence_engine import AdherenceEngine
        engine = AdherenceEngine(db)
        score_7d = await engine.compute_adherence_score(patient_id, days=7)
        if score_7d < 60.0:
            if not await _recent_alert_exists(db, patient_id, AlertTypeEnum.low_adherence):
                alert = Alert(
                    patient_id=patient_id,
                    alert_type=AlertTypeEnum.low_adherence,
                    severity=SeverityEnum.warning,
                    message=f"{patient.name}'s 7-day medication adherence is {score_7d}%. Needs attention.",
                    sent_to=family_contact,
                    channel=channel,
                )
                db.add(alert)
                alerts_created.append(alert)
                logger.info("WARNING low_adherence alert for patient %s (%.1f%%)", patient_id, score_7d)

        # Rule 5: 3 consecutive MISSED for same medication
        if outcome == AdherenceResponseEnum.MISSED:
            if not await _recent_alert_exists(db, patient_id, AlertTypeEnum.missed_dose):
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
                recent = (await db.execute(recent_q)).scalars().all()
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
                    db.add(alert)
                    alerts_created.append(alert)
                    logger.info(
                        "WARNING missed_dose (3 consecutive) for patient %s med %s",
                        patient_id, med_name,
                    )

        await db.flush()
    except Exception:
        logger.exception("Escalation rule check failed for patient %s", patient_id)
        raise

    return alerts_created


async def send_daily_summary(
    db: AsyncSession,
    twilio: "TwilioService",
    patient: Patient,
    app_base_url: str = "",
) -> bool:
    """Send WhatsApp daily summary for one patient. Returns True on success."""
    try:
        from app.services.adherence_engine import AdherenceEngine
        engine = AdherenceEngine(db)
        summary = await engine.get_daily_summary(patient.id)
        if summary.get("error"):
            return False

        if app_base_url:
            summary["dashboard_link"] = f"{app_base_url}/family/{patient.id}"

        language = patient.language.value
        message = twilio.format_daily_summary(summary, language=language)

        to = patient.family_whatsapp
        if not to:
            return False

        result = await twilio.send_whatsapp(to=to, body=message)
        if not _delivery_succeeded(result):
            logger.error(
                "Daily summary delivery failed patient=%s retryable=%s",
                patient.id,
                _delivery_retryable(result),
            )
            return False
        logger.info("Daily summary delivered patient=%s", patient.id)
        return True
    except Exception:
        logger.exception("send_daily_summary failed for patient %s", patient.id)
        return False


async def send_refill_alert(
    twilio: "TwilioService",
    patient: Patient,
    medication_name: str,
    days_remaining: float,
) -> bool:
    """Send a refill-due alert via WhatsApp. Returns True on success."""
    try:
        details = f"{medication_name} ({int(days_remaining)} days remaining)"
        body = twilio.format_alert(
            alert_type="refill_due",
            patient_name=patient.name,
            details=details,
            language=patient.language.value,
        )
        to = patient.family_whatsapp
        if not to:
            return False
        result = await twilio.send_whatsapp(to=to, body=body)
        if not _delivery_succeeded(result):
            logger.error("Refill alert delivery failed patient=%s", patient.id)
            return False
        return True
    except Exception:
        logger.exception("send_refill_alert failed for patient %s", patient.id)
        return False


async def send_side_effect_alert(
    twilio: "TwilioService",
    patient: Patient,
    medication_name: str,
    symptom: str,
) -> bool:
    """Send a side-effect alert via WhatsApp. Returns True on success."""
    try:
        details = f"{medication_name}: {symptom}"
        body = twilio.format_alert(
            alert_type="side_effect",
            patient_name=patient.name,
            details=details,
            language=patient.language.value,
        )
        to = patient.family_whatsapp
        if not to:
            return False
        result = await twilio.send_whatsapp(to=to, body=body)
        if not _delivery_succeeded(result):
            logger.error("Side-effect alert delivery failed patient=%s", patient.id)
            return False
        return True
    except Exception:
        logger.exception("send_side_effect_alert failed for patient %s", patient.id)
        return False


async def send_no_answer_alert(
    twilio: "TwilioService",
    patient: Patient,
) -> bool:
    """Send a no-answer alert via WhatsApp. Returns True on success."""
    try:
        body = twilio.format_alert(
            alert_type="no_answer",
            patient_name=patient.name,
            details="recent attempts",
            language=patient.language.value,
        )
        to = patient.family_whatsapp
        if not to:
            return False
        result = await twilio.send_whatsapp(to=to, body=body)
        if not _delivery_succeeded(result):
            logger.error("No-answer alert delivery failed patient=%s", patient.id)
            return False
        return True
    except Exception:
        logger.exception("send_no_answer_alert failed for patient %s", patient.id)
        return False


async def send_alert_notifications(
    twilio: "TwilioService",
    alerts: list[Alert],
    patient: Patient,
    db: AsyncSession | None = None,
) -> tuple[int, int]:
    """Deliver generated alerts and report ``(delivered, failed)`` counts.

    The Alert row is committed before this function is called. Twilio performs
    bounded transport retries, while this function keeps provider failures
    observable and never treats an error response as delivery success.
    When a database session is supplied, the existing Alert delivery fields are
    updated so dashboard operators can distinguish pending, sent, and failed.
    """
    delivered = 0
    failed = 0
    for alert in alerts:
        if not alert.sent_to or alert.channel != ChannelEnum.whatsapp:
            continue
        alert.delivery_attempt_count += 1
        alert.delivery_status = DeliveryStatusEnum.sending
        if db is not None:
            await db.flush()
        body = twilio.format_alert(
            alert_type=alert.alert_type.value,
            patient_name=patient.name,
            details=alert.message,
            language="tamil",
        )
        try:
            result = await twilio.send_whatsapp(to=alert.sent_to, body=body)
        except Exception:
            failed += 1
            alert.delivery_status = DeliveryStatusEnum.failed
            alert.delivery_failure_reason = "provider_exception"
            logger.exception("Alert delivery raised patient=%s alert_id=%s", patient.id, alert.id)
            continue
        if not _delivery_succeeded(result):
            failed += 1
            alert.delivery_status = DeliveryStatusEnum.failed
            alert.delivery_failure_reason = (
                str(result.get("detail", "provider_rejected"))[:500]
                if isinstance(result, Mapping)
                else "provider_rejected"
            )
            logger.error(
                "Alert delivery failed patient=%s alert_id=%s retryable=%s",
                patient.id,
                alert.id,
                _delivery_retryable(result),
            )
            continue
        delivered += 1
        alert.delivery_status = DeliveryStatusEnum.sent
        if isinstance(result, Mapping):
            provider_sid = result.get("sid")
            alert.provider_message_id = provider_sid if isinstance(provider_sid, str) else None
        logger.info("Alert delivered patient=%s alert_id=%s", patient.id, alert.id)
    if db is not None:
        await db.commit()
    return delivered, failed
