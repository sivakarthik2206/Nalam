"""Authenticated, idempotent Bolna callback endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from collections.abc import Mapping
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts import evaluate_escalations, send_alert_notifications
from app.database import get_db
from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    CallRecord,
    CallStatusEnum,
    Medication,
    Patient,
)
from app.schemas import BolnaFunctionResponse, BolnaWebhookPayload
from app.services.adherence_engine import AdherenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

_ALLOWED_OUTCOMES: Final[set[str]] = {
    member.value for member in AdherenceResponseEnum
}
_NO_ANSWER_STATUSES: Final[set[str]] = {
    "busy",
    "failed",
    "no-answer",
    "no_answer",
    "unanswered",
    "canceled",
    "cancelled",
}
_FINAL_STATUSES: Final[set[str]] = _NO_ANSWER_STATUSES | {
    "completed",
}
_CALL_STATUS_MAP: Final[dict[str, CallStatusEnum]] = {
    "scheduled": CallStatusEnum.scheduled,
    "queued": CallStatusEnum.scheduled,
    "initiated": CallStatusEnum.initiated,
    "ringing": CallStatusEnum.ringing,
    "answered": CallStatusEnum.answered,
    "in-progress": CallStatusEnum.in_progress,
    "in_progress": CallStatusEnum.in_progress,
    "completed": CallStatusEnum.completed,
    "no-answer": CallStatusEnum.no_answer,
    "no_answer": CallStatusEnum.no_answer,
    "busy": CallStatusEnum.busy,
    "failed": CallStatusEnum.failed,
    "canceled": CallStatusEnum.cancelled,
    "cancelled": CallStatusEnum.cancelled,
    "call-disconnected": CallStatusEnum.disconnected,
    "call_disconnected": CallStatusEnum.disconnected,
}


def _normalise_outcome(value: object) -> str:
    aliases = {
        "taken": "TAKEN",
        "not_taken": "MISSED",
        "missed": "MISSED",
        "side_effect": "SIDE_EFFECT",
        "no_answer": "NO_ANSWER",
        "stock_out": "STOCK_OUT",
        "callback_requested": "CALLBACK_REQUESTED",
        "rescheduled": "CALLBACK_REQUESTED",
    }
    raw = str(value).strip()
    return aliases.get(raw.lower(), raw.upper())


def _clean_phone(value: object) -> str:
    phone = str(value).strip()
    if phone.lower().startswith("whatsapp:"):
        phone = phone[9:]
    return phone


async def _verified_json(request: Request) -> dict[str, object]:
    """Verify Bolna's HMAC signature before parsing or using callback data."""
    raw_body = await request.body()
    secret = os.getenv("BOLNA_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bolna webhook verification is not configured",
        )

    provided = (
        request.headers.get("x-bolna-signature")
        or request.headers.get("x-webhook-signature")
        or ""
    ).strip()
    static_secret = request.headers.get("x-bolna-webhook-secret", "").strip()
    if static_secret and hmac.compare_digest(static_secret, secret):
        provided = ""
    elif not provided:
        logger.warning("Rejected Bolna webhook without signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing webhook signature")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided_hex = provided.removeprefix("sha256=").strip()
    if provided and (not provided_hex or not hmac.compare_digest(provided_hex, expected)):
        logger.warning("Rejected Bolna webhook with invalid signature")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook body must be an object")
    return dict(parsed)


def _validate_payload_contract(payload: BolnaWebhookPayload, event_id: str) -> None:
    if not event_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="bolna_call_id or X-Bolna-Event-ID is required for idempotency",
        )
    try:
        uuid.UUID(payload.patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid patient_id") from exc
    if payload.medication_id:
        try:
            uuid.UUID(payload.medication_id)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid medication_id") from exc

    outcome = payload._normalized_outcome
    if outcome not in _ALLOWED_OUTCOMES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported adherence outcome")
    if outcome == "SIDE_EFFECT" and payload.side_effect_noted is False:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="SIDE_EFFECT requires side_effect_noted=true")
    if outcome == "TAKEN" and payload.retry_required:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="TAKEN cannot require a retry")
    if payload.notes and len(payload.notes) > 2000:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="notes is too long")
    if payload.call_duration is not None and not 0 <= payload.call_duration <= 86_400:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid call_duration")


