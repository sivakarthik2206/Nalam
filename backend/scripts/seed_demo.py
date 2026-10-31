"""
Idempotent demo seed script for Nalam.

Creates 2 demo patients with medications and 7 days of fake adherence history.
Safe to run multiple times — checks by phone before inserting.

Usage:
    cd backend
    python -m scripts.seed_demo
"""

import asyncio
import os
import random
import sys
import uuid
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
    Medication,
    Patient,
)
from app.config import settings

# Seed for reproducibility — gives ~75% adherence (5/7 days taken)
random.seed(42)

# Demo patients spec
_DEMO_PATIENTS = [
    {
        "name": "Meenakshi Sundaram",
        "phone": "+919876543001",
        "language": "tamil",
        "family_whatsapp": None,  # filled from env or default
        "family_whatsapp_default": "+919876543002",
        "family_contact_name": "Demo Family - Tamil",
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
    },
    {
        "name": "Savitri Devi",
        "phone": "+919876543003",
        "language": "hindi",
        "family_whatsapp": None,
        "family_whatsapp_default": "+919876543004",
        "family_contact_name": "Demo Family - Hindi",
        "medications": [
            {
                "name": "Metformin 500mg",
                "dosage": "1 tablet",
                "frequency": ["morning"],
                "meal_timing": "after_meal",
            },
            {
                "name": "Losartan 50mg",
                "dosage": "1 tablet",
                "frequency": ["morning", "night"],
                "meal_timing": "before_meal",
            },
        ],
    },
]

# Slot → (scheduled_hour, scheduled_minute)
_SLOT_SCHEDULE = {
    "morning": (9, 0),
    "afternoon": (14, 0),
    "evening": (18, 0),
    "night": (21, 0),
}

# 7-day adherence pattern with seed 42 — roughly 75% (~5/7 days)
# Generate reproducible booleans for 7 days per slot
def _adherence_pattern(num_days: int = 7) -> list[bool]:
    """Generate ~75% adherence pattern reproducibly."""
    return [random.random() < 0.75 for _ in range(num_days)]


async def main() -> None:
    print("Nalam demo seed starting...")

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        now = datetime.now(timezone.utc)
        demo_family_whatsapp = settings.DEMO_FAMILY_WHATSAPP

        for p_spec in _DEMO_PATIENTS:
            # Resolve family_whatsapp
            family_wa = demo_family_whatsapp or p_spec["family_whatsapp_default"]

            # Idempotent: check by phone
            existing = (
                await session.execute(
                    select(Patient).where(Patient.phone == p_spec["phone"])
                )
            ).scalar_one_or_none()

            if existing:
                patient = existing
                print(f"  Patient {p_spec['name']} already exists — reusing id={patient.id}")
            else:
                patient = Patient(
                    name=p_spec["name"],
                    phone=p_spec["phone"],
                    language=p_spec["language"],
                    family_whatsapp=family_wa,
                    family_contact_name=p_spec["family_contact_name"],
                    is_active=True,
                    created_at=now - timedelta(days=10),
                )
                session.add(patient)
                await session.flush()
                await session.refresh(patient)
                print(f"  Created patient: {p_spec['name']} (id={patient.id})")

            # Medications
            for med_spec in p_spec["medications"]:
                # Check if med already exists for this patient
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
                    print(f"    Created medication: {med_spec['name']} (id={med.id})")

                    # Auto-create call schedules for each slot
                    for slot_str in med_spec["frequency"]:
                        hour, minute = _SLOT_SCHEDULE.get(slot_str, (9, 0))
                        today_slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        if now < today_slot:
                            next_call = today_slot
                        else:
                            next_call = today_slot + timedelta(days=1)

                        sched = CallSchedule(
                            patient_id=patient.id,
                            medication_id=med.id,
                            time_slot=slot_str,
                            scheduled_hour=hour,
                            scheduled_minute=minute,
                            next_call_at=next_call,
                            is_active=True,
                        )
                        session.add(sched)

                # Generate 7 days of history (7 days ago to yesterday)
                pattern = _adherence_pattern(7)
                for day_offset in range(7, 0, -1):
                    log_date = now - timedelta(days=day_offset)
                    log_date = log_date.replace(hour=9, minute=0, second=0, microsecond=0)

                    for slot_str in med_spec["frequency"]:
                        hour, _ = _SLOT_SCHEDULE.get(slot_str, (9, 0))
                        slot_time = log_date.replace(hour=hour)

                        # Idempotent: check by patient+medication+date+slot
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
                            continue  # Already seeded

                        # Use pattern index (day_offset-1 reversed)
                        idx = 7 - day_offset
                        outcome = AdherenceResponseEnum.TAKEN if pattern[idx] else AdherenceResponseEnum.MISSED

                        log = AdherenceLog(
                            patient_id=patient.id,
                            medication_id=med.id,
                            scheduled_time_slot=slot_str if slot_str in ("morning", "afternoon", "evening", "night") else None,
                            call_time=slot_time,
                            outcome=outcome,
                            follow_up_needed=(outcome == AdherenceResponseEnum.MISSED),
                            follow_up_completed=(outcome == AdherenceResponseEnum.MISSED),  # historical
                            created_at=slot_time,
                        )
                        session.add(log)

        await session.commit()
        print("Demo seed complete!")


if __name__ == "__main__":
    asyncio.run(main())
