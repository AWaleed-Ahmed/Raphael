# Raphael Console

Client-facing dashboard for Raphael’s I0 run API. It is intentionally a thin
client: it reads run state and sends idempotent actions to the agent; it never
calls the sandbox controller directly.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

By default the console runs in demo mode with realistic local data. To connect
to an agent API, set the Vite build-time variable:

```bash
VITE_RAPHAEL_API_URL=http://127.0.0.1:8091 npm run dev
```

The optional `VITE_RAPHAEL_INTERFACE_TOKEN` is intended only for local testing.
Do not put a production bearer token in a browser bundle; deploy a same-origin
server-side proxy instead.

## Current scope

- Overview metrics and recent runs
- Run filtering and search
- Run detail with diagnosis, evidence, sandbox validation, delivery, and audit
- Retry, escalate, and feedback actions using idempotency keys
- Demo mode when the agent API is unavailable

The API boundary follows `interface/prd-i0-api.md` and the schemas under
`contracts/agent/`.
