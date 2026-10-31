"""Dashboard endpoints — admin, family, alerts, refills, manual trigger."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Alert,
    AlertTypeEnum,
    CallSchedule,
    Medication,
    Patient,
    SeverityEnum,
)
from app.schemas import (
    AdminDashboardResponse,
    AlertCountsBySeverity,
    AlertResponse,
    DashboardSummary,
    FamilyDashboard,
    FamilyMedicationDetail,
    ManualCallResponse,
    PaginatedResponse,
    PaginationMeta,
    RefillInfo,
    TodayStatus,
    TrendPoint,
)
from app.services.adherence_engine import AdherenceEngine
from app.services.bolna_service import BolnaService
from app.utils.language import get_bolna_agent_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# =====================================================================
# 1. Admin / Pharmacy dashboard
# =====================================================================


@router.get(
    "/admin",
    response_model=AdminDashboardResponse,
    summary="Admin / pharmacy dashboard summary",
)
async def admin_dashboard(
    pharmacy_id: uuid.UUID | None = Query(None, description="Filter by pharmacy"),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate view: total patients, average adherence, alert counts,
    and per-patient summary sorted worst-adherence-first.
    """
    base = select(Patient)
    if pharmacy_id:
        base = base.where(Patient.pharmacy_id == pharmacy_id)

    all_patients = (await db.execute(base)).scalars().all()
    total = len(all_patients)
    active = [p for p in all_patients if p.is_active]
    active_count = len(active)

    engine = AdherenceEngine(db)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Per-patient summaries
    summaries: list[DashboardSummary] = []
    score_7d_acc = 0.0
    score_30d_acc = 0.0

    for patient in active:
        try:
            s7 = await engine.compute_adherence_score(patient.id, 7)
            s30 = await engine.compute_adherence_score(patient.id, 30)
            score_7d_acc += s7
            score_30d_acc += s30

            # Last call status
            last_log_q = (
                select(AdherenceLog)
                .where(AdherenceLog.patient_id == patient.id)
                .order_by(AdherenceLog.created_at.desc())
                .limit(1)
            )
            last_log = (await db.execute(last_log_q)).scalar_one_or_none()
            last_status = last_log.response.value if last_log else None

            # Alerts today
            alerts_today_q = (
                select(func.count())
                .select_from(Alert)
                .where(and_(Alert.patient_id == patient.id, Alert.created_at >= today_start))
            )
            at = (await db.execute(alerts_today_q)).scalar() or 0

            # Active medications
            med_q = select(Medication).where(
                and_(Medication.patient_id == patient.id, Medication.is_active.is_(True))
            )
            meds = (await db.execute(med_q)).scalars().all()

            # Refill-due names
            today_date = datetime.now(timezone.utc).date()
            refill_names: list[str] = []
            for m in meds:
                if m.prescription_start_date and m.prescribed_duration_days:
                    end = m.prescription_start_date + timedelta(days=m.prescribed_duration_days)
                    if end <= today_date + timedelta(days=5):
                        refill_names.append(m.name)

            summaries.append(
                DashboardSummary(
                    patient_id=patient.id,
                    patient_name=patient.name,
                    patient_phone=patient.phone,
                    adherence_score_7d=s7,
                    adherence_score_30d=s30,
                    last_call_status=last_status,
                    medications_count=len(meds),
                    alerts_today=at,
                    refill_due_medications=refill_names,
                )
            )
        except Exception:
            logger.exception("Dashboard summary failed for patient %s", patient.id)

    # Sort worst-first
    summaries.sort(key=lambda s: s.adherence_score_7d)

    avg_7d = round(score_7d_acc / active_count, 1) if active_count else 0.0
    avg_30d = round(score_30d_acc / active_count, 1) if active_count else 0.0

    # Alert counts by severity today
    alert_sev: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for sev in ("critical", "warning", "info"):
        q = (
            select(func.count())
            .select_from(Alert)
            .where(and_(Alert.created_at >= today_start, Alert.severity == sev))
        )
        if pharmacy_id:
            q = q.where(
                Alert.patient_id.in_(select(Patient.id).where(Patient.pharmacy_id == pharmacy_id))
            )
        alert_sev[sev] = (await db.execute(q)).scalar() or 0

    # Patients needing refill
    refill_count = sum(1 for s in summaries if s.refill_due_medications)

    return AdminDashboardResponse(
        total_patients=total,
        active_patients=active_count,
        avg_adherence_7d=avg_7d,
        avg_adherence_30d=avg_30d,
        alerts_today=AlertCountsBySeverity(**alert_sev),
        patients_needing_refill=refill_count,
        patients=summaries,
    )


