# Raphael Console

Client-facing dashboard for Raphael’s I0 run API. It is intentionally a thin
client: it reads run state and sends idempotent actions to the agent; it never
calls the sandbox controller directly.

## Run locally

See the [canonical pilot guide](../docs/pilot-install.md#6-optional-local-console)
for demo startup and the optional local `/api` development proxy.

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

An empty `VITE_RAPHAEL_API_URL` selects demo mode. For API data use `/api` with
the guide's proxy; direct access from Vite's origin to port 8091 lacks general
core CORS support. `VITE_*` settings are browser-visible and loaded by Vite,
independently of the Python backend. Keep backend tokens/provider/Supabase keys
out of the bundle. Nonlocal deployment needs a reviewed authenticated server
proxy. A production build and HTTP proxy smoke do not prove the full UI journey.

## Current scope

- Overview metrics and recent runs
- Run filtering and search
- Run detail with diagnosis, evidence, sandbox validation, delivery, and audit
- Retry, escalate, and feedback actions using idempotency keys
- Demo mode when the agent API is unavailable

The API boundary follows `interface/prd-i0-api.md` and the schemas under
`contracts/agent/`.
