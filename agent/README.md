# Raphael Agent (Engineer B)

Phase 1 ingest + Phase 0 LangGraph stub. Sandbox HTTP client talks to the frozen controller under `sandbox/`.

**Non-goals still:** K8s watcher, LLM diagnosis, opening PRs, production writes.

---

## Layout

```text
agent/
  pyproject.toml
  README.md
  fixtures/                 # fixture + GitHub webhook samples + recorded sandbox
  tests/
  raphael_agent/
    ingest/                 # normalize, GitHub HMAC, policy, accept/persist
    store/                  # durable JSON run_record + ingest decisions
    evidence/               # adapters + redaction + fixture stub
    diagnosis/              # structured diagnosis (stub)
    patch/                  # constrained patch proposal (stub)
    publish/                # PR publish — no-op; requires result_id
    graph/                  # LangGraph happy-path stub
    sandbox_client/         # typed HTTP client → sandbox controller
    http_api/               # /health + GitHub webhook + GET run
    scripts/smoke.py        # smoke CLI
```

Graph nodes: `ingest → evidence → diagnose → reproduce → patch → validate → publish_or_escalate`

Terminal statuses: `success_draft_pr_ready` | `escalated` | `failed_closed`

Ingest decisions: `accepted` | `ignored` | `duplicate` | `cooldown` | `concurrency_limit` | `unauthorized` | `invalid`

---

## Setup

Use **Python 3.12+**.

```bash
cd agent
py -3.12 -m venv .venv

# Windows
.venv\Scripts\activate
# Unix
# source .venv/bin/activate

pip install -e .
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Sandbox controller |
| `RAPHAEL_AGENT_LISTEN` | `127.0.0.1:8091` | Agent HTTP bind |
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | Run + raw event store |
| `RAPHAEL_GITHUB_WEBHOOK_SECRET` | unset | If set, require `X-Hub-Signature-256` |
| `RAPHAEL_INGEST_COOLDOWN_SECONDS` | `900` | FR-006 cooldown |
| `RAPHAEL_INGEST_MAX_CONCURRENT_RUNS` | `2` | FR-006 concurrency |
| `RAPHAEL_INGEST_RUN_GRAPH` | unset | If `1`, webhook also runs stub graph |
| `RAPHAEL_AGENT_TENANT_ID` | `local-dev` | Tenant for fingerprints |

---

## Smoke path

### Offline graph (Phase 0 path)

```bash
cd agent
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
```

### Via Phase 1 ingest (persist + policy + graph)

```bash
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub --via-ingest
```

### Live sandbox (optional)

```bash
# Terminal 1 — repo root
RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml

# Terminal 2
cd agent
python -m raphael_agent.scripts.smoke --sandbox-mode live
```

### pytest

```bash
cd agent
pytest -q
```

---

## GitHub webhook server

```bash
cd agent
# optional: set RAPHAEL_GITHUB_WEBHOOK_SECRET
python -m raphael_agent.http_api.app
# or: raphael-agent-serve
```

```bash
curl -s -X POST http://127.0.0.1:8091/v1/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -H "X-GitHub-Delivery: local-1" \
  --data-binary @fixtures/github_workflow_run_failure.json
```

Supported events: `workflow_run`, `check_run`, `deployment_status` (failure/error only).  
K8s watcher: not in Phase 1.

---

## Phase 2 handoff (diagnose + patch)

- Real deterministic analyzers + structured LLM hypotheses (still schema-bound)
- Constrained patch workspace generation (diagnosis/patch leave stub mode)
- Optional LangGraph checkpointer; keep `run_record` as inspectable source of truth
- Evidence: optional GitHub Actions API log download behind the existing adapter
- Do not open PRs yet; publish stays gated on sandbox `result_id`