async def _find_patient_and_medication(
    db: AsyncSession,
    *,
    patient_id_raw: object,
    recipient_phone: object,
    medication_id_raw: object,
) -> tuple[Patient, Medication]:
    patient: Patient | None = None
    if patient_id_raw:
        try:
            patient_id = uuid.UUID(str(patient_id_raw))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid patient_id") from exc
        patient = (
            await db.execute(
                select(Patient).where(Patient.id == patient_id).with_for_update()
            )
        ).scalar_one_or_none()
    if patient is None and recipient_phone:
        patient = (
            await db.execute(
                select(Patient).where(Patient.phone == _clean_phone(recipient_phone)).with_for_update()
            )
        ).scalar_one_or_none()
    if not patient or not patient.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active patient not found")

    medication_id: uuid.UUID | None = None
    if medication_id_raw:
        try:
            medication_id = uuid.UUID(str(medication_id_raw))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid medication_id") from exc
    query = select(Medication).where(
        and_(
            Medication.patient_id == patient.id,
            Medication.is_active.is_(True),
        )
    )
    if medication_id:
        query = query.where(Medication.id == medication_id)
    medication = (await db.execute(query.limit(1))).scalar_one_or_none()
    if not medication:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Active medication not found for patient")
    return patient, medication


async def _existing_event(
    db: AsyncSession,
    *,
    event_id: str,
    patient_id: uuid.UUID,
    medication_id: uuid.UUID,
) -> AdherenceLog | None:
    existing = (
        await db.execute(
            select(AdherenceLog).where(AdherenceLog.bolna_call_id == event_id)
        )
    ).scalar_one_or_none()
    if existing and (
        existing.patient_id != patient_id or existing.medication_id != medication_id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Event identifier already belongs to another dose")
    return existing


async def _record_outcome(
    db: AsyncSession,
    *,
    patient: Patient,
    medication: Medication,
    payload: BolnaWebhookPayload,
    event_id: str,
    mark_previous_follow_up: bool = False,
    provider_status: str = "completed",
) -> tuple[AdherenceLog, list, bool]:
    existing = await _existing_event(
        db,
        event_id=event_id,
        patient_id=patient.id,
        medication_id=medication.id,
    )
    if existing:
        logger.info("Duplicate Bolna event ignored event_id=%s log_id=%s", event_id, existing.id)
        return existing, [], True

    engine = AdherenceEngine(db)
    log = await engine.log_response(
        patient_id=patient.id,
        medication_id=medication.id,
        time_slot=payload.time_slot or "morning",
        response=payload._normalized_outcome.lower(),
        side_effect_details=payload.side_effect_notes,
        bolna_call_id=event_id,
        call_duration=payload.call_duration,
        notes=payload._resolved_notes,
        idempotency_key=f"bolna:{event_id}:{patient.id}:{medication.id}",
        source="voice",
    )
    call_record = (
        await db.execute(select(CallRecord).where(CallRecord.provider_call_id == event_id))
    ).scalar_one_or_none()
    call_status = _CALL_STATUS_MAP.get(provider_status, CallStatusEnum.completed)
    if call_record is None:
        call_record = CallRecord(
            patient_id=patient.id,
            provider_call_id=event_id,
            status=call_status,
            outcome=log.outcome,
            failure_reason=("provider_call_failed" if call_status == CallStatusEnum.failed else None),
            idempotency_key=f"bolna-call:{event_id}",
        )
        db.add(call_record)
        await db.flush()
    else:
        call_record.status = call_status
        call_record.outcome = log.outcome
    log.call_record_id = call_record.id
    if mark_previous_follow_up:
        previous = (
            await db.execute(
                select(AdherenceLog)
                .where(
                    and_(
                        AdherenceLog.patient_id == patient.id,
                        AdherenceLog.medication_id == medication.id,
                        AdherenceLog.follow_up_needed.is_(True),
                        AdherenceLog.follow_up_completed.is_(False),
                        AdherenceLog.id != log.id,
                    )
                )
                .order_by(AdherenceLog.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if previous:
            previous.follow_up_completed = True
    alerts = await evaluate_escalations(db, patient.id, log)
    await db.commit()
    return log, alerts, False


async def _finish_function_event(
    payload: BolnaWebhookPayload,
    request: Request,
    db: AsyncSession,
    *,
    mark_previous_follow_up: bool = False,
) -> BolnaFunctionResponse:
    event_id = payload.bolna_call_id or request.headers.get("x-bolna-event-id", "")
    _validate_payload_contract(payload, event_id)
    patient, medication = await _find_patient_and_medication(
        db,
        patient_id_raw=payload.patient_id,
        recipient_phone=None,
        medication_id_raw=payload.medication_id,
    )
    log, alerts, duplicate = await _record_outcome(
        db,
        patient=patient,
        medication=medication,
        payload=payload,
        event_id=event_id,
        mark_previous_follow_up=mark_previous_follow_up,
    )
    if duplicate:
        return BolnaFunctionResponse(status="duplicate" if duplicate else "logged", message="Thank you")

    delivered, failed = await send_alert_notifications(
        request.app.state.twilio_service,
        alerts,
        patient,
        db=db,
    )
    logger.info(
        "Bolna outcome processed patient=%s log_id=%s alerts=%d delivered=%d failed=%d",
        patient.id,
        log.id,
        len(alerts),
        delivered,
        failed,
    )
    if payload._normalized_outcome in {"MISSED", "NO_ANSWER", "CALLBACK_REQUESTED"}:
        await request.app.state.scheduler_service.schedule_retry_call(
            patient_id=str(patient.id),
            medication_id=str(medication.id),
            log_id=str(log.id),
            attempt_number=1,
        )
    return BolnaFunctionResponse(status="logged", message="Thank you")


@router.post("/bolna", status_code=status.HTTP_200_OK)
async def bolna_call_completed(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Process only authenticated final Bolna execution events."""
    body = await _verified_json(request)
    call_id = str(
        body.get("execution_id")
        or body.get("call_id")
        or body.get("id")
        or (body.get("telephony_data") or {}).get("call_id", "")
    ).strip()
    status_raw = str(body.get("call_status") or body.get("status") or "").strip().lower()
    if not call_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Bolna execution_id is required")
    if status_raw and status_raw not in _FINAL_STATUSES:
        patient_id_raw = body.get("patient_id") or (
            body.get("user_data") or {}
        ).get("patient_id") if isinstance(body.get("user_data") or {}, Mapping) else body.get("patient_id")
        recipient_phone = body.get("recipient_phone_number") or body.get("recipient_phone") or body.get("phone")
        patient: Patient | None = None
        if patient_id_raw:
            try:
                patient = (
                    await db.execute(
                        select(Patient).where(Patient.id == uuid.UUID(str(patient_id_raw))).with_for_update()
                    )
                ).scalar_one_or_none()
            except ValueError:
                patient = None
        if patient is None and recipient_phone:
            patient = (
                await db.execute(
                    select(Patient).where(Patient.phone == _clean_phone(recipient_phone)).with_for_update()
                )
            ).scalar_one_or_none()
        if patient is not None:
            record = (
                await db.execute(select(CallRecord).where(CallRecord.provider_call_id == call_id))
            ).scalar_one_or_none()
            if record is None:
                record = CallRecord(
                    patient_id=patient.id,
                    provider_call_id=call_id,
                    status=_CALL_STATUS_MAP.get(status_raw, CallStatusEnum.initiated),
                    idempotency_key=f"bolna-call:{call_id}",
                )
                db.add(record)
            else:
                record.status = _CALL_STATUS_MAP.get(status_raw, record.status)
            await db.commit()
        return {"status": "accepted", "reason": "lifecycle_status", "execution_id": call_id}

    extracted = body.get("extracted_data") or body.get("user_data") or {}
    if not isinstance(extracted, Mapping):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid extracted_data")
    patient_id_raw = extracted.get("patient_id") or body.get("patient_id")
    medication_id_raw = extracted.get("medication_id") or body.get("medication_id")
    recipient_phone = body.get("recipient_phone_number") or body.get("recipient_phone") or body.get("phone")
    raw_outcome = extracted.get("outcome") or extracted.get("response")
    if status_raw in _NO_ANSWER_STATUSES:
        raw_outcome = "NO_ANSWER"
    if raw_outcome is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Completed event has no adherence outcome")
    outcome = _normalise_outcome(raw_outcome)
    payload_data: dict[str, object] = {
        "patient_id": str(patient_id_raw or ""),
        "medication_id": str(medication_id_raw) if medication_id_raw else None,
        "outcome": outcome,
        "side_effect_noted": outcome == "SIDE_EFFECT",
        "retry_required": outcome in {"MISSED", "NO_ANSWER", "CALLBACK_REQUESTED"},
        "notes": extracted.get("notes") or extracted.get("side_effect_notes") or extracted.get("response_text"),
        "side_effect_notes": extracted.get("side_effect_details") or extracted.get("side_effect_notes"),
        "time_slot": extracted.get("time_slot") or "morning",
        "bolna_call_id": call_id,
        "call_duration": body.get("call_duration") or body.get("duration"),
    }
    payload = BolnaWebhookPayload.model_validate(payload_data)
    _validate_payload_contract(payload, call_id)
    patient, medication = await _find_patient_and_medication(
        db,
        patient_id_raw=patient_id_raw,
        recipient_phone=recipient_phone,
        medication_id_raw=medication_id_raw,
    )
    log, alerts, duplicate = await _record_outcome(
        db,
        patient=patient,
        medication=medication,
        payload=payload,
        event_id=call_id,
        provider_status=status_raw or "completed",
    )
    if alerts:
        delivered, failed = await send_alert_notifications(
            request.app.state.twilio_service,
            alerts,
            patient,
            db=db,
        )
        logger.info("Post-call alerts delivered=%d failed=%d", delivered, failed)
    if not duplicate and payload._normalized_outcome in {"MISSED", "NO_ANSWER", "CALLBACK_REQUESTED"}:
        await request.app.state.scheduler_service.schedule_retry_call(
            patient_id=str(patient.id),
            medication_id=str(medication.id),
            log_id=str(log.id),
            attempt_number=1,
        )
    return {
        "status": "processed",
        "execution_id": call_id,
        "adherence_log_id": str(log.id),
        "alerts_created": len(alerts),
    }


@router.post("/bolna/function", response_model=BolnaFunctionResponse, status_code=status.HTTP_200_OK)
async def bolna_function_call(
    payload: BolnaWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BolnaFunctionResponse:
    """Process one authenticated real-time function/tool event."""
    body = await _verified_json(request)
    if not payload.bolna_call_id:
        provider_event_id = body.get("execution_id") or body.get("call_id") or body.get("id")
        if isinstance(provider_event_id, str):
            payload.bolna_call_id = provider_event_id
    return await _finish_function_event(payload, request, db)


@router.post("/bolna/follow-up", response_model=BolnaFunctionResponse, status_code=status.HTTP_200_OK)
async def bolna_follow_up(
    payload: BolnaWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> BolnaFunctionResponse:
    """Process a follow-up outcome and close the prior pending follow-up."""
    body = await _verified_json(request)
    if not payload.bolna_call_id:
        provider_event_id = body.get("execution_id") or body.get("call_id") or body.get("id")
        if isinstance(provider_event_id, str):
            payload.bolna_call_id = provider_event_id
    return await _finish_function_event(payload, request, db, mark_previous_follow_up=True)
