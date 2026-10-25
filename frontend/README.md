# Raphael Console

Client-facing dashboard for Raphael’s I0 run API. It is intentionally a thin
client: it reads run state and sends idempotent actions to the agent; it never
calls the sandbox controller directly.

## Run locally

See the [canonical pilot guide](../docs/pilot-install.md#6-optional-local-console)
for demo startup and the optional local `/api` development proxy.

```bash
cd frontend
nvm install
nvm use
npm ci
npm run dev -- --hostname 127.0.0.1 --port 5173
```

Use Node 24.22.1 or a newer 24.x security release. `.nvmrc` selects the
validated version; npm rejects older runtimes. Vercel selects the 24.x line
from `engines.node` and manages patch updates. Redeploy and verify the actual
deployment runtime after a security update; the package setting alone does
not prove an existing deployment is patched.

Open `http://127.0.0.1:5173/console/` for the console; `/` serves the landing page.
An empty `VITE_RAPHAEL_API_URL` selects demo mode. For API data, set
`RAPHAEL_DEV_API_PROXY=true` and `VITE_RAPHAEL_API_URL=/api` in the shell or
`frontend/.env.local`, then restart using the command above. Next.js forwards
`/api/*` to `http://127.0.0.1:8091/*` only in development when opted in. See the
guide for Bash and PowerShell examples. Direct cross-origin access to port 8091
lacks general core CORS support. The dev command builds the legacy console with
Vite before starting Next.js. `VITE_*` settings are browser-visible and embedded
by Vite at build time, independently of the Python backend. Keep backend tokens/provider/Supabase keys
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
