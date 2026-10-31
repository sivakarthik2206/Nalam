"""Nalam — Medication Adherence Platform API."""

import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional
import uuid

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.config import settings
from app.database import async_session_factory, engine
from app.middleware import RequestLoggingMiddleware, ExceptionHandlingMiddleware
from app.models import Patient, Medication, CallSchedule, Pharmacy
from app.routers import adherence, dashboard, patients, webhooks, spec_aliases
from app.utils.language import get_bolna_agent_id
from app.services.bolna_service import BolnaService
from app.services.twilio_service import TwilioService
from app.services.scheduler_service import SchedulerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections for live real-time dashboard events."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcasts a JSON message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


ws_manager = ConnectionManager()


async def broadcast_event(event_type: str, data: dict):
    """Helper to broadcast dashboard events globally."""
    payload = {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await ws_manager.broadcast(payload)


# ---------------------------------------------------------------------------
# Service initialisation helpers
# ---------------------------------------------------------------------------

def _create_bolna_service() -> BolnaService:
    return BolnaService(api_key=settings.BOLNA_API_KEY)


def _create_twilio_service() -> TwilioService:
    return TwilioService(
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN,
        whatsapp_from=settings.TWILIO_WHATSAPP_FROM,
    )


def _create_scheduler_service(
    bolna: BolnaService,
    twilio: TwilioService,
) -> SchedulerService:
    return SchedulerService(
        bolna_service=bolna,
        twilio_service=twilio,
        db_session_factory=async_session_factory,
    )


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise services on startup, tear down on shutdown."""
    logger.info("Starting Nalam API …")

    # Create services
    bolna = _create_bolna_service()
    twilio = _create_twilio_service()
    scheduler = _create_scheduler_service(bolna, twilio)

    # Store on app.state so routers / deps can access them
    app.state.bolna_service = bolna
    app.state.twilio_service = twilio
    app.state.scheduler_service = scheduler
    app.state.ws_manager = ws_manager

    # Start background scheduler
    await scheduler.start()

    yield

    # Shutdown
    await scheduler.stop()
    await bolna.close()
    logger.info("Nalam API shut down cleanly")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Nalam API",
    description="Medication adherence platform with AI voice calls and WhatsApp alerts",
    version="1.0.0",
    lifespan=lifespan,
)

# Custom Middlewares
app.add_middleware(ExceptionHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware — origins from env var
_cors_raw = settings.CORS_ORIGINS
cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(patients.router, prefix="/api/v1")
app.include_router(adherence.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(spec_aliases.router, prefix="/api/v1", tags=["Spec Aliases"])


# ---------------------------------------------------------------------------
# Dependency helpers (access services from any router)
# ---------------------------------------------------------------------------

def get_bolna_service(request: Request) -> BolnaService:
    """FastAPI dependency — returns the BolnaService singleton."""
    return request.app.state.bolna_service


def get_twilio_service(request: Request) -> TwilioService:
    """FastAPI dependency — returns the TwilioService singleton."""
    return request.app.state.twilio_service


def get_scheduler_service(request: Request) -> SchedulerService:
    """FastAPI dependency — returns the SchedulerService singleton."""
    return request.app.state.scheduler_service


# ---------------------------------------------------------------------------
# WebSocket Endpoint for Live Dashboard
# ---------------------------------------------------------------------------

@app.websocket("/api/v1/ws/dashboard")
async def websocket_dashboard_endpoint(websocket: WebSocket):
    """Real-time live updates stream for admin dashboard."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection open and await any client ping or message
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as exc:
        logger.debug(f"WebSocket client terminated: {exc}")
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Health check with DB and Scheduler status
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    """System health check verifying database and background scheduler."""
    db_status = "disconnected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        logger.warning(f"Health check DB ping failed: {e}")
        db_status = f"error: {str(e)}"

    scheduler_status = "stopped"
    try:
        if hasattr(app.state, "scheduler_service") and app.state.scheduler_service.scheduler:
            scheduler_status = "running" if app.state.scheduler_service.scheduler.running else "paused"
    except Exception:
        pass

    is_healthy = db_status == "connected"

    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": "nalam-api",
        "database": db_status,
        "scheduler": scheduler_status,
        "active_ws_connections": len(ws_manager.active_connections),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "Nalam API",
        "description": "Voice-first Medication Adherence Platform",
        "docs_url": "/docs",
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Demo Trigger for Judges & Presentations
# ---------------------------------------------------------------------------

class DemoTriggerRequest(BaseModel):
    phone: str = Field(..., description="Phone number with country code, e.g. +919876543210")
    name: str = Field("Demo Patient", description="Patient name")
    language: str = Field("hindi", description="'hindi', 'tamil', or 'english'")
    medication_name: str = Field("Metformin 500mg", description="Medication name")
    dosage: str = Field("1 tablet", description="Dosage")
    meal_relation: str = Field("after_meal", description="before_meal, after_meal, or with_meal")
    time_slot: str = Field("morning", description="morning, afternoon, evening, night")


@app.post("/api/v1/test/trigger-demo", tags=["Demo"])
async def trigger_demo_call(payload: DemoTriggerRequest, request: Request):
    """
    One-click instant demo endpoint for hackathons/judges.
    Takes a phone number, registers/locates demo patient, and triggers Bolna voice AI call.
    """
    bolna = request.app.state.bolna_service
    twilio = request.app.state.twilio_service

    # Select appropriate agent
    agent_id = get_bolna_agent_id(payload.language)
    if not agent_id:
        # Fallback to Hindi or Tamil if specific agent not configured
        agent_id = settings.BOLNA_AGENT_ID_HINDI or settings.BOLNA_AGENT_ID_TAMIL or "demo-agent"

    patient_id = str(uuid.uuid4())
    medication_id = str(uuid.uuid4())

    async with async_session_factory() as session:
        # Try to find existing demo patient with this phone or create one
        res = await session.execute(select(Patient).where(Patient.phone == payload.phone))
        existing_patient = res.scalar_one_or_none()

        if existing_patient:
            patient_id = str(existing_patient.id)
            # Find or create medication
            med_res = await session.execute(select(Medication).where(Medication.patient_id == existing_patient.id))
            med = med_res.scalars().first()
            if med:
                medication_id = str(med.id)
            else:
                new_med = Medication(
                    id=uuid.UUID(medication_id),
                    patient_id=existing_patient.id,
                    name=payload.medication_name,
                    dosage=payload.dosage,
                    frequency=[payload.time_slot],
                    meal_timing=payload.meal_relation,
                )
                session.add(new_med)
                await session.commit()
        else:
            new_patient = Patient(
                id=uuid.UUID(patient_id),
                name=payload.name,
                phone=payload.phone,
                language=payload.language,
                family_contact_name="Family Caregiver",
                family_whatsapp=payload.phone,
            )
            session.add(new_patient)
            new_med = Medication(
                id=uuid.UUID(medication_id),
                patient_id=uuid.UUID(patient_id),
                name=payload.medication_name,
                dosage=payload.dosage,
                frequency=[payload.time_slot],
                meal_timing=payload.meal_relation,
            )
            session.add(new_med)
            await session.commit()

    user_data = {
        "patient_name": payload.name,
        "medication_name": payload.medication_name,
        "dosage": payload.dosage,
        "meal_relation": payload.meal_relation,
        "language": payload.language,
        "time_slot": payload.time_slot,
        "patient_id": patient_id,
        "medication_id": medication_id,
    }

    logger.info(f"Triggering demo call to {payload.phone} with agent {agent_id}")
    try:
        call_res = await bolna.trigger_call(
            agent_id=agent_id,
            recipient_phone=payload.phone,
            user_data=user_data,
        )
    except Exception as exc:
        logger.error(f"Bolna call trigger failed: {exc}")
        call_res = {"status": "simulated", "message": str(exc), "call_id": f"sim-{uuid.uuid4().hex[:8]}"}

    # Broadcast event via websocket to show live on dashboard
    await broadcast_event("call_triggered", {
        "patient_name": payload.name,
        "phone": payload.phone,
        "medication": payload.medication_name,
        "time_slot": payload.time_slot,
        "call_id": call_res.get("call_id"),
    })

    return {
        "message": f"Demo call initiated to {payload.phone}",
        "call_result": call_res,
        "patient_id": patient_id,
        "medication_id": medication_id,
    }
