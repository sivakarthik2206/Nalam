# Nalam — Demo Script

Tamil-only voice AI medication adherence demo. Total runtime: ~4 minutes.

---

## Prerequisites checklist

Before going live, verify each item:

- [ ] Railway backend URL known: `https://<your-railway-url>`
- [ ] Vercel frontend URL known: `https://<your-vercel-url>`
- [ ] `BOLNA_AGENT_ID_TAMIL` set in Railway environment variables
- [ ] Demo patient seeded: `python -m scripts.seed_demo` (see patient ID in output)
- [ ] Twilio sandbox joined by family number: `curl -X POST https://<railway-url>/api/v1/test/send-test-whatsapp`
- [ ] Frontend loads: open `https://<vercel-url>` in browser

---

## Demo flow (~4 minutes)

### Part 1 — Show the dashboard (30 seconds)

Open `https://<vercel-url>` and navigate to the admin view.

> **Say:** "This is Nalam — a voice AI that calls elderly patients every day in
> Tamil, checks whether they took their medication, and alerts the family on
> WhatsApp if something is wrong."

Point to the patient card: Meenakshi Sundaram, 2 active medications, 75% adherence
over the last 7 days.

---

### Part 2 — Trigger the demo call (30 seconds)

Click "Trigger Call" on the dashboard, or run:

```bash
curl -X POST https://<your-railway-url>/api/v1/test/trigger-demo \
  -H "Content-Type: application/json" \
  -d '{"phone":"+919876543001"}'
```

> **Say:** "I just triggered a real outbound call. Bolna's Tamil voice agent is
> dialling the patient now."

---

### Part 3 — Live call (60–90 seconds)

The agent calls the configured number and speaks in Tamil. The call follows this
sequence:

| Agent says (Tamil) | Translation | Patient should say |
|---|---|---|
| "வணக்கம் Meenakshi Sundaram அவர்களே. நான் நலம் உதவியாளர் பேசுகிறேன். நீங்கள் Meenakshi Sundaram அவர்கள்தானா? எப்படி இருக்கிறீர்கள்?" | Greeting and identity check | "ஆம், நான்தான்" (Yes, it's me) |
| "இன்றைய morning நேரத்தில் Metformin 500mg, 1 tablet மாத்திரையை எடுத்தீர்களா?" | Did you take your morning Metformin? | "ஆம், எடுத்தேன்" (Yes, I took it) |
| "மருந்து எடுத்த பிறகு ஏதாவது உடல் சிரமம் இருக்கிறதா?" | Any side effects? | "இல்லை" (No) |
| "நன்றி. உங்கள் உடல்நலத்தை கவனித்துக்கொள்ளுங்கள். வணக்கம்." | Thank you, goodbye | — |

> **Say:** "The agent is speaking in Tamil — natural, spoken Tamil, not robotic.
> It confirms identity before naming any medication, so patient data is never
> exposed to the wrong caller."

---

### Part 4 — Show real-time update (30 seconds)

Once the call ends, the backend receives the adherence result via Bolna webhook
and the dashboard updates automatically.

> **Say:** "The call result is already in the database. The dashboard shows the
> outcome — Taken — and updates the 7-day adherence score live."

Point to the updated adherence log entry.

---

### Part 5 — Show the WhatsApp alert (30 seconds)

If outcome was MISSED, SIDE_EFFECT, or NO_ANSWER, a WhatsApp message is sent to
the family number. Show the message on the judge's phone:

> *Sample alert (Tamil):*
> ```
> ⚠️ Nalam எச்சரிக்கை — Meenakshi Sundaram கடந்த 2 அழைப்புகளுக்கு
> பதிலளிக்கவில்லை. தயவுசெய்து அவரைப் பார்க்கவும்.
> ```

> **Say:** "The family gets a Tamil WhatsApp alert immediately. They don't need
> to log in anywhere — they just get a message on their phone."

---

### Part 6 — Wrap up (30 seconds)

Navigate to the 7-day adherence chart in the dashboard.

> **Say:** "Every call builds a history. The family and the doctor can see
> patterns over time — which days were missed, whether there are side effects.
> That's Nalam."

---

## Troubleshooting cheatsheet

### Call not triggering

```bash
# Check backend is up
curl https://<railway-url>/health

# Check agent ID is set
curl https://<railway-url>/api/v1/test/trigger-demo \
  -H "Content-Type: application/json" \
  -d '{"phone":"+919876543001"}'
# 503 → BOLNA_AGENT_ID_TAMIL not set in Railway
# 404 → patient not seeded — run seed_demo.py
# 403 → consent_status not granted — run seed_demo.py again (it fixes it)
```

### WhatsApp not delivered

```bash
curl -X POST https://<railway-url>/api/v1/test/send-test-whatsapp
# "recipient has not joined the Twilio sandbox" → family must send
#   "join <keyword>" to +14155238886 on WhatsApp first
```

### Frontend shows wrong data / CORS error

The `NEXT_PUBLIC_API_URL` in Vercel must point to your Railway URL. If you changed
the Railway URL, you must update this variable in Vercel **and redeploy** the
frontend (env vars bake in at build time, not runtime).

### Agent speaks but outcome is not logged

Check Railway logs for webhook errors. Common causes:
- `BOLNA_WEBHOOK_SECRET` mismatch between Railway and Bolna agent header
- `BACKEND_PUBLIC_URL` in Railway pointing to wrong URL (Bolna cannot reach it)

```bash
# Manually log a response to verify the pipeline
curl -X POST https://<railway-url>/api/v1/log-response \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "<patient-id-from-seed>",
    "medication_id": "<medication-id-from-seed>",
    "outcome": "TAKEN",
    "side_effect_noted": false,
    "retry_required": false,
    "time_slot": "morning"
  }'
```

### Dashboard not updating in real time

The WebSocket connection requires the Railway URL to be reachable from the browser.
If the browser shows a CORS or WebSocket error in DevTools, check `CORS_ORIGINS`
in Railway variables includes the Vercel URL.

---

## Key Tamil phrases for judges

| Phrase | Meaning |
|---|---|
| வணக்கம் | Hello / Greeting |
| நான் நலம் உதவியாளர் பேசுகிறேன் | I am the Nalam assistant speaking |
| மாத்திரை எடுத்தீர்களா? | Did you take the tablet? |
| ஆம், எடுத்தேன் | Yes, I took it |
| இல்லை, இன்னும் எடுக்கவில்லை | No, I haven't taken it yet |
| மருந்து தீர்ந்துவிட்டது | The medicine is finished (stock out) |
| உடல் சிரமம் | Physical discomfort / side effect |
| நன்றி | Thank you |
