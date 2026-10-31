# Nalam (நலம்)

Nalam is a voice-first medication-adherence monitoring demo for elderly patients. A configured Tamil Bolna agent calls a consented test patient, records a structured medication outcome in FastAPI, calculates adherence from stored logs, and creates family/pharmacy alerts. The Next.js dashboard reads the backend as its source of truth.

This checkout is a buildathon/demo system. It must use synthetic records and sandbox/test recipients only. It is not a medical device, does not diagnose, and must not be used with real patient data until authentication, tenant isolation, webhook authentication, retention controls, and regulatory review are complete.

## Architecture

```text
Next.js (Vercel) ──HTTP/WebSocket──> FastAPI (Railway/Render)
                                      │
                                      ├── SQLAlchemy async ──> PostgreSQL
                                      ├── Bolna outbound call
                                      │      └── POST /api/v1/log-response
                                      └── Twilio WhatsApp Sandbox
```

The intended workflow is:

1. An operator selects an explicitly seeded demo patient in `/admin`.
2. FastAPI loads the patient and medication context and asks Bolna to call the configured test number.
3. The Tamil conversation confirms identity, asks about the configured medicine and meal timing, checks side effects, and calls `report_adherence` once.
4. FastAPI validates/normalizes the outcome, stores an `AdherenceLog`, evaluates alerts, and schedules a follow-up for a missed or unanswered outcome.
5. The dashboard refreshes through polling/WebSocket invalidation and displays the persisted result.

The backend currently uses an in-process APScheduler. It has restart recovery logic, but pending work is not yet a fully durable database-backed queue; run one web worker until that limitation is removed.

## Repository layout

- `backend/app/`: FastAPI application, SQLAlchemy models, routers, adherence, scheduler, Bolna, and Twilio services.
- `backend/tests/`: pytest contract and regression tests; provider calls are mocked or omitted.
- `backend/scripts/seed_demo.py`: idempotent synthetic demo seed.
- `frontend/`: Next.js family and admin views.
- `bolna-agents/tamil-agent-prompt.md`: Tamil conversation/tool contract to configure in Bolna.
- `.github/workflows/lint.yml`: backend tests, frontend lint/type/build checks, and high-confidence secret scanning.

