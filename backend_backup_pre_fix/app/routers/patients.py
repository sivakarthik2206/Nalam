"""Patient & medication CRUD endpoints."""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Alert,
    CallSchedule,
    Medication,
    Patient,
    TimeSlotEnum,
)
from app.schemas import (
    AlertResponse,
    MedicationCreate,
    MedicationResponse,
    MedicationUpdate,
    PaginatedResponse,
    PaginationMeta,
    PatientCreate,
    PatientResponse,
    PatientUpdate,
    PatientWithMedications,
)
from app.services.adherence_engine import AdherenceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients", tags=["Patients"])

_PHONE_RE = re.compile(r"^\+91\d{10}$")

# Slot → (hour, minute) mapping for auto-created CallSchedules
_SLOT_SCHEDULE: dict[str, tuple[int, int]] = {
    "morning": (9, 0),
    "afternoon": (14, 0),
    "evening": (18, 0),
    "night": (21, 0),
}

IST = timezone(timedelta(hours=5, minutes=30))


# ========================= Patient CRUD =========================


@router.post(
    "/",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new patient",
)
async def create_patient(payload: PatientCreate, db: AsyncSession = Depends(get_db)):
    """Register a new patient. Phone must match +91XXXXXXXXXX."""
    # Phone uniqueness check
    existing = (
        await db.execute(select(Patient).where(Patient.phone == payload.phone))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Patient with phone {payload.phone} already exists",
        )

    patient = Patient(**payload.model_dump())
    db.add(patient)
    await db.flush()
    await db.refresh(patient)
    logger.info("Patient created id=%s name=%s", patient.id, patient.name)
    return patient


