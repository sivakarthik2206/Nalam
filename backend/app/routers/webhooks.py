"""Bolna AI webhook endpoints — post-call, real-time function call, follow-up."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AdherenceLog, Medication, Patient
from app.schemas import (
    BolnaFunctionPayload,
    BolnaFunctionResponse,
    BolnaWebhookPayload,
)
from app.services.adherence_engine import AdherenceEngine
from app.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Bolna call_status values that indicate call was not answered
_NO_ANSWER_STATUSES = {"no_answer", "busy", "failed", "no-answer", "unanswered", "canceled"}


# =====================================================================
# 1. Post-call completion webhook
# =====================================================================


@router.post(
    "/bolna",
    summary="Receive call completion data from Bolna",
    status_code=status.HTTP_200_OK,
)
async def bolna_call_completed(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Receive raw JSON post-call completion webhook from Bolna.
    Extracts call_id, recipient_phone, call_status, transcript, extracted_data.
    Logs adherence outcome, evaluates escalation rules, sends alerts via WhatsApp,
    and returns 200 OK.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}

    logger.info("Bolna webhook raw payload received: %s", body)

    # 1. Extract from Bolna payload
    call_id = (
        body.get("call_id")
        or body.get("id")
        or (body.get("telephony_data") or {}).get("call_id")
        or ""
    )
    recipient_phone = (
        body.get("recipient_phone")
        or body.get("recipient_phone_number")
        or body.get("phone")
        or (body.get("telephony_data") or {}).get("to")
        or ""
    )
    call_status_raw = (
        body.get("call_status")
        or body.get("status")
        or ""
    )
    call_duration = body.get("call_duration") or body.get("duration")

    extracted_data = (
        body.get("extracted_data")
        or body.get("user_data")
        or {}
    )

    # 2. From extracted_data, get: patient_id, medication_id, time_slot, outcome
    patient_id_raw = extracted_data.get("patient_id") or body.get("patient_id")
    medication_id_raw = extracted_data.get("medication_id") or body.get("medication_id")
    time_slot = extracted_data.get("time_slot", "morning")
    outcome_str = (
        extracted_data.get("outcome")
        or extracted_data.get("response")
        or "no_answer"
    )
    side_effect_details = extracted_data.get("side_effect_details")
    notes = extracted_data.get("notes")

    # 3. If call_status indicates call was not answered, force NO_ANSWER
    if str(call_status_raw).lower() in _NO_ANSWER_STATUSES:
        outcome_str = "no_answer"

    # 4. Resolve patient
    patient: Patient | None = None
    if patient_id_raw:
        try:
            p_uuid = uuid.UUID(str(patient_id_raw))
            patient = (
                await db.execute(select(Patient).where(Patient.id == p_uuid))
            ).scalar_one_or_none()
        except ValueError:
            pass

    if not patient and recipient_phone:
        patient = (
            await db.execute(select(Patient).where(Patient.phone == recipient_phone))
        ).scalar_one_or_none()

    if not patient:
        logger.warning(
            "Webhook received for unknown patient (phone=%s, id=%s)",
            recipient_phone, patient_id_raw,
        )
        return {"status": "ignored", "reason": "patient_not_found"}

    # 5. Resolve medication
    medication_id: uuid.UUID | None = None
    if medication_id_raw:
        try:
            medication_id = uuid.UUID(str(medication_id_raw))
        except ValueError:
            logger.warning("Invalid medication_id in extracted_data: %s", medication_id_raw)

    if not medication_id:
        med = (
            await db.execute(
                select(Medication)
                .where(
                    Medication.patient_id == patient.id,
                    Medication.is_active.is_(True),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if med:
            medication_id = med.id
        else:
            logger.warning("No active medication for patient %s", patient.id)
            return {"status": "ignored", "reason": "no_active_medication"}

    # 6. Log response
    engine = AdherenceEngine(db)
    log = await engine.log_response(
        patient_id=patient.id,
        medication_id=medication_id,
        time_slot=time_slot,
        response=outcome_str,
        side_effect_details=side_effect_details,
        bolna_call_id=str(call_id) if call_id else None,
        call_duration=int(call_duration) if call_duration is not None else None,
        notes=notes,
    )

    # 7. Escalation checks
    from app.alerts import evaluate_escalations
    alerts = await evaluate_escalations(db, patient.id, log)

    # 8. Send notifications
    twilio: TwilioService = request.app.state.twilio_service
    await _send_alert_notifications(twilio, alerts, patient, side_effect_details or notes)

    # 9. Schedule retry if needed
    outcome_upper = log.outcome.value
    if outcome_upper in ("MISSED", "NO_ANSWER"):
        try:
            scheduler = request.app.state.scheduler_service
            await scheduler.schedule_retry_call(
                patient_id=str(patient.id),
                medication_id=str(medication_id),
                log_id=str(log.id),
                attempt_number=1,
            )
        except Exception:
            logger.exception("Failed to schedule retry call for patient %s", patient.id)

    return {
        "status": "processed",
        "call_id": call_id,
        "adherence_log_id": str(log.id),
        "alerts_created": len(alerts),
    }


# =====================================================================
# 2. Real-time function call endpoint hit BY Bolna DURING the call
# =====================================================================


@router.post(
    "/bolna/function",
    response_model=BolnaFunctionResponse,
    summary="Real-time function call hit by Bolna during the call",
    status_code=status.HTTP_200_OK,
)
async def bolna_function_call(
    payload: BolnaWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time function call endpoint hit BY Bolna DURING the call.
    Accepts both new spec shape and legacy shape.
    Immediately logs response, runs escalation checks, fires WhatsApp alert
    to family if side_effect, and returns in < 2 seconds so the call doesn't stall.
    """
    normalised_outcome = payload._normalized_outcome
    logger.info(
        "Bolna function call during call — patient=%s med=%s outcome=%s",
        payload.patient_id,
        payload.medication_id,
        normalised_outcome,
    )

    try:
        patient_id = uuid.UUID(payload.patient_id)
        medication_id = uuid.UUID(payload.medication_id) if payload.medication_id else None

        # Resolve medication if not given
        if not medication_id:
            med = (
                await db.execute(
                    select(Medication)
                    .where(
                        Medication.patient_id == patient_id,
                        Medication.is_active.is_(True),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if med:
                medication_id = med.id

        if not medication_id:
            logger.warning("No medication_id resolved for patient %s", patient_id)
            return BolnaFunctionResponse(status="logged", message="Thank you")

        engine = AdherenceEngine(db)

        # 1. Log the response (pass lowercase for legacy compat; engine normalises it)
        log = await engine.log_response(
            patient_id=patient_id,
            medication_id=medication_id,
            time_slot=payload.time_slot or "morning",
            response=normalised_outcome.lower(),
            side_effect_details=payload.side_effect_notes,
            bolna_call_id=payload.bolna_call_id,
            call_duration=payload.call_duration,
            notes=payload._resolved_notes,
        )

        # 2. Escalation checks
        from app.alerts import evaluate_escalations
        alerts = await evaluate_escalations(db, patient_id, log)

        # 3. If side_effect or alerts: fire WhatsApp alert
        if normalised_outcome == "SIDE_EFFECT" and alerts:
            twilio: TwilioService = request.app.state.twilio_service
            patient = (
                await db.execute(select(Patient).where(Patient.id == patient_id))
            ).scalar_one_or_none()
            if patient:
                await _send_alert_notifications(
                    twilio, alerts, patient, payload._resolved_notes
                )

        # 4. Schedule retry if needed
        if normalised_outcome in ("MISSED", "NO_ANSWER") or payload.retry_required:
            try:
                scheduler = request.app.state.scheduler_service
                await scheduler.schedule_retry_call(
                    patient_id=str(patient_id),
                    medication_id=str(medication_id),
                    log_id=str(log.id),
                    attempt_number=1,
                )
            except Exception:
                logger.exception("Failed to schedule retry for patient %s", patient_id)

        return BolnaFunctionResponse(status="logged", message="Thank you")

    except Exception:
        logger.exception("Bolna function call failed during call execution")
        return BolnaFunctionResponse(status="logged", message="Thank you")


# =====================================================================
# 3. Dedicated endpoint for follow-up call results
# =====================================================================


@router.post(
    "/bolna/follow-up",
    response_model=BolnaFunctionResponse,
    summary="Dedicated endpoint for follow-up call results",
    status_code=status.HTTP_200_OK,
)
async def bolna_follow_up(
    payload: BolnaWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Dedicated endpoint for follow-up call results.
    Logs response, marks original log's follow_up_completed = True,
    runs escalation checks, and returns {"status": "logged", "message": "Thank you"}.
    """
    normalised_outcome = payload._normalized_outcome
    logger.info(
        "Bolna follow-up call received — patient=%s med=%s outcome=%s",
        payload.patient_id,
        payload.medication_id,
        normalised_outcome,
    )

    try:
        patient_id = uuid.UUID(payload.patient_id)
        medication_id = uuid.UUID(payload.medication_id) if payload.medication_id else None

        if not medication_id:
            med = (
                await db.execute(
                    select(Medication)
                    .where(
                        Medication.patient_id == patient_id,
                        Medication.is_active.is_(True),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if med:
                medication_id = med.id

        if not medication_id:
            return BolnaFunctionResponse(status="logged", message="Thank you")

        engine = AdherenceEngine(db)

        # 1. Log the response
        log = await engine.log_response(
            patient_id=patient_id,
            medication_id=medication_id,
            time_slot=payload.time_slot or "morning",
            response=normalised_outcome.lower(),
            side_effect_details=payload.side_effect_notes,
            bolna_call_id=payload.bolna_call_id,
            call_duration=payload.call_duration,
            notes=payload._resolved_notes,
        )

        # 2. Mark the original log's follow_up_completed = True
        original_q = (
            select(AdherenceLog)
            .where(
                and_(
                    AdherenceLog.patient_id == patient_id,
                    AdherenceLog.medication_id == medication_id,
                    AdherenceLog.follow_up_needed.is_(True),
                    AdherenceLog.follow_up_completed.is_(False),
                    AdherenceLog.id != log.id,
                )
            )
            .order_by(AdherenceLog.created_at.desc())
            .limit(1)
        )
        original_log = (await db.execute(original_q)).scalar_one_or_none()
        if original_log:
            original_log.follow_up_completed = True
            logger.info("Marked previous log %s follow_up_completed = True", original_log.id)

        # 3. Escalation checks
        from app.alerts import evaluate_escalations
        alerts = await evaluate_escalations(db, patient_id, log)

        # 4. If side_effect, immediately notify family
        if normalised_outcome == "SIDE_EFFECT" and alerts:
            twilio: TwilioService = request.app.state.twilio_service
            patient = (
                await db.execute(select(Patient).where(Patient.id == patient_id))
            ).scalar_one_or_none()
            if patient:
                await _send_alert_notifications(
                    twilio, alerts, patient, payload._resolved_notes
                )

        return BolnaFunctionResponse(status="logged", message="Thank you")

    except Exception:
        logger.exception("Bolna follow-up call handling failed")
        return BolnaFunctionResponse(status="logged", message="Thank you")


# =====================================================================
# Helper
# =====================================================================


async def _send_alert_notifications(
    twilio: TwilioService,
    alerts: list,
    patient: Patient,
    details: str | None = None,
) -> None:
    """Send WhatsApp messages to family contact for generated alerts."""
    for alert in alerts:
        if alert.sent_to and alert.channel.value == "whatsapp":
            try:
                body = twilio.format_alert(
                    alert_type=alert.alert_type.value,
                    patient_name=patient.name,
                    details=alert.message,
                    language=patient.language.value,
                )
                await twilio.send_whatsapp(to=alert.sent_to, body=body)
                logger.info(
                    "WhatsApp alert (%s) sent to %s for patient %s",
                    alert.alert_type.value,
                    alert.sent_to,
                    patient.name,
                )
            except Exception:
                logger.exception("Failed to send WhatsApp alert to %s", alert.sent_to)
