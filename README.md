# Nalam (நலம்) — Voice-First Medication Adherence Platform

> **Nalam** (நலம் — Tamil for *Wellbeing/Good Health*) is an empathetic, voice-first medication adherence and chronic disease care platform tailored specifically for elderly patients and families across India. Powered by conversational AI voice calls in local languages (Hindi, Tamil, English) and proactive WhatsApp caregiver alerts.

---

## 🌟 The Problem
In India, over **77 million people live with Type 2 Diabetes** and another **80+ million battle Hypertension**. For elderly parents living independently:
- **Language & Literacy Barriers:** Complex English smartphone health apps fail for non-English speaking elderly parents.
- **Cognitive Load & Polypharmacy:** Elderly seniors take 4–8 pills daily at different times (before meals, after meals). Forgetting doses is rampant.
- **Caregiver Anxiety & Separation:** Adult children working in metropolitan cities or abroad experience persistent anxiety over whether their parents took vital heart or BP medicines on time.
- **Unnoticed Side Effects & Refill Stockouts:** Dizziness or nausea often goes unreported until an emergency hospital admission occurs.

---

## 💡 The Solution: The Closed-Loop Care System

```
                      ┌────────────────────────────────┐
                      │   Local Pharmacy / Hospital    │
                      │       Nalam Admin Portal       │
                      └───────────────┬────────────────┘
                                      │ (1) Prescribes & Schedules
                                      ▼
                      ┌────────────────────────────────┐
                      │      Nalam FastAPI Engine      │
                      │   (APScheduler + PostgreSQL)   │
                      └───────────────┬────────────────┘
                                      │ (2) Triggers Scheduled Call
                                      ▼
                      ┌────────────────────────────────┐
                      │    Bolna Conversational AI     │
                      │  (Warm Hindi / Tamil / English)│
                      └───────────────┬────────────────┘
                                      │ (3) 90-sec Empathetic Call
                                      ▼
                      ┌────────────────────────────────┐
                      │        Elderly Patient         │
                      │   (Answers landline / mobile)  │
                      └───────────────┬────────────────┘
                                      │ (4) In-call voice response
                                      ▼
                      ┌────────────────────────────────┐
                      │   Instant Webhook Evaluation   │
                      └───────┬────────────────┬───────┘
            Taken / Praise    │                │ Missed / Side Effect / Low Refill
                              ▼                ▼
     ┌──────────────────────────────┐    ┌───────────────────────────────────┐
     │  Live Real-time Dashboard    │    │      Twilio WhatsApp Alert        │
     │   (WebSocket Event Stream)   │    │  (Sent to Son / Daughter instantly│
     │      Adherence Score ++      │    │  with 1-click WhatsApp Call link) │
     └──────────────────────────────┘    └───────────────────────────────────┘
```

1. **Warm Human-like Check-ins:** The system places a friendly call in natural Hindi ("Maata ji") or Tamil ("Amma") asking if the morning/evening dose was taken relative to food.
2. **Real-time In-Call Feedback:** Powered by Bolna tool calling, patient confirmations, rescheduled doses, or side effects are processed within milliseconds.
3. **Peace of Mind for Children:** If a dose is missed or dizziness is reported, the caregiver receives an immediate WhatsApp notification with full context.
4. **Pharmacy Refill Management:** Tracks remaining pills automatically and alerts both pharmacy and family 5 days before stock runs out.

---

## 🛠️ Tech Stack

