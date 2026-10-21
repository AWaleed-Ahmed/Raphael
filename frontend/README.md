# Raphael website and console

The frontend is one Next.js application, with routes in `src/app`, shared React
components in `src/components`, and landing sections in `src/features/Pages/Landing`.
Dependencies and configuration live directly in `frontend`; there is no nested app.

The public landing page lives at `/`. It uses the approved forest-and-paper
theme, responsive local WebP imagery, an illustrative repair walkthrough,
expandable evidence, and passing/blocked validation examples. These interactions
are presentation-only and make no agent or sandbox API calls.
The walkthrough follows six scroll-driven stages with keyboard navigation, a visible step indicator, and a skip link. The handoff preview has expandable diff, evidence, and validation attachments. The header and closing CTA open the demo console. The intro runs for about 3.4 seconds once per browser session, with the header expanding from a pill after the logo docks. The footer motion control saves a local preference; OS reduced-motion settings always take priority.

Planned architecture work is documented in [the roadmap](docs/roadmap.md).

The existing operator console remains at `/console/`, and the design study at
`/direction/`. Their existing HTML, JavaScript, and styles remain unchanged.

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

Open http://localhost:3000 for the landing page, or append `/console/` for the
dashboard. `npm run dev` runs one Next.js server. Before startup, the existing
console and design study are built as static files and served through Next.js.
No second development server or port 5173 is needed. If you edit the console's
`src/main.js` or `src/styles.css`, restart development to rebuild those files.

Run `npm run build`, then `npm start` (or `npm run preview`) to inspect the
production build. The build compiles the two existing Vite pages, copies their
output into the Next.js public directory, and builds Next.js. The production
server serves all three pages without a separate Vite server. Run `npm test`
for the landing interaction tests.

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