@router.get(
    "/",
    response_model=PaginatedResponse[PatientResponse],
    summary="List all active patients",
)
async def list_patients(
    pharmacy_id: uuid.UUID | None = Query(None, description="Filter by pharmacy"),
    language: str | None = Query(None, description="Filter by language (hindi/tamil/english)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated list of active patients with optional filters."""
    base = select(Patient).where(Patient.is_active.is_(True))
    if pharmacy_id:
        base = base.where(Patient.pharmacy_id == pharmacy_id)
    if language:
        base = base.where(Patient.language == language)

    # Total count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated rows
    offset = (page - 1) * limit
    rows_q = base.order_by(Patient.created_at.desc()).offset(offset).limit(limit)
    patients = (await db.execute(rows_q)).scalars().all()

    total_pages = max(1, -(-total // limit))  # ceil division
    return PaginatedResponse(
        data=[PatientResponse.model_validate(p) for p in patients],
        meta=PaginationMeta(page=page, limit=limit, total=total, total_pages=total_pages),
    )


@router.get(
    "/{patient_id}",
    response_model=PatientWithMedications,
    summary="Get patient with medications, scores, and recent alerts",
)
async def get_patient(patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Full patient view including medications, adherence scores, and last 10 alerts."""
    stmt = (
        select(Patient)
        .options(selectinload(Patient.medications))
        .where(Patient.id == patient_id)
    )
    patient = (await db.execute(stmt)).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    engine = AdherenceEngine(db)
    score_7d = await engine.compute_adherence_score(patient_id, days=7)
    score_30d = await engine.compute_adherence_score(patient_id, days=30)

    # Recent alerts
    alerts_q = (
        select(Alert)
        .where(Alert.patient_id == patient_id)
        .order_by(Alert.created_at.desc())
        .limit(10)
    )
    alerts = (await db.execute(alerts_q)).scalars().all()

    resp = PatientWithMedications.model_validate(patient)
    resp.adherence_score_7d = score_7d
    resp.adherence_score_30d = score_30d
    resp.recent_alerts = [AlertResponse.model_validate(a) for a in alerts]
    return resp


@router.put(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient details (partial)",
)
async def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partial update — only provided fields are changed."""
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    for key, value in update_data.items():
        setattr(patient, key, value)

    await db.flush()
    await db.refresh(patient)
    logger.info("Patient updated id=%s fields=%s", patient_id, list(update_data.keys()))
    return patient


@router.delete(
    "/{patient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a patient",
)
async def deactivate_patient(
    patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Set is_active=False on the patient."""
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.is_active = False
    await db.flush()
    logger.info("Patient deactivated id=%s", patient_id)
    return None


# ========================= Medication CRUD =========================


@router.post(
    "/{patient_id}/medications",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add medication and auto-create call schedules",
)
async def add_medication(
    patient_id: uuid.UUID,
    payload: MedicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a medication for the patient.
    Automatically creates a CallSchedule for each entry in ``frequency``.
    """
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    med = Medication(patient_id=patient_id, **payload.model_dump())
    db.add(med)
    await db.flush()
    await db.refresh(med)

    # Auto-create CallSchedule entries
    now_ist = datetime.now(IST)
    for slot_str in payload.frequency:
        hour_min = _SLOT_SCHEDULE.get(slot_str)
        if not hour_min:
            logger.warning("Unknown frequency slot '%s', skipping CallSchedule", slot_str)
            continue

        hour, minute = hour_min

        # Determine next_call_at
        today_slot = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now_ist < today_slot:
            next_call = today_slot.astimezone(timezone.utc)
        else:
            next_call = (today_slot + timedelta(days=1)).astimezone(timezone.utc)

        try:
            slot_enum = TimeSlotEnum(slot_str)
        except ValueError:
            slot_enum = None

        schedule = CallSchedule(
            patient_id=patient_id,
            medication_id=med.id,
            time_slot=slot_enum,
            scheduled_hour=hour,
            scheduled_minute=minute,
            next_call_at=next_call,
        )
        db.add(schedule)

    await db.flush()
    logger.info(
        "Medication created id=%s for patient=%s, %d schedules auto-created",
        med.id, patient_id, len(payload.frequency),
    )
    return med


@router.get(
    "/{patient_id}/medications",
    response_model=list[MedicationResponse],
    summary="List patient's active medications",
)
async def list_medications(
    patient_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Return all active medications for a patient."""
    # Verify patient
    patient = (
        await db.execute(select(Patient).where(Patient.id == patient_id))
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    stmt = select(Medication).where(
        and_(Medication.patient_id == patient_id, Medication.is_active.is_(True))
    )
    meds = (await db.execute(stmt)).scalars().all()
    return meds


@router.put(
    "/{patient_id}/medications/{medication_id}",
    response_model=MedicationResponse,
    summary="Update a medication",
)
async def update_medication(
    patient_id: uuid.UUID,
    medication_id: uuid.UUID,
    payload: MedicationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Partial update on medication fields."""
    med = (
        await db.execute(
            select(Medication).where(
                and_(Medication.id == medication_id, Medication.patient_id == patient_id)
            )
        )
    ).scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields to update")

    for key, value in update_data.items():
        setattr(med, key, value)

    await db.flush()
    await db.refresh(med)
    logger.info("Medication updated id=%s fields=%s", medication_id, list(update_data.keys()))
    return med


@router.delete(
    "/{patient_id}/medications/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete medication and deactivate its schedules",
)
async def deactivate_medication(
    patient_id: uuid.UUID,
    medication_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Set is_active=False on the medication and all its CallSchedules."""
    med = (
        await db.execute(
            select(Medication).where(
                and_(Medication.id == medication_id, Medication.patient_id == patient_id)
            )
        )
    ).scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    med.is_active = False

    # Deactivate linked schedules
    sched_q = select(CallSchedule).where(
        and_(
            CallSchedule.medication_id == medication_id,
            CallSchedule.patient_id == patient_id,
        )
    )
    schedules = (await db.execute(sched_q)).scalars().all()
    for s in schedules:
        s.is_active = False

    await db.flush()
    logger.info(
        "Medication %s deactivated, %d schedules deactivated", medication_id, len(schedules)
    )
    return None
