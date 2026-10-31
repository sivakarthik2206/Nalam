"""Adherence data endpoints — scores, history, daily status, trend."""

import logging
import uuid
from datetime import date as date_type, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Medication,
    Patient,
)
from app.schemas import (
    AdherenceLogResponse,
    AdherenceScoreResponse,
    DailyAdherenceResponse,
    DailyDoseItem,
    TrendPoint,
)
from app.services.adherence_engine import AdherenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/adherence", tags=["Adherence"])


# =====================================================================
# Score
# =====================================================================


@router.get(
    "/{patient_id}/score",
    response_model=AdherenceScoreResponse,
    summary="Get adherence scores with streak data",
)
async def get_adherence_score(
    patient_id: uuid.UUID,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Return 7-day and 30-day scores, total expected / taken, and current / best streak."""
    # Verify patient
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    engine = AdherenceEngine(db)
    metrics_7d = await engine.compute_adherence_metrics(patient_id, 7)
    metrics_30d = await engine.compute_adherence_metrics(patient_id, 30)
    requested_metrics = await engine.compute_adherence_metrics(patient_id, days)

    # Streak calculation — walk backwards day by day
    streak_current, streak_best = await _compute_streaks(db, patient_id, meds)

    return AdherenceScoreResponse(
        patient_id=patient_id,
        score_7d=metrics_7d.score,
        score_30d=metrics_30d.score,
        total_doses_expected=requested_metrics.expected,
        total_doses_taken=requested_metrics.taken,
        streak_current=streak_current,
        streak_best=streak_best,
    )


async def _compute_streaks(
    db: AsyncSession,
    patient_id: uuid.UUID,
    meds: list[Medication],
) -> tuple[int, int]:
    """Compute current and best adherence streak (in days)."""
    if not meds:
        return 0, 0

    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if patient is None:
        return 0, 0
    try:
        patient_zone = ZoneInfo(patient.timezone_name)
    except (ZoneInfoNotFoundError, AttributeError):
        patient_zone = timezone.utc

    today = datetime.now(timezone.utc).astimezone(patient_zone).date()
    total_freq = sum(len(m.frequency) if isinstance(m.frequency, list) else 0 for m in meds)
    if total_freq == 0:
        return 0, 0

    current_streak = 0
    best_streak = 0
    running = 0
    current_active = True  # still building current streak

    # Look back up to 90 days
    for offset in range(90):
        d = today - timedelta(days=offset)
        day_start = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        taken_q = (
            select(func.count())
            .select_from(AdherenceLog)
            .where(
                and_(
                    AdherenceLog.patient_id == patient_id,
                    AdherenceLog.call_time >= day_start,
                    AdherenceLog.call_time < day_end,
                    AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                )
            )
        )
        taken = (await db.execute(taken_q)).scalar() or 0

        # A day counts as "fully adherent" if taken >= expected
        if taken >= total_freq:
            running += 1
        else:
            if current_active:
                current_streak = running
                current_active = False
            best_streak = max(best_streak, running)
            running = 0

    # Final accounting
    if current_active:
        current_streak = running
    best_streak = max(best_streak, running, current_streak)

    return current_streak, best_streak


# =====================================================================
# History
# =====================================================================


@router.get(
    "/{patient_id}/history",
    response_model=list[AdherenceLogResponse],
    summary="Get adherence log history",
)
async def get_adherence_history(
    patient_id: uuid.UUID,
    days: int = Query(7, ge=1, le=90),
    medication_id: uuid.UUID | None = Query(None, description="Filter by medication"),
    db: AsyncSession = Depends(get_db),
):
    """Return adherence logs ordered most-recent-first."""
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(AdherenceLog)
        .where(
            and_(
                AdherenceLog.patient_id == patient_id,
                AdherenceLog.call_time >= since,
            )
        )
        .order_by(AdherenceLog.created_at.desc())
    )
    if medication_id:
        medication_exists = (
            await db.execute(
                select(Medication.id).where(
                    Medication.id == medication_id,
                    Medication.patient_id == patient_id,
                )
            )
        ).scalar_one_or_none()
        if medication_exists is None:
            raise HTTPException(status_code=404, detail="Medication not found")
        stmt = stmt.where(AdherenceLog.medication_id == medication_id)

    logs = (await db.execute(stmt)).scalars().all()
    return logs


# =====================================================================
# Daily (today's dose-by-dose status)
# =====================================================================


@router.get(
    "/{patient_id}/daily",
    response_model=DailyAdherenceResponse,
    summary="Today's dose-by-dose status",
)
async def get_daily_adherence(
    patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Per-medication, per-slot status for today."""
    patient = (
        await db.execute(
            select(Patient)
            .options(selectinload(Patient.medications))
            .where(Patient.id == patient_id)
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    try:
        patient_zone = ZoneInfo(patient.timezone_name)
    except (ZoneInfoNotFoundError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Patient timezone is invalid") from exc
    local_today = datetime.now(timezone.utc).astimezone(patient_zone).date()
    today_start = datetime.combine(local_today, datetime.min.time(), tzinfo=patient_zone).astimezone(
        timezone.utc
    )
    today_end = today_start + timedelta(days=1)

    logs_q = select(AdherenceLog).where(
        and_(
            AdherenceLog.patient_id == patient_id,
            AdherenceLog.call_time >= today_start,
            AdherenceLog.call_time < today_end,
        )
    )
    today_logs = (await db.execute(logs_q)).scalars().all()

    # (medication_id, slot) → (outcome, logged_at)
    lookup: dict[tuple[uuid.UUID, str | None], tuple[str, datetime]] = {}
    for log in today_logs:
        slot_val = log.scheduled_time_slot.value if log.scheduled_time_slot else None
        lookup[(log.medication_id, slot_val)] = (log.outcome.value, log.call_time)

    items: list[DailyDoseItem] = []
    for med in patient.medications:
        if not med.is_active:
            continue
        freq = med.frequency if isinstance(med.frequency, list) else []
        for slot in freq:
            entry = lookup.get((med.id, slot))
            if entry:
                raw_status, logged_at = entry
                if raw_status == "TAKEN":
                    display = "taken"
                elif raw_status == "SIDE_EFFECT":
                    display = "side_effect"
                else:
                    display = "missed"
            else:
                display = "pending"
                logged_at = None

            items.append(
                DailyDoseItem(
                    name=med.name,
                    medication_name=med.name,
                    medication_id=med.id,
                    time_slot=slot,
                    meal_timing=med.meal_timing.value,
                    status=display,
                    logged_at=logged_at,
                )
            )

    return DailyAdherenceResponse(
        patient_name=patient.name,
        date=local_today,
        medications=items,
    )


# =====================================================================
# Trend (daily scores for charting)
# =====================================================================


@router.get(
    "/{patient_id}/trend",
    response_model=list[TrendPoint],
    summary="Daily adherence scores for charting",
)
async def get_adherence_trend(
    patient_id: uuid.UUID,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Return one data point per day with score, taken, and expected counts."""
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    meds = (
        await db.execute(
            select(Medication).where(
                and_(Medication.patient_id == patient_id, Medication.is_active.is_(True))
            )
        )
    ).scalars().all()

    total_freq = sum(len(m.frequency) if isinstance(m.frequency, list) else 0 for m in meds)

    try:
        patient_zone = ZoneInfo(patient.timezone_name)
    except (ZoneInfoNotFoundError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Patient timezone is invalid") from exc
    today = datetime.now(timezone.utc).astimezone(patient_zone).date()
    points: list[TrendPoint] = []

    for offset in range(days - 1, -1, -1):  # oldest first
        d = today - timedelta(days=offset)
        day_start = datetime.combine(d, datetime.min.time(), tzinfo=patient_zone).astimezone(
            timezone.utc
        )
        day_end = day_start + timedelta(days=1)

        taken_q = (
            select(func.count())
            .select_from(AdherenceLog)
            .where(
                and_(
                    AdherenceLog.patient_id == patient_id,
                    AdherenceLog.call_time >= day_start,
                    AdherenceLog.call_time < day_end,
                    AdherenceLog.outcome == AdherenceResponseEnum.TAKEN,
                )
            )
        )
        taken = (await db.execute(taken_q)).scalar() or 0
        expected = total_freq
        score = round((taken / expected) * 100, 1) if expected > 0 else None

        points.append(
            TrendPoint(date=d, score=score, doses_taken=taken, doses_expected=expected)
        )

    return points
