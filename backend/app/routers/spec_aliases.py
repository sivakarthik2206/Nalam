"""Spec alias routes — satisfy exact path requirements from the product spec.

All routes delegate to existing service logic; no business logic is duplicated here.
Registered with prefix /api/v1 in main.py.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    AdherenceLog,
    Alert,
    CallSchedule,
    ConsentStatusEnum,
    Medication,
    Patient,
)
from app.schemas import BolnaWebhookPayload, BolnaFunctionResponse
from app.services.adherence_engine import AdherenceEngine
from app.utils.language import get_bolna_agent_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Spec Aliases"])


# =====================================================================
# Route 1: POST /log-response
# Alias for the Bolna function call endpoint.
# =====================================================================


@router.post(
    "/log-response",
    response_model=BolnaFunctionResponse,
    summary="[Spec alias] Log a medication response (alias for /webhooks/bolna/function)",
)
async def log_response(
    payload: BolnaWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Spec alias — delegates to the Bolna function call handler."""
    from app.routers.webhooks import bolna_function_call
    return await bolna_function_call(payload=payload, request=request, db=db)


# =====================================================================
# Route 2: POST /trigger-calls
# =====================================================================


class TriggerCallsRequest(BaseModel):
    patient_ids: list[str] | None = None
    force: bool = False


class TriggerCallsResponse(BaseModel):
    triggered: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []


