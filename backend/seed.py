"""
Seed script for Nalam database.
Populates Apollo Pharmacy - T. Nagar, demo patients (Hindi, Tamil, English),
medications, call schedules, adherence history logs, and initial alerts.

NOTE: This script uses a simplified model that maps to the current schema.
For a fully idempotent demo seed, use scripts/seed_demo.py instead.
"""

import asyncio
from datetime import datetime, timezone, timedelta
import uuid

from app.database import async_session_factory, engine
from app.models import Base, Pharmacy, Patient, Medication, CallSchedule, AdherenceLog, Alert, AdherenceResponseEnum, AlertTypeEnum, SeverityEnum, ChannelEnum


async def seed():
    print("Initialising database schema and seeding Nalam demo data...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        pharmacy_id = uuid.uuid4()
        pharmacy = Pharmacy(
            id=pharmacy_id,
            name="Apollo Pharmacy - T. Nagar",
            phone="+914428150000",
            address="14 Pondy Bazaar, T. Nagar, Chennai - 600017",
            email="tnagar@apollopharmacy.org",
        )
        session.add(pharmacy)

        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # Patient 1: Lakshmi Devi (Hindi)
        # -------------------------------------------------------------
        p1_id = uuid.uuid4()
        p1 = Patient(
            id=p1_id,
            pharmacy_id=pharmacy_id,
            name="Lakshmi Devi",
            phone="+919876543210",
            language="hindi",
            family_contact_name="Ramesh Sharma (Son)",
            family_whatsapp="+919876543211",
            is_active=True,
            created_at=now - timedelta(days=30),
        )
        session.add(p1)

        m1_1_id = uuid.uuid4()
        m1_1 = Medication(
            id=m1_1_id,
            patient_id=p1_id,
            name="Metformin 500mg",
            dosage="1 tablet",
            frequency=["morning", "evening"],
            meal_timing="after_meal",
            is_active=True,
            pills_dispensed=60,
            prescription_duration_days=30,
        )
        m1_2 = Medication(
            id=uuid.uuid4(),
            patient_id=p1_id,
            name="Telmisartan 40mg",
            dosage="1 tablet",
            frequency=["morning"],
            meal_timing="before_meal",
            is_active=True,
            pills_dispensed=30,
        )
        m1_3_id = uuid.uuid4()
        m1_3 = Medication(
            id=m1_3_id,
            patient_id=p1_id,
            name="Atorvastatin 10mg",
            dosage="1 tablet",
            frequency=["night"],
            meal_timing="after_meal",
            is_active=True,
            pills_dispensed=30,
        )
        session.add_all([m1_1, m1_2, m1_3])

        # Schedules for Lakshmi
        session.add(CallSchedule(
            patient_id=p1_id, medication_id=m1_1_id,
            scheduled_hour=8, scheduled_minute=30, time_slot="morning", is_active=True
        ))
        session.add(CallSchedule(
            patient_id=p1_id, medication_id=m1_3_id,
            scheduled_hour=20, scheduled_minute=30, time_slot="night", is_active=True
        ))

        # Adherence history for Lakshmi (past 7 days)
        for i in range(7, 0, -1):
            log_date = now - timedelta(days=i)
            outcome = AdherenceResponseEnum.MISSED if i == 2 else AdherenceResponseEnum.TAKEN
            session.add(AdherenceLog(
                patient_id=p1_id,
                medication_id=m1_1_id,
                bolna_call_id=f"bolna-lakshmi-{i}",
                outcome=outcome,
                call_time=log_date,
                follow_up_needed=(outcome == AdherenceResponseEnum.MISSED),
                created_at=log_date,
            ))

        # -------------------------------------------------------------
        # Patient 2: Meenakshi Ammal (Tamil)
        # -------------------------------------------------------------
        p2_id = uuid.uuid4()
        p2 = Patient(
            id=p2_id,
            pharmacy_id=pharmacy_id,
            name="Meenakshi Ammal",
            phone="+919444123456",
            language="tamil",
            family_contact_name="Karthik Subramanian (Son)",
            family_whatsapp="+919444123457",
            is_active=True,
            created_at=now - timedelta(days=45),
        )
        session.add(p2)

        m2_1_id = uuid.uuid4()
        m2_1 = Medication(
            id=m2_1_id,
            patient_id=p2_id,
            name="Glimepiride 1mg",
            dosage="1 tablet",
            frequency=["morning"],
            meal_timing="before_meal",
            is_active=True,
            pills_dispensed=30,
        )
        m2_2 = Medication(
            id=uuid.uuid4(),
            patient_id=p2_id,
            name="Amlodipine 5mg",
            dosage="1 tablet",
            frequency=["morning"],
            meal_timing="after_meal",
            is_active=True,
            pills_dispensed=30,
        )
        session.add_all([m2_1, m2_2])

        session.add(CallSchedule(
            patient_id=p2_id, medication_id=m2_1_id,
            scheduled_hour=8, scheduled_minute=0, time_slot="morning", is_active=True
        ))

        for i in range(7, 0, -1):
            log_date = now - timedelta(days=i)
            session.add(AdherenceLog(
                patient_id=p2_id,
                medication_id=m2_1_id,
                bolna_call_id=f"bolna-meenakshi-{i}",
                outcome=AdherenceResponseEnum.TAKEN,
                call_time=log_date,
                created_at=log_date,
            ))

        # -------------------------------------------------------------
        # Patient 3: Rajesh Kumar (English)
        # -------------------------------------------------------------
        p3_id = uuid.uuid4()
        p3 = Patient(
            id=p3_id,
            pharmacy_id=pharmacy_id,
            name="Rajesh Kumar",
            phone="+919888877777",
            language="english",
            family_contact_name="Priya Kumar (Daughter)",
            family_whatsapp="+919888877778",
            is_active=True,
            created_at=now - timedelta(days=20),
        )
        session.add(p3)

        m3_1_id = uuid.uuid4()
        m3_1 = Medication(
            id=m3_1_id,
            patient_id=p3_id,
            name="Ecosprin 75mg",
            dosage="1 tablet",
            frequency=["afternoon"],
            meal_timing="after_meal",
            is_active=True,
            pills_dispensed=30,
        )
        m3_2 = Medication(
            id=uuid.uuid4(),
            patient_id=p3_id,
            name="Rosuvastatin 10mg",
            dosage="1 tablet",
            frequency=["night"],
            meal_timing="after_meal",
            is_active=True,
            pills_dispensed=30,
        )
        session.add_all([m3_1, m3_2])

        session.add(CallSchedule(
            patient_id=p3_id, medication_id=m3_1_id,
            scheduled_hour=13, scheduled_minute=30, time_slot="afternoon", is_active=True
        ))

        for i in range(7, 0, -1):
            log_date = now - timedelta(days=i)
            if i == 2:
                session.add(AdherenceLog(
                    patient_id=p3_id,
                    medication_id=m3_1_id,
                    bolna_call_id=f"bolna-rajesh-{i}",
                    outcome=AdherenceResponseEnum.SIDE_EFFECT,
                    call_time=log_date,
                    side_effect_details="I felt quite dizzy about an hour after taking the tablet.",
                    notes="I felt quite dizzy about an hour after taking the tablet.",
                    created_at=log_date,
                ))
            else:
                session.add(AdherenceLog(
                    patient_id=p3_id,
                    medication_id=m3_1_id,
                    bolna_call_id=f"bolna-rajesh-{i}",
                    outcome=AdherenceResponseEnum.TAKEN,
                    call_time=log_date,
                    created_at=log_date,
                ))

        # -------------------------------------------------------------
        # Alerts
        # -------------------------------------------------------------
        session.add(Alert(
            patient_id=p3_id,
            alert_type=AlertTypeEnum.side_effect,
            severity=SeverityEnum.critical,
            message="Rajesh Kumar reported dizziness after taking Ecosprin 75mg.",
            is_read=False,
            channel=ChannelEnum.whatsapp,
            created_at=now - timedelta(days=2),
        ))

        session.add(Alert(
            patient_id=p1_id,
            alert_type=AlertTypeEnum.refill_due,
            severity=SeverityEnum.warning,
            message="Lakshmi Devi has only 6 tablets left of Metformin 500mg (~3 days remaining). Refill reminder sent.",
            is_read=False,
            channel=ChannelEnum.dashboard,
            created_at=now - timedelta(hours=6),
        ))

        await session.commit()
        print("Database successfully seeded with demo pharmacy, patients, schedules, logs, and alerts!")


if __name__ == "__main__":
    asyncio.run(seed())
