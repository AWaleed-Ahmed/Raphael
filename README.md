<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="frontend/public/logo-white.png" />
    <source media="(prefers-color-scheme: light)" srcset="frontend/public/logo-dark.png" />
    <img src="frontend/public/logo-dark.png" alt="Raphael wing mark" width="150" height="100" />
  </picture>
  <h1>Raphael</h1>
  <p>Investigate failed deployments. Test a repair. Send it for review.</p>
  <p>
    <a href="https://github.com/AWaleed-Ahmed/Raphael/actions/workflows/ci.yml"><img src="https://github.com/AWaleed-Ahmed/Raphael/actions/workflows/ci.yml/badge.svg" alt="Core CI" /></a>
    <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white" alt="Python 3.12 or newer" />
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="Apache License 2.0" /></a>
  </p>
</div>

Raphael helps platform engineers investigate Kubernetes deployment failures. It
turns webhook events into evidence, diagnoses supported failure classes, and
coordinates reproduction and validation through [Ignis](https://github.com/AWaleed-Ahmed/Ignis).
Validated changes can become draft pull requests; uncertain or blocked cases
produce an escalation report.

The two projects have distinct jobs: Raphael owns diagnosis, patch policy and
GitHub delivery; Ignis runs the sandbox. Production stays read-only, and a human
reviews what ships. Publication defaults to dry-run.

## Features

- **Failure intake:** GitHub, Kubernetes, Prometheus Alertmanager, Datadog and
  CloudWatch webhook adapters with normalized failure fingerprints.
- **Evidence and diagnosis:** deterministic analyzers for probe mismatches,
  image-reference failures, missing configuration and policy blocks.
- **Bounded repair:** allowlisted patch templates, retries within a budget,
  sandbox validation and structured refusal when evidence is insufficient.
- **Optional localization:** source anchors, candidate ranking and scoped
  healthy-trace comparisons backed by Supabase.
- **Operator tools:** run history, retry/escalate/feedback APIs, JSON or SQLite
  run storage, and a browser console with demo data.
- **Optional external models:** OpenAI, Gemini, Anthropic and other configured
  providers through the [BYOK adapters](docs/byok-provider-guide.md). Model
  suggestions remain subject to deterministic policy checks.

These are implemented paths, not a claim that every integration is qualified
for a customer deployment. Local trained inference and broader localization,
learning and partner acceptance have separate verification requirements.

## Demo

> Screenshot or GIF pending: capture the console's run detail and one validated
> repair or refusal. Label any capture made with demo data.

<!-- TODO: Add a real screenshot or GIF here after capturing and reviewing it. -->

You can try the console with local demo data:

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1 --port 5173
```

Open [localhost:5173/console/](http://127.0.0.1:5173/console/); `/` serves the
landing page. Leave `VITE_RAPHAEL_API_URL` unset for demo mode. See the [console guide](frontend/README.md) for connecting to the
core through a local proxy.

## Tech stack

| Component | Technology |
| --- | --- |
| Diagnosis and repair graph | Python 3.12+, LangGraph |
| Core HTTP services | Starlette, Uvicorn, HTTPX |
| Data validation | JSON Schema, Pydantic, PyYAML |
| Persistence | JSON files or SQLite; optional Supabase catalog/telemetry |
| Operator console | JavaScript, CSS, Vite 6 |
| Sandbox execution | Separate Rust [Ignis](https://github.com/AWaleed-Ahmed/Ignis) service |
| Tests | pytest, unittest and cross-repository process evaluations |

## Getting started

### Prerequisites

- Python 3.12+ with `venv` and pip.
- Git.
- For the optional console: Node.js 24.22.1 or newer 24.x and npm; select
  `frontend/.nvmrc` with `nvm install` and `nvm use` from `frontend/`.
- For a full sandbox pilot: a compatible Ignis build and its prerequisites.
  Follow the [pilot installation guide](docs/pilot-install.md) for the tested pair.

### Install

```bash
git clone https://github.com/AWaleed-Ahmed/Raphael.git
cd Raphael
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-bootstrap.txt
python -m pip install -e agent -e dispatch
```

For an existing clone, start at the virtual-environment step from its root.
Commands below use Bash; Linux/WSL setup details are in [CONTRIBUTING.md](CONTRIBUTING.md).

### Run the recorded-data smoke

This exercises the agent graph without a cluster, provider key or Supabase
project. Sandbox responses are recorded fixtures, and publication is simulated.

```bash
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_PUBLISH_MODE=dry_run
export RAPHAEL_MODEL_ENABLED=0
export RAPHAEL_LLM_DIAGNOSIS=0
export RAPHAEL_LLM_PATCH=0
export RAPHAEL_LEARNING=0
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
```

The included probe-mismatch fixture should finish with
`status=success_draft_pr_ready` and `terminal_reason=draft_pr_dry_run`.
The printed compare URL is a simulated publication, not an opened pull request.

### Start the core

With the environment above still active, run from the repository root:

```bash
export RAPHAEL_AGENT_LISTEN=127.0.0.1:8091
python run.py
```

`run.py` serves the agent and dispatch routes together, sharing one orchestrator.
Starting this process alone does not start a sandbox executor. Use the
[pilot installation guide](docs/pilot-install.md) to configure the Ignis connector,
dispatch tokens, persistence and webhook-to-dispatch bridge.

The pilot guide names a specific release pair. Check this checkout's
[`CONTRACTS_VERSION`](CONTRACTS_VERSION) before following release-specific commands;
an older branch may carry a different pin.

## Usage

In another terminal, inspect the local core:

```bash
curl --fail http://127.0.0.1:8091/health
curl --fail http://127.0.0.1:8091/v1/runs
curl --fail http://127.0.0.1:8091/v1/metrics
```

The interface permits unauthenticated loopback requests only when
`RAPHAEL_INTERFACE_TOKEN` is unset. Configuring it requires a matching bearer
token; see [interface authentication](interface/prd-i0-api.md).

<details>
<summary>Tests, console builds and process evaluations</summary>

Run the Python suites from the repository root with the virtual environment active:

```bash
python -m pytest -q agent/tests
python -m pytest -q dispatch/tests
python -m unittest evals.test_run_evals
```

Some tests require a configured controller or external dependencies; inspect
skips and environment requirements before treating results as live proof.

Build the console:

```bash
cd frontend
npm ci
npm run build
```

The build is written to `frontend/dist/`. For real-process evaluations with an
Ignis binary, follow [evals/README.md](evals/README.md). Those scenarios clone
pinned fixture repositories and are separate from the offline smoke.

</details>

## Project structure

```text
Raphael/
├── run.py             # Combined agent and dispatch entry point
├── agent/             # Graph, intake, diagnosis, localization and delivery
├── dispatch/          # Tenant job queue and connector protocol orchestration
├── contracts/         # Agent schemas and pinned Ignis contract snapshot
├── frontend/          # Vite operator console and brand assets
├── supabase/          # Catalog/telemetry migrations and setup guide
├── evals/             # Versioned scenarios and scoring
├── e2e/               # Cross-repository process and kind checks
└── docs/              # Pilot setup, acceptance evidence and operating notes
```

The active sandbox executor lives in Ignis, rather than Raphael's historical
`sandbox/` directory. Contract synchronization is handled by
[`tools/sync-sandbox-contracts.ps1`](tools/sync-sandbox-contracts.ps1).

## Configuration

The Python services read exported environment variables; they do not
automatically load `.env`. The supplied [`.env.example`](.env.example) covers
optional Supabase configuration. Vite loads its own frontend environment.

| Variable | Purpose |
| --- | --- |
| `RAPHAEL_AGENT_LISTEN` | Combined core address; defaults to `127.0.0.1:8091` |
| `RAPHAEL_AGENT_DATA_DIR` | Run-state directory; defaults to `.raphael-agent-data` |
| `RAPHAEL_AGENT_STORE` | `json` by default, or `sqlite` |
| `RAPHAEL_SANDBOX_URL` | External Ignis controller URL |
| `RAPHAEL_DISPATCH_BRIDGE_ENABLED` | Set to `1` to route supported intake into dispatch |
| `RAPHAEL_DISPATCH_TOKENS` | JSON bearer-to-tenant/role mapping for producers and connectors |
| `RAPHAEL_PARTNER_MODE`, `RAPHAEL_PUBLISH_MODE` | Delivery controls; use `dry_run` for local evaluation |
| `RAPHAEL_MODEL_ENABLED`, `RAPHAEL_LEARNING` | Keep `0` unless deliberately qualifying those paths |
| `RAPHAEL_LLM_DIAGNOSIS`, `RAPHAEL_LLM_PATCH` | Opt in to external model assistance |
| `RAPHAEL_LLM_PROVIDER`, `RAPHAEL_LLM_API_KEY`, `RAPHAEL_LLM_MODEL` | Provider, backend credential and optional pinned model |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY` | Optional backend catalog/telemetry access |
| `VITE_RAPHAEL_API_URL` | Console API base; unset selects demo mode |

See [agent configuration](agent/README.md), [Supabase setup](supabase/README.md)
and the [pilot guide](docs/pilot-install.md) for authentication and complete profiles.
Keep backend credentials out of browser bundles. Live GitHub publication needs
separate credentials and policy configuration; setting one publish flag is insufficient.

## Local model qualification

Measured on **251 source-linked public fixture inputs** through production graph
nodes and the production gateway, plus an actual compiled graph control. Local
inference remains **off by default**. The detailed [graph qualification report](docs/model-graph-qualification-65.md)
records inputs, outputs, artifact identities, timing methodology, safety gates and
separate live-environment evidence, including a passed model-enabled kind repair
with partial sandbox fidelity. These figures are fixture results, not
production accuracy or a rollout approval.

| Capability | Fixture result and limits | Learned / rule paths | Warm median / p95 |
| --- | --- | --- | --- |
| Failure classification | 40/40 emitted classifications match (100%); 40/50 overall (80%); 10 image-policy stops | 40 / 40 | 1.09 / 1.47 ms |
| Candidate ranking | 37/50 top-1 fix-file matches (74%); gateway projection of benchmark candidates | 50 / 0 | 1.00 / 1.11 ms |
| Incident similarity | 44/50 top-1 class matches (88%); queries overlap the owned fixture index | 50 / 0 | 3.16 / 3.52 ms |
| Trace anomaly | 38/50 fault-window matches (76%); weak per-trace labels | 50 / 15 | 2.09 / 2.17 ms |
| Patch selection | 12/50 safe-template hypothesis matches (24%); 41/51 outputs, 22 refusals; not repair accuracy | 1 / 40 | 0.66 / 0.69 ms |

[Hosted CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40354545306) supplies
the shown latency values (Linux, Python 3.12.15). Latency is for the measured warm
node/adapter call, including local catalog HTTP
where applicable. Rule paths can overlap final refusals. Effective overrides and abstentions are
reported separately; learned
execution does not mean the learned answer determined the final decision.

### Original-source development evaluation (#78, Phase 2)

The [paired development report](docs/model-readiness-phase-2.md) uses original
Kubernetes reports, reproduced Python failures and OpenRCA telemetry. All five
capabilities remain deferred; these results do not establish production accuracy.

| Capability | Model-off versus model-on result | Decision |
| --- | --- | --- |
| Classification | Same decisions on 6 reports; 2 policy stops, 4 model abstentions | More evidence needed |
| Ranking | Both: top-1 1/3, top-3 2/3; 0 wins, 3 ties, 0 regressions | No observed benefit |
| Similarity | 0 returned matches in 6 queries; relevance labels pending | More evidence needed |
| Trace anomaly | 3 native telemetry sources blocked on compatibility/baseline requirements | Not scored |
| Patch selection | 6 report precondition checks; 0 proposals or validated repairs | Not qualified |

## Roadmap

The [release milestones](docs/release-milestones-2026-10-18.md) track acceptance
beyond the existing implementation: live baseline qualification, measured
localization/calibration, learning evidence and partner-pilot acceptance.
See the [PRD](prd.md) for requirements and [handoff](handoff.md) for current evidence.

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and [CODING_RULE.md](CODING_RULE.md).
Keep changes focused, include regression/refusal coverage, and preserve the
boundary between the agent and sandbox executor. Contract changes originate
in Ignis before Raphael updates its pinned snapshot.

## License

[Apache License 2.0](LICENSE).

## Author

[AWaleed-Ahmed](https://github.com/AWaleed-Ahmed)

## Contributors

| Contributor | Role |
| --- | --- |
| [AmazingDude](https://github.com/AmazingDude) | Core contributor and maintainer |
