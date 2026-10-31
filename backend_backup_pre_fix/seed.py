"""
Seed script for Nalam database.
Populates Apollo Pharmacy - T. Nagar, demo patients (Hindi, Tamil, English),
medications, call schedules, adherence history logs, and initial alerts.
"""

import asyncio
from datetime import datetime, timezone, timedelta, time
import uuid

from app.database import async_session_factory, engine, Base
from app.models import Pharmacy, Patient, Medication, CallSchedule, AdherenceLog, Alert


async def seed():
    print("🌱 Initialising database schema and seeding Nalam demo data...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        # Check if already seeded
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
            family_contact_phone="+919876543211",
            is_active=True,
            created_at=now - timedelta(days=30),
        )
        session.add(p1)

        m1_1 = Medication(
            id=uuid.uuid4(),
            patient_id=p1_id,
            name="Metformin 500mg",
            dosage="1 tablet",
            meal_relation="after_meal",
            time_slot="morning",
            is_active=True,
            total_quantity=60,
            remaining_quantity=6,  # 3 days left -> triggers refill alert!
            refill_threshold_days=5,
        )
        m1_2 = Medication(
            id=uuid.uuid4(),
            patient_id=p1_id,
            name="Telmisartan 40mg",
            dosage="1 tablet",
            meal_relation="before_meal",
            time_slot="morning",
            is_active=True,
            total_quantity=30,
            remaining_quantity=22,
        )
        m1_3 = Medication(
            id=uuid.uuid4(),
            patient_id=p1_id,
            name="Atorvastatin 10mg",
            dosage="1 tablet",
            meal_relation="after_meal",
            time_slot="night",
            is_active=True,
            total_quantity=30,
            remaining_quantity=24,
        )
        session.add_all([m1_1, m1_2, m1_3])

        # Schedules for Lakshmi
        session.add(CallSchedule(patient_id=p1_id, medication_id=m1_1.id, scheduled_time=time(8, 30), time_slot="morning", is_active=True))
        session.add(CallSchedule(patient_id=p1_id, medication_id=m1_3.id, scheduled_time=time(20, 30), time_slot="night", is_active=True))

        # Adherence history for Lakshmi (past 7 days)
        for i in range(7, 0, -1):
            log_date = now - timedelta(days=i)
            # Missed once 2 days ago
            status = "missed" if i == 2 else "taken"
            session.add(AdherenceLog(
                patient_id=p1_id,
                medication_id=m1_1.id,
                call_id=f"bolna-lakshmi-{i}",
                status=status,
                patient_response="Haan beta, abhi li hai" if status == "taken" else "Nahi bhool gayi thi",
                call_duration=42,
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
            family_contact_phone="+919444123457",
            is_active=True,
            created_at=now - timedelta(days=45),
        )
        session.add(p2)

        m2_1 = Medication(
            id=uuid.uuid4(),
            patient_id=p2_id,
            name="Glimepiride 1mg",
            dosage="1 tablet",
            meal_relation="before_meal",
            time_slot="morning",
            is_active=True,
            total_quantity=30,
            remaining_quantity=18,
        )
        m2_2 = Medication(
            id=uuid.uuid4(),
            patient_id=p2_id,
            name="Amlodipine 5mg",
            dosage="1 tablet",
            meal_relation="after_meal",
            time_slot="morning",
            is_active=True,
            total_quantity=30,
            remaining_quantity=20,
        )
        session.add_all([m2_1, m2_2])

        session.add(CallSchedule(patient_id=p2_id, medication_id=m2_1.id, scheduled_time=time(8, 0), time_slot="morning", is_active=True))

        # Meenakshi has 100% adherence streak
        for i in range(7, 0, -1):
            session.add(AdherenceLog(
                patient_id=p2_id,
                medication_id=m2_1.id,
                call_id=f"bolna-meenakshi-{i}",
                status="taken",
                patient_response="Aama ma, kaalaila saapten.",
                call_duration=36,
                created_at=now - timedelta(days=i),
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
            family_contact_phone="+919888877778",
            is_active=True,
            created_at=now - timedelta(days=20),
        )
        session.add(p3)

        m3_1 = Medication(
            id=uuid.uuid4(),
            patient_id=p3_id,
            name="Ecosprin 75mg",
            dosage="1 tablet",
            meal_relation="after_meal",
            time_slot="afternoon",
            is_active=True,
            total_quantity=30,
            remaining_quantity=15,
        )
        m3_2 = Medication(
            id=uuid.uuid4(),
            patient_id=p3_id,
            name="Rosuvastatin 10mg",
            dosage="1 tablet",
            meal_relation="after_meal",
            time_slot="night",
            is_active=True,
            total_quantity=30,
            remaining_quantity=14,
        )
        session.add_all([m3_1, m3_2])

        session.add(CallSchedule(patient_id=p3_id, medication_id=m3_1.id, scheduled_time=time(13, 30), time_slot="afternoon", is_active=True))

        # Adherence history with side effect 2 days ago
        for i in range(7, 0, -1):
            if i == 2:
                session.add(AdherenceLog(
                    patient_id=p3_id,
                    medication_id=m3_1.id,
                    call_id=f"bolna-rajesh-{i}",
                    status="side_effect",
                    patient_response="I felt quite dizzy about an hour after taking the tablet.",
                    call_duration=55,
                    created_at=now - timedelta(days=i),
                ))
            else:
                session.add(AdherenceLog(
                    patient_id=p3_id,
                    medication_id=m3_1.id,
                    call_id=f"bolna-rajesh-{i}",
                    status="taken",
                    patient_response="Yes, I have taken it on time.",
                    call_duration=30,
                    created_at=now - timedelta(days=i),
                ))

        # -------------------------------------------------------------
        # Alerts
        # -------------------------------------------------------------
        # 1. Active side effect alert for Rajesh Kumar
        session.add(Alert(
            patient_id=p3_id,
            alert_type="side_effect",
            severity="high",
            message="Rajesh Kumar reported dizziness after taking Ecosprin 75mg. WhatsApp notification sent to Priya Kumar.",
            is_resolved=False,
            created_at=now - timedelta(days=2),
        ))

        # 2. Refill alert for Lakshmi Devi (Metformin low stock)
        session.add(Alert(
            patient_id=p1_id,
            alert_type="refill_due",
            severity="medium",
            message="Lakshmi Devi has only 6 tablets left of Metformin 500mg (~3 days remaining). Refill reminder sent.",
            is_resolved=False,
            created_at=now - timedelta(hours=6),
        ))

        await session.commit()
        print("✅ Database successfully seeded with demo pharmacy, patients, schedules, logs, and alerts!")


if __name__ == "__main__":
    asyncio.run(seed())