@router.post(
    "/trigger-calls",
    response_model=TriggerCallsResponse,
    summary="[Spec alias] Trigger calls for patients",
)
async def trigger_calls(
    request: Request,
    body: TriggerCallsRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Bolna calls for one or more patients.

    - If patient_ids omitted: operate on ALL active patients.
    - force=False: only trigger for patients whose CallSchedule.next_call_at <= now.
    - force=True: trigger for ALL specified/active patients regardless of schedule.
    """
    if body is None:
        body = TriggerCallsRequest()
    bolna = request.app.state.bolna_service
    now = datetime.now(timezone.utc)

    triggered: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    # Resolve patient list
    if body.patient_ids:
        try:
            patient_uuids = [uuid.UUID(pid) for pid in body.patient_ids]
        except ValueError as e:
            return TriggerCallsResponse(
                failed=[{"patient_id": str(body.patient_ids), "error": str(e)}]
            )
        patients_q = select(Patient).where(
            and_(
                Patient.id.in_(patient_uuids),
                Patient.is_active.is_(True),
                Patient.demo_only.is_(True),
                Patient.consent_status == ConsentStatusEnum.granted,
            )
        )
    else:
        patients_q = select(Patient).where(
            and_(
                Patient.is_active.is_(True),
                Patient.demo_only.is_(True),
                Patient.consent_status == ConsentStatusEnum.granted,
            )
        )

    patients = (await db.execute(patients_q)).scalars().all()

    for patient in patients:
        try:
            # Check schedule unless force=True
            if not body.force:
                schedule_q = select(CallSchedule).where(
                    and_(
                        CallSchedule.patient_id == patient.id,
                        CallSchedule.is_active.is_(True),
                        CallSchedule.next_call_at <= now,
                    )
                )
                due_schedules = (await db.execute(schedule_q)).scalars().all()
                if not due_schedules:
                    continue

            # Get active medications
            meds_q = select(Medication).where(
                and_(Medication.patient_id == patient.id, Medication.is_active.is_(True))
            )
            meds = (await db.execute(meds_q)).scalars().all()
            if not meds:
                failed.append({"patient_id": str(patient.id), "error": "no_active_medications"})
                continue

            agent_id = get_bolna_agent_id(patient.language.value)
            if not agent_id:
                failed.append({"patient_id": str(patient.id), "error": f"no_agent_for_{patient.language.value}"})
                continue

            # Trigger for first active medication (or all)
            for med in meds:
                user_data = {
                    "patient_name": patient.name,
                    "medication_name": med.name,
                    "dosage": med.dosage,
                    "meal_timing": med.meal_timing.value,
                    "language": patient.language.value,
                    "time_slot": "morning",
                    "patient_id": str(patient.id),
                    "medication_id": str(med.id),
                }
                result = await bolna.trigger_call(
                    agent_id=agent_id,
                    recipient_phone=patient.phone,
                    user_data=user_data,
                )
                call_id = result.get("call_id", "")
                if result.get("error"):
                    failed.append({
                        "patient_id": str(patient.id),
                        "error": result.get("detail", "call_failed"),
                    })
                else:
                    triggered.append({"patient_id": str(patient.id), "call_id": str(call_id)})

        except Exception as exc:
            logger.exception("trigger-calls failed for patient %s", patient.id)
            failed.append({"patient_id": str(patient.id), "error": "call_trigger_failed"})

    return TriggerCallsResponse(triggered=triggered, failed=failed)


# =====================================================================
# Route 3: GET /patient-summary
# =====================================================================


@router.get(
    "/patient-summary",
    summary="[Spec alias] Get patient summary (single or all)",
)
async def patient_summary(
    patient_id: uuid.UUID | None = Query(None, description="Omit for all active patients"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns patient summary with adherence scores, medications, alerts, refill info.

    - patient_id provided: return single patient summary.
    - patient_id omitted: return list of all active patients.
    """
    engine = AdherenceEngine(db)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async def _build_summary(patient: Patient) -> dict[str, object]:
        score_7d = await engine.compute_adherence_score(patient.id, 7)

        # Today's call status
        last_log_q = (
            select(AdherenceLog)
            .where(
                and_(
                    AdherenceLog.patient_id == patient.id,
                    AdherenceLog.created_at >= today_start,
                )
            )
            .order_by(AdherenceLog.created_at.desc())
            .limit(1)
        )
        last_log = (await db.execute(last_log_q)).scalar_one_or_none()
        today_call_status = last_log.outcome.value if last_log else "pending"

        # Active medications
        meds_q = select(Medication).where(
            and_(Medication.patient_id == patient.id, Medication.is_active.is_(True))
        )
        meds = (await db.execute(meds_q)).scalars().all()

        # Last confirmed time per medication
        med_list: list[dict[str, object]] = []
        for med in meds:
            last_taken_q = (
                select(AdherenceLog)
                .where(
                    and_(
                        AdherenceLog.medication_id == med.id,
                        AdherenceLog.outcome == "TAKEN",
                    )
                )
                .order_by(AdherenceLog.created_at.desc())
                .limit(1)
            )
            last_taken = (await db.execute(last_taken_q)).scalar_one_or_none()
            med_list.append({
                "name": med.name,
                "dosage": med.dosage,
                "meal_timing": med.meal_timing.value,
                "frequency": med.frequency if isinstance(med.frequency, list) else [],
                "last_confirmed_time": last_taken.call_time.isoformat() if last_taken else None,
            })

        # Recent alerts (last 5)
        alerts_q = (
            select(Alert)
            .where(Alert.patient_id == patient.id)
            .order_by(Alert.created_at.desc())
            .limit(5)
        )
        recent_alerts = (await db.execute(alerts_q)).scalars().all()

        # Refill due
        refill_preds = await engine.get_refill_predictions(patient.id)
        refill_due = [
            {"medication_name": r["medication_name"], "days_remaining": r["days_remaining"]}
            for r in refill_preds
            if r["refill_urgent"]
        ]

        return {
            "patient_id": str(patient.id),
            "patient_name": patient.name,
            "patient_language": patient.language.value,
            "today_call_status": today_call_status,
            "adherence_score_7d": score_7d,
            "medications": med_list,
            "recent_alerts": [
                {
                    "id": str(a.id),
                    "alert_type": a.alert_type.value,
                    "severity": a.severity.value,
                    "message": a.message,
                    "created_at": a.created_at.isoformat(),
                }
                for a in recent_alerts
            ],
            "refill_due": refill_due,
        }

    if patient_id:
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if not patient:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Patient not found")
        return await _build_summary(patient)
    else:
        patients = (await db.execute(
            select(Patient).where(Patient.is_active.is_(True))
        )).scalars().all()
        results = []
        for p in patients:
            try:
                results.append(await _build_summary(p))
            except Exception:
                logger.exception("patient-summary failed for patient %s", p.id)
        return results


# =====================================================================
# Route 4: POST /daily-summary
# =====================================================================


@router.post(
    "/daily-summary",
    summary="[Spec alias] Trigger WhatsApp daily summary",
)
async def daily_summary(
    request: Request,
    patient_id: uuid.UUID | None = Query(None, description="Omit for all active patients"),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger immediate WhatsApp daily summary.

    - patient_id provided: send for one patient.
    - patient_id omitted: send for all active patients with family_whatsapp set.
    """
    from app.alerts import send_daily_summary as _send_daily_summary
    from app.config import settings

    twilio = request.app.state.twilio_service
    app_base_url = settings.APP_BASE_URL

    sent: list[str] = []
    failed: list[str] = []

    async def _send_for_patient(patient: Patient) -> None:
        if not patient.family_whatsapp:
            failed.append(patient.name)
            return
        success = await _send_daily_summary(db, twilio, patient, app_base_url)
        if success:
            sent.append(patient.name)
        else:
            failed.append(patient.name)

    if patient_id:
        patient = (
            await db.execute(select(Patient).where(Patient.id == patient_id))
        ).scalar_one_or_none()
        if not patient:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Patient not found")
        await _send_for_patient(patient)
    else:
        patients_q = select(Patient).where(
            and_(
                Patient.is_active.is_(True),
                Patient.family_whatsapp.isnot(None),
            )
        )
        patients = (await db.execute(patients_q)).scalars().all()
        for p in patients:
            try:
                await _send_for_patient(p)
            except Exception:
                logger.exception("daily-summary failed for patient %s", p.name)
                failed.append(p.name)

    return {"sent": sent, "failed": failed}