### Backend
- **Framework:** Python 3.12, FastAPI, Uvicorn
- **ORM & DB:** SQLAlchemy 2.0 (Async), PostgreSQL, asyncpg driver
- **Migrations:** Alembic
- **Task Scheduling:** APScheduler (Timezone-aware: `Asia/Kolkata` IST)
- **Voice Agent:** [Bolna AI](https://bolna.ai) Voice Agents (Hindi, Tamil, English prompts)
- **Messaging:** Twilio WhatsApp Business API
- **Real-Time:** WebSockets for instant dashboard event streaming

### Frontend
- **Framework:** Next.js 16.4.1 (App Router), TypeScript
- **Styling:** Tailwind CSS v4, Lucide React icons
- **UI Components:** Radix UI / shadcn/ui primitives (cards, dialogs, sheets, badges, tabs)
- **State & Data Fetching:** TanStack React Query v5, Axios
- **Data Visualisations:** Recharts (30-day adherence trend lines, 7-day adherence bars)
- **Delight:** Canvas Confetti for patient onboarding success

---

## 📁 Repository Structure

```
Nalam/
├── backend/
│   ├── alembic/                  # Database migration scripts
│   ├── alembic.ini               # Alembic configuration
│   ├── app/
│   │   ├── config.py             # Pydantic v2 application settings
│   │   ├── database.py           # Async SQLAlchemy session engine
│   │   ├── main.py               # FastAPI app, lifespan, WebSockets, Demo endpoint
│   │   ├── middleware.py         # Exception handling & request logging middleware
│   │   ├── models.py             # SQLAlchemy models (Patient, Medication, AdherenceLog, Alert)
│   │   ├── schemas.py            # Pydantic validation schemas
│   │   ├── routers/
│   │   │   ├── adherence.py      # Adherence history, metrics, manual logging
│   │   │   ├── dashboard.py      # Pharmacy overview stats, alerts, refill lists
│   │   │   ├── patients.py       # Patient & medication CRUD, instant trigger calls
│   │   │   └── webhooks.py       # Bolna in-call function & post-call status webhooks
│   │   ├── services/
│   │   │   ├── adherence_engine.py  # Calculates streaks, 7d/30d scores, refill deduction
│   │   │   ├── bolna_service.py     # Bolna API client for voice triggers
│   │   │   ├── scheduler_service.py # APScheduler runner for automated call slots
│   │   │   └── twilio_service.py    # WhatsApp caregiver alert delivery
│   │   └── utils/
│   │       └── language.py       # Indian language mapping helpers
│   ├── seed.py                   # Demo database seeder
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── admin/            # Pharmacy staff dashboard, patients, alerts, refills
│   │   │   ├── family/[patientId]/ # Shareable non-clinical caregiver status page
│   │   │   ├── onboard/          # Multi-step patient onboarding with instant test call
│   │   │   └── page.tsx          # Public landing page
│   │   ├── components/           # Reusable UI & dashboard components
│   │   ├── lib/                  # API client, React Query hooks, types, WebSocket helper
│   │   └── providers/            # React Query & Toast providers
│   ├── package.json
│   └── vercel.json
├── bolna-agents/
│   ├── hindi-agent-prompt.md     # Production Bolna prompt for Hindi/Hinglish calls
│   ├── tamil-agent-prompt.md     # Production Bolna prompt for Tamil/Tanglish calls
│   └── english-agent-prompt.md   # Production Bolna prompt for Indian English calls
├── .github/workflows/lint.yml    # CI test and build workflow
├── docker-compose.yml            # Local PostgreSQL + Backend orchestration
├── Procfile                      # Railway deployment configuration
├── railway.toml                  # Nixpacks deployment configuration
└── README.md
```

---

## 🚀 Quickstart & Local Setup

### Prerequisites
- Python 3.12+
- Node.js 20+ & pnpm
- Docker & Docker Compose (or a local PostgreSQL 16 instance)

### 1. Clone & Configure Environment

Create your `.env` file in the root:
```bash
cp .env.example .env
```

Populate your API keys:
- `BOLNA_API_KEY`: Get from [Bolna Dashboard](https://bolna.ai)
- `BOLNA_AGENT_ID_HINDI`: Agent ID for Hindi calls
- `BOLNA_AGENT_ID_TAMIL`: Agent ID for Tamil calls
- `TWILIO_ACCOUNT_SID`: Twilio account SID
- `TWILIO_AUTH_TOKEN`: Twilio auth token
- `TWILIO_WHATSAPP_FROM`: WhatsApp sender (e.g. `whatsapp:+14155238886`)

### 2. Run Database & Backend

Using Docker Compose:
```bash
docker compose up -d db
```

Or run FastAPI directly:
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000
```
Backend Swagger API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Run Frontend

In a separate terminal:
```bash
cd frontend
pnpm install
pnpm dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## ⚡ Live Hackathon Demo Features

1. **One-Click Instant Judge Demo Call:**
   - Make a `POST` request to `/api/v1/test/trigger-demo` with your personal phone number, language (`"hindi"`, `"tamil"`, or `"english"`), and medication name.
   - Within 5 seconds, your phone will ring with Nalam calling in your chosen language!
2. **Interactive Onboarding (`/onboard`):**
   - Clean 4-step wizard: Patient Info $\rightarrow$ Chronic Medications $\rightarrow$ Call Timing & Food Relations $\rightarrow$ Instant Test Call.
   - Confetti celebration upon completion with a one-click copyable Family Dashboard link.
3. **Shareable Family Link (`/family/{patientId}`):**
   - Clean, loving, zero-jargon dashboard designed for family members.
   - Displays 7-day adherence bars, today's medication timeline, and an emergency "Call Parent" button.
4. **Staff Admin Operations (`/admin`):**
   - Real-time KPI counter (Active Patients, Today's Adherence Rate, Critical Alerts, Pending Refills).
   - Instant voice call trigger from patient list.
   - Refill inventory depletion tracking based on adherence logs.

---

## 🛡️ Safety & Medical Disclaimers
- Nalam is an adherence companion and never modifies prescriptions or provides medical diagnoses.
- In-call safety guardrails immediately instruct patients reporting severe distress (chest pain, acute breathlessness) to contact emergency services (108 in India) and instantly flags emergency alerts to registered family members.

---

## 👨‍💻 Author & Buildathon Credit
- **Built by:** Siva Karthik
- **Institution:** Vellore Institute of Technology (VIT), Chennai
- **Theme:** AI Voice & Healthcare for Bharat
