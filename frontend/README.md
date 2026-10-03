# Raphael website and console

The public landing page lives at `/`. It uses the approved forest-and-paper
theme, responsive local WebP imagery, an illustrative repair walkthrough,
expandable evidence, and passing/blocked validation examples. These interactions
are presentation-only and make no agent or sandbox API calls.
The walkthrough has five selectable stages, can be played or paused, and
shows the relevant evidence at each step. The footer motion control saves a
local preference; OS reduced-motion settings always take priority.

The existing operator console is available at `/console/`. Vite builds both
HTML entry points; their scripts and styles are kept separate.

## Operator console

Client-facing dashboard for Raphael’s I0 run API. It is intentionally a thin
client: it reads run state and sends idempotent actions to the agent; it never
calls the sandbox controller directly.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL for the website, or append `/console/` for the
dashboard. Run `npm run build` to create both pages in `dist`, then
`npm run preview` to inspect the production build. Static hosting must serve
`index.html` at `/` and `console/index.html` at `/console/`; `vercel.json`
includes the console rewrite.

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
