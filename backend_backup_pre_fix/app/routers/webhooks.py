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
    Logs adherence response, evaluates escalation rules, sends alerts via WhatsApp,
    and returns 200 OK.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}

    logger.info("Bolna webhook raw payload received: %s", body)

    # 1. Extract from Bolna payload: call_id, recipient_phone, call_status, transcript, extracted_data
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
    transcript = body.get("transcript") or ""
    call_duration = body.get("call_duration") or body.get("duration")

    extracted_data = (
        body.get("extracted_data")
        or body.get("user_data")
        or {}
    )

    # 2. From extracted_data, get: patient_id, medication_id, time_slot, response, side_effect_details
    patient_id_raw = extracted_data.get("patient_id") or body.get("patient_id")
    medication_id_raw = extracted_data.get("medication_id") or body.get("medication_id")
    time_slot = extracted_data.get("time_slot", "morning")
    response_str = extracted_data.get("response", "no_answer")
    side_effect_details = extracted_data.get("side_effect_details")

    # 3. If call_status indicates call was not answered, log response as "no_answer"
    if str(call_status_raw).lower() in _NO_ANSWER_STATUSES:
        response_str = "no_answer"

    # 4. Resolve patient (by patient_id first, then recipient_phone)
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
            recipient_phone,
            patient_id_raw,
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

    # 6. Call adherence_engine.log_response()
    engine = AdherenceEngine(db)
    log = await engine.log_response(
        patient_id=patient.id,
        medication_id=medication_id,
        time_slot=time_slot,
        response=response_str,
        side_effect_details=side_effect_details,
        bolna_call_id=str(call_id) if call_id else None,
        call_duration=int(call_duration) if call_duration is not None else None,
    )

    # 7. Call adherence_engine.check_escalation_rules()
    alerts = await engine.check_escalation_rules(patient.id, log)

    # 8. For each alert returned, send via twilio_service
    twilio: TwilioService = request.app.state.twilio_service
    await _send_alert_notifications(twilio, alerts, patient, side_effect_details)

    # 9. Return 200 OK
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
    payload: BolnaFunctionPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time function call endpoint hit BY Bolna DURING the call.
    Immediately logs response, runs escalation checks, fires WhatsApp alert
    to family if side_effect, and returns in < 2 seconds so the call doesn't stall.
    """
    logger.info(
        "Bolna function call during call — patient=%s med=%s response=%s",
        payload.patient_id,
        payload.medication_id,
        payload.response,
    )

    try:
        patient_id = uuid.UUID(payload.patient_id)
        medication_id = uuid.UUID(payload.medication_id)

        engine = AdherenceEngine(db)

        # 1. Immediately log the response
        log = await engine.log_response(
            patient_id=patient_id,
            medication_id=medication_id,
            time_slot=payload.time_slot,
            response=payload.response,
            side_effect_details=payload.side_effect_details,
            bolna_call_id=payload.bolna_call_id,
            call_duration=payload.call_duration,
        )

        # 2. Run escalation checks
        alerts = await engine.check_escalation_rules(patient_id, log)

        # 3. If side_effect: immediately fire WhatsApp alert to family
        if payload.response == "side_effect" and alerts:
            twilio: TwilioService = request.app.state.twilio_service
            patient = (
                await db.execute(select(Patient).where(Patient.id == patient_id))
            ).scalar_one_or_none()
            if patient:
                await _send_alert_notifications(
                    twilio, alerts, patient, payload.side_effect_details
                )

        # 4. Return: { "status": "logged", "message": "Thank you" }
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
    payload: BolnaFunctionPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Dedicated endpoint for follow-up call results.
    Logs response, marks original log's follow_up_completed = True,
    runs escalation checks, and returns {"status": "logged", "message": "Thank you"}.
    """
    logger.info(
        "Bolna follow-up call received — patient=%s med=%s response=%s",
        payload.patient_id,
        payload.medication_id,
        payload.response,
    )

    try:
        patient_id = uuid.UUID(payload.patient_id)
        medication_id = uuid.UUID(payload.medication_id)

        engine = AdherenceEngine(db)

        # 1. Log the response
        log = await engine.log_response(
            patient_id=patient_id,
            medication_id=medication_id,
            time_slot=payload.time_slot,
            response=payload.response,
            side_effect_details=payload.side_effect_details,
            bolna_call_id=payload.bolna_call_id,
            call_duration=payload.call_duration,
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

        # 3. Run escalation checks
        alerts = await engine.check_escalation_rules(patient_id, log)

        # 4. If side_effect, immediately notify family via WhatsApp
        if payload.response == "side_effect" and alerts:
            twilio: TwilioService = request.app.state.twilio_service
            patient = (
                await db.execute(select(Patient).where(Patient.id == patient_id))
            ).scalar_one_or_none()
            if patient:
                await _send_alert_notifications(
                    twilio, alerts, patient, payload.side_effect_details
                )

        # 5. Return: { "status": "logged", "message": "Thank you" }
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
