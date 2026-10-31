# Nalam frontend

This is the Next.js dashboard for the Nalam medication-adherence demo. It exposes two product views:

- `/family/[patientId]` for a synthetic family dashboard.
- `/admin` for pharmacy/admin operations and the manual demo-call control.

The browser talks directly to the FastAPI service. No backend credentials belong in this project or in any `NEXT_PUBLIC_*` variable.

## Local development

From `frontend/`:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Create `frontend/.env.local` with the public URLs for the backend:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws/dashboard
```

The API base URL must include `/api/v1`. The WebSocket URL is optional; when configured it is used for dashboard invalidation events. These values are public browser configuration, not secrets.

## Verification

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm build
```

The build requires a reachable backend only when a page is exercised at runtime; the Next.js production build itself uses the public URL values above.

## Vercel deployment

Set the Vercel project root directory to `frontend`, use the Next.js framework preset, and define:

- `NEXT_PUBLIC_API_URL=https://<backend-host>/api/v1`
- `NEXT_PUBLIC_WS_URL=wss://<backend-host>/api/v1/ws/dashboard`

The backend must allow the deployed Vercel origin through its `CORS_ORIGINS` setting. Do not put `BOLNA_*`, `TWILIO_*`, database URLs, or webhook secrets in Vercel environment variables.

## Trust and demo limits

The current backend has no user authentication and the public family route is ID-addressable. Use synthetic seeded records only until authentication and access controls are implemented. A successful page load does not verify a Bolna call or Twilio WhatsApp delivery.
