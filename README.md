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

## Configuration

Copy `backend/.env.example` to `backend/.env`. The backend reads these variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL async URL, for example `postgresql+asyncpg://...` |
| `SUPABASE_DATABASE_URL` | Optional database override; when non-empty it takes precedence |
| `BOLNA_API_KEY` | Server-only Bolna credential |
| `BOLNA_AGENT_ID_TAMIL` | Tamil Bolna agent identifier |
| `BOLNA_WEBHOOK_SECRET` | Shared secret used to authenticate Bolna callback bodies |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | Server-only Twilio credentials |
| `TWILIO_WHATSAPP_FROM` | Joined WhatsApp Sandbox sender, normally `whatsapp:+14155238886` |
| `BACKEND_PUBLIC_URL` | Public HTTPS backend URL used in provider setup |
| `APP_BASE_URL` | Frontend URL used in dashboard links |
| `CORS_ORIGINS` | Comma-separated browser origins; do not use `*` for deployment |
| `DEMO_FAMILY_WHATSAPP` | Optional configured test recipient used by the seed script |
| `DEMO_RETRY_DELAY_SECONDS` | Optional local retry delay override; leave blank for 30 minutes and never set it in production |

The frontend uses only public browser variables in `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws/dashboard
```

The scheduler currently reads `DEMO_RETRY_DELAY_SECONDS` directly from the process environment; it does not yet require an explicit `DEMO_MODE=true` guard. Leave it blank outside local demos. The repository still contains legacy Hindi/English and Sarvam references in `bolna-agents/bolna_agent_config.json`; that file must not be imported as the Tamil production configuration.

## Local setup

Prerequisites: Python 3.12+, PostgreSQL 16+, Node.js 20+, and pnpm 10.

```powershell
docker compose up -d db

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install pytest pytest-asyncio aiosqlite
Copy-Item .env.example .env
```

The current Alembic head includes an empty-database path and an additive durable-domain migration, but it was not executable in this environment because Docker/PostgreSQL was unavailable. Verify `alembic upgrade head` against a fresh PostgreSQL database before deployment. The demo seed also calls SQLAlchemy `create_all` for local convenience; that is not a substitute for production migrations.

For a local demo database only:

```powershell
python -m scripts.seed_demo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```powershell
cd frontend
pnpm install --frozen-lockfile
Copy-Item ..\.env.example .env.local
pnpm dev
```

Open `http://localhost:3000/admin`. The seed script is intended to be idempotent by patient phone and medication name, but it only contains synthetic records.

## Provider setup

### Bolna

Deploy the backend at a public HTTPS URL before configuring Bolna. Configure one Tamil agent with Bolna's bundled ASR/LLM/TTS, the prompt in `bolna-agents/tamil-agent-prompt.md`, and the `report_adherence` tool URL:

```text
https://<backend-host>/api/v1/log-response
```

The post-call endpoint is:

```text
https://<backend-host>/api/v1/webhooks/bolna
```

The callback endpoints require `BOLNA_WEBHOOK_SECRET` and an HMAC/static-secret header. Configure the provider's exact supported signature header before exposing them publicly. A configured `BOLNA_API_KEY` or agent ID is not evidence that a real call was completed.

### Twilio WhatsApp Sandbox

Configure the account SID, auth token, sender, and a family/test recipient that has joined the sandbox. The current service reports provider request results but does not persist a complete delivery state machine or verify delivery callbacks. Automated tests never send real messages.

## Commands and verification

Backend:

```powershell
cd backend
pytest -q
python -m compileall -q app scripts
```

Frontend:

```powershell
cd frontend
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

Important endpoints include `GET /health`, `GET /`, `GET /api/v1/dashboard/admin`, `GET /api/v1/dashboard/family/{patient_id}`, `POST /api/v1/dashboard/trigger-call/{patient_id}`, `POST /api/v1/log-response`, and `POST /api/v1/webhooks/bolna/function`.

The tests prove local contracts using SQLite and provider mocks. They do not prove a live Bolna call, a live Twilio delivery, a public deployment, or a PostgreSQL migration run.

## Deployment

### Numbered deployment sequence

Complete in order. Steps that need a URL you don't have yet are marked — come back after the step that produces it.

**1. Collect credentials**
- Railway PostgreSQL URL (change scheme to `postgresql+asyncpg://`)
- Bolna API key (dashboard → API Keys)
- Twilio Account SID + Auth Token (Twilio console → Account Info)
- Generate webhook secret: `python -c "import secrets; print(secrets.token_hex(32))"`

**2. Deploy backend to Railway**
1. Push repo to GitHub; create a Railway project from the repo.
2. Add a PostgreSQL plugin; Railway injects `DATABASE_URL` automatically.
3. Set Railway environment variables (Settings → Variables) using `backend/.env.example` as a guide. Leave `BOLNA_AGENT_ID_TAMIL` and `BACKEND_PUBLIC_URL` blank for now.
4. First deploy runs `alembic upgrade head` then starts Uvicorn.
5. Copy the Railway public URL shown in the deploy log.
6. Set `BACKEND_PUBLIC_URL=https://<your-railway-url>` in Railway variables and redeploy.
7. Verify: `curl https://<your-railway-url>/health` → `{"status":"ok"}`

