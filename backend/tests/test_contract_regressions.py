"""Regression contracts for safety-critical Nalam behavior.

These tests deliberately exercise business rules and persistence contracts rather
than checking only that routes are registered or that a response is truthy.
External providers are not contacted by this module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.alerts import evaluate_escalations
from app.models import (
    AdherenceLog,
    AdherenceResponseEnum,
    AlertTypeEnum,
    Base,
    LanguageEnum,
    MealTimingEnum,
    Medication,
    Patient,
)
from app.routers.webhooks import _validate_payload_contract
from app.schemas import BolnaWebhookPayload, PatientCreate
from app.services.adherence_engine import AdherenceEngine


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide an isolated SQLite database for deterministic contract tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


def _patient() -> Patient:
    return Patient(
        id=uuid.uuid4(),
        name="Meenakshi",
        phone="+919876543001",
        language=LanguageEnum.tamil,
        family_whatsapp="+919876543002",
    )


def _medication(patient_id: uuid.UUID) -> Medication:
    return Medication(
        id=uuid.uuid4(),
        patient_id=patient_id,
        name="Metformin 500mg",
        dosage="1 tablet",
        frequency=["morning", "evening"],
        meal_timing=MealTimingEnum.after_meal,
    )


def _log(
    patient_id: uuid.UUID,
    medication_id: uuid.UUID,
    outcome: AdherenceResponseEnum,
    created_at: datetime,
) -> AdherenceLog:
    return AdherenceLog(
        id=uuid.uuid4(),
        patient_id=patient_id,
        medication_id=medication_id,
        call_time=created_at,
        outcome=outcome,
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_adherence_score_counts_only_confirmed_taken_outcomes(
    db_session: AsyncSession,
) -> None:
    """Missed, side-effect, and unanswered calls must not count as adherence."""
    patient = _patient()
    medication = _medication(patient.id)
    db_session.add_all([patient, medication])
    await db_session.flush()

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            _log(patient.id, medication.id, AdherenceResponseEnum.TAKEN, now),
            _log(
                patient.id,
                medication.id,
                AdherenceResponseEnum.MISSED,
                now - timedelta(hours=1),
            ),
            _log(
                patient.id,
                medication.id,
                AdherenceResponseEnum.SIDE_EFFECT,
                now - timedelta(hours=2),
            ),
            _log(
                patient.id,
                medication.id,
                AdherenceResponseEnum.NO_ANSWER,
                now - timedelta(hours=3),
            ),
        ]
    )
    await db_session.flush()

    score = await AdherenceEngine(db_session).compute_adherence_score(patient.id, days=7)

    assert score == round(1 / (2 * 7) * 100, 1)


@pytest.mark.asyncio
async def test_repeated_side_effect_evaluation_creates_one_alert(
    db_session: AsyncSession,
) -> None:
    """Reprocessing the same alert class in its dedupe window is idempotent."""
    patient = _patient()
    medication = _medication(patient.id)
    db_session.add_all([patient, medication])
    await db_session.flush()

    now = datetime.now(timezone.utc)
    first_log = _log(
        patient.id,
        medication.id,
        AdherenceResponseEnum.SIDE_EFFECT,
        now,
    )
    first_log.side_effect_details = "dizziness"
    db_session.add(first_log)
    await db_session.flush()

    first_alerts = await evaluate_escalations(db_session, patient.id, first_log)
    await db_session.flush()

    second_log = _log(
        patient.id,
        medication.id,
        AdherenceResponseEnum.SIDE_EFFECT,
        now + timedelta(seconds=1),
    )
    second_log.side_effect_details = "dizziness"
    db_session.add(second_log)
    await db_session.flush()

    second_alerts = await evaluate_escalations(db_session, patient.id, second_log)

    assert [alert for alert in first_alerts if alert.alert_type == AlertTypeEnum.side_effect]
    assert not [alert for alert in second_alerts if alert.alert_type == AlertTypeEnum.side_effect]


def test_durable_work_entities_expose_idempotency_contracts() -> None:
    """Durable scheduling/call records must be represented in the ORM schema."""
    expected_tables = {
        "scheduled_doses",
        "call_records",
        "retry_jobs",
    }
    assert expected_tables.issubset(Base.metadata.tables)

    scheduled_dose_constraints = {
        constraint.name
        for constraint in Base.metadata.tables["scheduled_doses"].constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert "uq_scheduled_dose_medication_time" in scheduled_dose_constraints

    for table_name in ("call_records", "retry_jobs"):
        table = Base.metadata.tables[table_name]
        assert table.c.idempotency_key.unique is True


def test_patient_input_requires_indian_e164_and_keeps_legacy_family_alias() -> None:
    """Outbound-call identity data must be validated at the API boundary."""
    patient = PatientCreate(
        name="Meenakshi",
        phone="+919876543001",
        family_contact_phone="+919876543002",
    )
    assert patient.family_whatsapp == "+919876543002"

    with pytest.raises(ValidationError):
        PatientCreate(name="Invalid", phone="555-0100")


def test_webhook_contract_rejects_conflicting_outcome_flags() -> None:
    """Provider payloads cannot claim a confirmed dose that still needs retry."""
    payload = BolnaWebhookPayload(
        patient_id=str(uuid.uuid4()),
        medication_id=str(uuid.uuid4()),
        outcome="TAKEN",
        retry_required=True,
    )

    with pytest.raises(HTTPException) as error:
        _validate_payload_contract(payload, "provider-event-1")

    assert error.value.status_code == 422