# =====================================================================
# 2. Family dashboard
# =====================================================================


@router.get(
    "/family/{patient_id}",
    response_model=FamilyDashboard,
    summary="Family member dashboard for a patient",
)
async def family_dashboard(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Full family view: today's status, scores, trend, refill info,
    recent alerts, and next scheduled call.
    """
    patient = (
        await db.execute(
            select(Patient)
            .options(selectinload(Patient.medications))
            .where(Patient.id == patient_id)
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    engine = AdherenceEngine(db)
    score_7d = await engine.compute_adherence_score(patient_id, 7)
    score_30d = await engine.compute_adherence_score(patient_id, 30)

    # ---- Today's status ----
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_logs = (
        await db.execute(
            select(AdherenceLog).where(
                and_(AdherenceLog.patient_id == patient_id, AdherenceLog.created_at >= today_start)
            )
        )
    ).scalars().all()

    log_lookup: dict[tuple[uuid.UUID, str | None], str] = {}
    for log in today_logs:
        slot = log.scheduled_time_slot.value if log.scheduled_time_slot else None
        log_lookup[(log.medication_id, slot)] = log.response.value

    today_items: list[TodayStatus] = []
    for med in patient.medications:
        if not med.is_active:
            continue
        freq = med.frequency if isinstance(med.frequency, list) else []
        for slot in freq:
            raw = log_lookup.get((med.id, slot), "pending")
            if raw == "taken":
                disp = "taken"
            elif raw in ("not_taken", "no_answer", "stock_out"):
                disp = "not_taken"
            else:
                disp = "pending"
            today_items.append(
                TodayStatus(
                    time_slot=slot,
                    medication_name=med.name,
                    name=med.name,
                    status=disp,
                )
            )

    # ---- 14-day trend ----
    trend: list[TrendPoint] = []
    total_freq = sum(
        len(m.frequency) if isinstance(m.frequency, list) else 0
        for m in patient.medications if m.is_active
    )
    today_date = datetime.now(timezone.utc).date()
    for offset in range(13, -1, -1):
        d = today_date - timedelta(days=offset)
        ds = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        de = ds + timedelta(days=1)
        taken_q = (
            select(func.count()).select_from(AdherenceLog).where(
                and_(
                    AdherenceLog.patient_id == patient_id,
                    AdherenceLog.created_at >= ds,
                    AdherenceLog.created_at < de,
                    AdherenceLog.response == AdherenceResponseEnum.taken,
                )
            )
        )
        taken = (await db.execute(taken_q)).scalar() or 0
        sc = round((taken / total_freq) * 100, 1) if total_freq else 0.0
        trend.append(TrendPoint(date=d, score=sc, doses_taken=taken, doses_expected=total_freq))

    # ---- Recent alerts ----
    alerts = (
        await db.execute(
            select(Alert)
            .where(Alert.patient_id == patient_id)
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    # ---- Medications with refill data ----
    refill_preds = await engine.get_refill_predictions(patient_id)
    refill_map: dict[str, dict] = {r["medication_id"]: r for r in refill_preds}

    med_details: list[FamilyMedicationDetail] = []
    for med in patient.medications:
        if not med.is_active:
            continue
        refill = refill_map.get(str(med.id), {})
        med_details.append(
            FamilyMedicationDetail(
                name=med.name,
                dosage=med.dosage,
                meal_relation=med.meal_relation.value,
                frequency=med.frequency if isinstance(med.frequency, list) else [],
                pills_remaining=refill.get("pills_remaining"),
                days_until_refill=refill.get("days_remaining"),
            )
        )

    # ---- Next scheduled call ----
    now = datetime.now(timezone.utc)
    next_call_q = (
        select(CallSchedule.next_call_at)
        .where(
            and_(
                CallSchedule.patient_id == patient_id,
                CallSchedule.is_active.is_(True),
                CallSchedule.next_call_at > now,
            )
        )
        .order_by(CallSchedule.next_call_at.asc())
        .limit(1)
    )
    next_call = (await db.execute(next_call_q)).scalar_one_or_none()

    return FamilyDashboard(
        patient_name=patient.name,
        patient_language=patient.language.value,
        today=today_items,
        adherence_score_7d=score_7d,
        adherence_score_30d=score_30d,
        trend=trend,
        recent_alerts=[AlertResponse.model_validate(a) for a in alerts],
        medications=med_details,
        next_scheduled_call=next_call,
        family_contact_name=patient.family_contact_name,
    )


# =====================================================================
# 3. Alerts (list + mark read)
# =====================================================================


@router.get(
    "/alerts",
    response_model=PaginatedResponse[AlertResponse],
    summary="List all alerts with filters",
)
async def list_alerts(
    patient_id: uuid.UUID | None = Query(None),
    severity: str | None = Query(None, description="critical / warning / info"),
    is_read: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated alert list with optional filters."""
    base = select(Alert)
    if patient_id:
        base = base.where(Alert.patient_id == patient_id)
    if severity:
        base = base.where(Alert.severity == severity)
    if is_read is not None:
        base = base.where(Alert.is_read == is_read)

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * limit
    rows = (
        await db.execute(
            base.order_by(Alert.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    total_pages = max(1, -(-total // limit))
    return PaginatedResponse(
        data=[AlertResponse.model_validate(a) for a in rows],
        meta=PaginationMeta(page=page, limit=limit, total=total, total_pages=total_pages),
    )


@router.put(
    "/alerts/{alert_id}/read",
    response_model=AlertResponse,
    summary="Mark an alert as read",
)
async def mark_alert_read(
    alert_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Set is_read = True on the alert."""
    alert = (
        await db.execute(select(Alert).where(Alert.id == alert_id))
    ).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    await db.flush()
    await db.refresh(alert)
    return alert


# =====================================================================
# 4. Refills
# =====================================================================


@router.get(
    "/refills",
    response_model=list[RefillInfo],
    summary="Patients with upcoming refills",
)
async def list_refills(db: AsyncSession = Depends(get_db)):
    """Return medications that are running low or due for refill."""
    engine = AdherenceEngine(db)
    preds = await engine.get_refill_predictions()

    results: list[RefillInfo] = []
    # Cache patient lookups
    patient_cache: dict[str, Patient] = {}
    for r in preds:
        pid = r["patient_id"]
        if pid not in patient_cache:
            p = (
                await db.execute(select(Patient).where(Patient.id == uuid.UUID(pid)))
            ).scalar_one_or_none()
            if p:
                patient_cache[pid] = p
        p = patient_cache.get(pid)
        if not p:
            continue

        results.append(
            RefillInfo(
                patient_id=p.id,
                patient_name=p.name,
                patient_phone=p.phone,
                medication_name=r["medication_name"],
                pills_remaining=r["pills_remaining"],
                days_remaining=r["days_remaining"],
                refill_urgent=r["refill_urgent"],
            )
        )

    # Urgent first
    results.sort(key=lambda x: x.days_remaining)
    return results


# =====================================================================
# 5. Manual trigger call (for testing)
# =====================================================================


@router.post(
    "/trigger-call/{patient_id}",
    response_model=ManualCallResponse,
    summary="Manually trigger a call to a patient",
)
async def trigger_manual_call(
    patient_id: uuid.UUID,
    request: Request,
    medication_id: uuid.UUID | None = Query(None, description="Specific medication, or all if omitted"),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger one or more Bolna calls to a patient (for testing / ad-hoc)."""
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not patient.is_active:
        raise HTTPException(status_code=400, detail="Patient is inactive")

    agent_id = get_bolna_agent_id(patient.language.value)
    if not agent_id:
        raise HTTPException(
            status_code=400,
            detail=f"No Bolna agent configured for language: {patient.language.value}",
        )

    # Determine which medications to call for
    if medication_id:
        med = (
            await db.execute(
                select(Medication).where(
                    and_(Medication.id == medication_id, Medication.patient_id == patient_id)
                )
            )
        ).scalar_one_or_none()
        if not med:
            raise HTTPException(status_code=404, detail="Medication not found")
        meds = [med]
    else:
        meds_q = select(Medication).where(
            and_(Medication.patient_id == patient_id, Medication.is_active.is_(True))
        )
        meds = list((await db.execute(meds_q)).scalars().all())
        if not meds:
            raise HTTPException(status_code=400, detail="No active medications for this patient")

    bolna: BolnaService = request.app.state.bolna_service
    call_ids: list[str] = []

    for med in meds:
        try:
            user_data = {
                "patient_name": patient.name,
                "medication_name": med.name,
                "dosage": med.dosage,
                "meal_relation": med.meal_relation.value,
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
            cid = result.get("call_id")
            if cid:
                call_ids.append(cid)
        except Exception:
            logger.exception("Manual trigger failed for med %s", med.id)

    return ManualCallResponse(calls_triggered=len(call_ids), call_ids=call_ids)