**3. Import Bolna Tamil agent**
1. Fill `BACKEND_PUBLIC_URL` and `BOLNA_WEBHOOK_SECRET` in `backend/.env`.
2. Render the agent config: `cd backend && python -m scripts.render_bolna_config`
3. Bolna dashboard → Agents → Import → upload `bolna-agents/bolna_agent_config.json`.
4. Copy the agent UUID; set `BOLNA_AGENT_ID_TAMIL=<uuid>` in Railway variables.
5. In Bolna agent settings, add header `X-Bolna-Webhook-Secret: <your secret>`.

**4. Deploy frontend to Vercel**
> `NEXT_PUBLIC_API_URL` is baked into the Next.js bundle at build time — set it **before** the Vercel build runs.

1. New Vercel project → import repo → Root Directory: `frontend`.
2. Add environment variable `NEXT_PUBLIC_API_URL=https://<your-railway-url>` in Vercel.
3. Deploy.
4. Copy Vercel URL; update Railway variables: `APP_BASE_URL`, `FRONTEND_ORIGIN`, `CORS_ORIGINS`.

**5. Seed demo data**
```bash
cd backend
DATABASE_URL=postgresql+asyncpg://... python -m scripts.seed_demo
```
Confirms: 1 Tamil patient (Meenakshi Sundaram), 2 medications, 7 days history.

**6. Verify Twilio sandbox participation**
1. Family member sends `join <sandbox-keyword>` to WhatsApp `+14155238886`.
   (Keyword in Twilio console → Messaging → Try it out → Send a WhatsApp message)
2. Verify: `curl -X POST https://<your-railway-url>/api/v1/test/send-test-whatsapp`
   - Success: `{"message":"Test WhatsApp sent successfully","sid":"SM..."}`
   - Failure: `WhatsApp alert failed: recipient has not joined the Twilio sandbox` → repeat step 1.

**7. Run smoke test**
```bash
# Trigger demo call
curl -X POST https://<your-railway-url>/api/v1/test/trigger-demo \
  -H "Content-Type: application/json" \
  -d '{"phone":"+919876543001"}'

# Check health
curl https://<your-railway-url>/health
```

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `404` on trigger-demo | Patient not seeded with `demo_only=True` | Re-run `seed_demo.py` |
| `503 Tamil Bolna agent is not configured` | `BOLNA_AGENT_ID_TAMIL` not set | Complete step 3 |
| `WhatsApp alert failed: recipient has not joined the Twilio sandbox` | Sandbox join not completed | Complete step 6 |
| Frontend shows CORS error or wrong data | `NEXT_PUBLIC_API_URL` baked with wrong value | Update Vercel env var and **redeploy** |
| Railway deploy fails at `alembic upgrade head` | `DATABASE_URL` wrong scheme | Use `postgresql+asyncpg://` not `postgresql://` |
| `ValidationError` on `DEMO_RETRY_DELAY_SECONDS` | Old code without blank-string coercion | Ensure latest code is deployed |

### Backend

`railway.toml` starts one Uvicorn worker and runs `alembic upgrade head` before startup. Provide PostgreSQL, `DATABASE_URL`, the server-only provider credentials, `BACKEND_PUBLIC_URL`, `APP_BASE_URL`, and an explicit `CORS_ORIGINS`. Verify `/health` and database readiness after deployment. Because the scheduler is in-process, do not scale the web process horizontally.

### Frontend

Create a Vercel project with root directory `frontend`, use the Next.js preset, and set `NEXT_PUBLIC_API_URL` to the deployed backend URL. Never put database, Bolna, Twilio, or webhook credentials in Vercel variables.

## Demo sequence

1. Start PostgreSQL, seed the synthetic data, and start FastAPI and Next.js.
2. Open `/admin` and select a seeded patient.
3. Use the manual call control only after configuring a real Bolna agent and test recipient.
4. For a local contract-only demo, submit a structured payload to `/api/v1/log-response` with the seeded patient and medication UUIDs; inspect the family/admin dashboards afterward.
5. For a missed-dose path, submit `outcome=MISSED`; inspect the persisted retry scheduling/log output. The production default is 30 minutes. For a local-only accelerated run, set `DEMO_RETRY_DELAY_SECONDS=120` before starting the backend and clear it afterward.
6. Treat any WhatsApp alert as unverified until it is observed in the joined sandbox; no local test simulates provider delivery.

## Security status

No committed high-confidence API credentials were found in the tracked files reviewed for this QA pass. `.env.example` files contain blanks/placeholders, and CI scans tracked files for common credential patterns. That does not make the application safe for public health data: authentication/authorization, tenant isolation, webhook signature validation, rate limiting, strict demo-recipient enforcement, durable idempotency across webhook side effects, and secret rotation remain required before production use.
