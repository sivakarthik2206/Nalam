"""
Idempotent demo seed script for Nalam (Tamil-only).

Creates one Tamil demo patient with 2 medications and 7 days of fake adherence
history (~75% adherence). Safe to run multiple times — checks by phone before
inserting.

Usage:
    cd backend
    python -m scripts.seed_demo
"""

import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root is on path when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_, select

from app.database import async_session_factory, engine
from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    Base,
    CallSchedule,
    ConsentStatusEnum,
    Medication,
    Patient,
)
from app.config import settings

# Seed for reproducibility — seed 42 gives ~75% adherence (5-6/7 days taken)
random.seed(42)

# Single Tamil demo patient — the only language Nalam supports
_DEMO_PATIENT = {
    "name": "Meenakshi Sundaram",
    "phone": "+919876543001",
    "language": "tamil",
    "family_contact_name": "Demo Family",
    "medications": [
        {
            "name": "Metformin 500mg",
            "dosage": "1 tablet",
            "frequency": ["morning", "evening"],
            "meal_timing": "after_meal",
        },
        {
            "name": "Amlodipine 5mg",
            "dosage": "1 tablet",
            "frequency": ["morning"],
            "meal_timing": "before_meal",
        },
    ],
}

# Slot → (scheduled_hour, scheduled_minute)
_SLOT_SCHEDULE = {
    "morning": (9, 0),
    "afternoon": (14, 0),
    "evening": (18, 0),
    "night": (21, 0),
}


def _adherence_pattern(num_days: int = 7) -> list[bool]:
    """Generate ~75% adherence pattern reproducibly (seed fixed at module level)."""
    return [random.random() < 0.75 for _ in range(num_days)]


async def main() -> None:
    print("Nalam demo seed starting (Tamil-only)...")

    # Ensure tables exist — safe for local dev; use alembic on production
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)

        # family_whatsapp: prefer DEMO_FAMILY_WHATSAPP env var, fall back to
        # a placeholder so the seed still succeeds without it configured
        family_wa = settings.DEMO_FAMILY_WHATSAPP or "+919876543002"

        p_spec = _DEMO_PATIENT

        existing = (
            await session.execute(
                select(Patient).where(Patient.phone == p_spec["phone"])
            )
        ).scalar_one_or_none()

        if existing:
            patient = existing
            # Ensure existing patient has correct demo flags set
            if not patient.demo_only:
                patient.demo_only = True
            if patient.consent_status != ConsentStatusEnum.granted:
                patient.consent_status = ConsentStatusEnum.granted
                patient.consent_at = patient.consent_at or (now - timedelta(days=10))
            print(f"  Patient {p_spec['name']} already exists — reusing id={patient.id}")
        else:
            patient = Patient(
                name=p_spec["name"],
                phone=p_spec["phone"],
                language=p_spec["language"],
                family_whatsapp=family_wa,
                family_contact_name=p_spec["family_contact_name"],
                is_active=True,
                demo_only=True,
                consent_status=ConsentStatusEnum.granted,
                consent_at=now - timedelta(days=10),
                created_at=now - timedelta(days=10),
            )
            session.add(patient)
            await session.flush()
            await session.refresh(patient)
            print(f"  Created patient: {p_spec['name']} (id={patient.id})")

        med_count = 0
        log_count = 0

        for med_spec in p_spec["medications"]:
            existing_med = (
                await session.execute(
                    select(Medication).where(
                        and_(
                            Medication.patient_id == patient.id,
                            Medication.name == med_spec["name"],
                            Medication.is_active.is_(True),
                        )
                    )
                )
            ).scalar_one_or_none()

            if existing_med:
                med = existing_med
                print(f"    Medication {med_spec['name']} already exists — reusing")
            else:
                med = Medication(
                    patient_id=patient.id,
                    name=med_spec["name"],
                    dosage=med_spec["dosage"],
                    frequency=med_spec["frequency"],
                    meal_timing=med_spec["meal_timing"],
                    pills_dispensed=60,
                    is_active=True,
                )
                session.add(med)
                await session.flush()
                await session.refresh(med)
                med_count += 1
                print(f"    Created medication: {med_spec['name']} (id={med.id})")

                for slot_str in med_spec["frequency"]:
                    hour, minute = _SLOT_SCHEDULE.get(slot_str, (9, 0))
                    today_slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    next_call = today_slot if now < today_slot else today_slot + timedelta(days=1)
                    session.add(CallSchedule(
                        patient_id=patient.id,
                        medication_id=med.id,
                        time_slot=slot_str,
                        scheduled_hour=hour,
                        scheduled_minute=minute,
                        next_call_at=next_call,
                        is_active=True,
                    ))

            # Generate 7 days of history (7 days ago to yesterday)
            pattern = _adherence_pattern(7)
            for day_offset in range(7, 0, -1):
                log_date = now - timedelta(days=day_offset)
                for slot_str in med_spec["frequency"]:
                    hour, _ = _SLOT_SCHEDULE.get(slot_str, (9, 0))
                    slot_time = log_date.replace(hour=hour, minute=0, second=0, microsecond=0)
                    day_start = slot_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = day_start + timedelta(days=1)

                    existing_log = (
                        await session.execute(
                            select(AdherenceLog).where(
                                and_(
                                    AdherenceLog.patient_id == patient.id,
                                    AdherenceLog.medication_id == med.id,
                                    AdherenceLog.created_at >= day_start,
                                    AdherenceLog.created_at < day_end,
                                )
                            )
                        )
                    ).scalar_one_or_none()

                    if existing_log:
                        continue

                    idx = 7 - day_offset
                    outcome = (
                        AdherenceResponseEnum.TAKEN if pattern[idx]
                        else AdherenceResponseEnum.MISSED
                    )
                    session.add(AdherenceLog(
                        patient_id=patient.id,
                        medication_id=med.id,
                        scheduled_time_slot=slot_str,
                        call_time=slot_time,
                        outcome=outcome,
                        follow_up_needed=(outcome == AdherenceResponseEnum.MISSED),
                        follow_up_completed=(outcome == AdherenceResponseEnum.MISSED),
                        created_at=slot_time,
                    ))
                    log_count += 1

        await session.commit()

    print(
        f"\nDemo seed complete!\n"
        f"  patients : 1\n"
        f"  medications created : {med_count}\n"
        f"  adherence logs created : {log_count}\n"
        f"  patient id: {patient.id}\n"
        f"  phone    : {patient.phone}\n"
        f"  family WA: {family_wa}\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
