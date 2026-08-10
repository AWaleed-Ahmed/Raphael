# Raphael Agent (Engineer B)

Phase 0 skeleton: LangGraph stub, sandbox HTTP client, and frozen contracts under [`contracts/agent/`](../contracts/agent/).

**Non-goals here:** real GitHub webhooks, K8s watcher, LLM diagnosis, opening PRs, production writes.

---

## Layout

```text
agent/
  pyproject.toml
  README.md
  fixtures/                 # fake failed-run event + recorded sandbox responses
  tests/
  raphael_agent/
    ingest/                 # event normalize (stub)
    evidence/               # evidence collection (stub)
    diagnosis/              # structured diagnosis (stub)
    patch/                  # constrained patch proposal (stub)
    publish/                # PR publish — no-op; requires result_id
    graph/                  # LangGraph happy-path stub
    sandbox_client/         # typed HTTP client → sandbox controller
    scripts/smoke.py        # smoke CLI
```

Graph nodes: `ingest → evidence → diagnose → reproduce → patch → validate → publish_or_escalate`

Terminal statuses: `success_draft_pr_ready` | `escalated` | `failed_closed`

---

## Setup

Use **Python 3.12+** (on Windows prefer `py -3.12` / the python.org install — MSYS Python may create a broken venv without `Scripts\pip`).

```bash
cd agent
py -3.12 -m venv .venv

# Windows
.venv\Scripts\activate
# Unix
# source .venv/bin/activate

pip install -e .
```

Default sandbox URL: `http://127.0.0.1:8090` (`RAPHAEL_SANDBOX_URL`).

---

## Smoke path

### Offline (controller down) — recorded stubs

Walks the stub graph using `fixtures/recorded_sandbox_responses.json`. No HTTP required.

```bash
cd agent
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
# or
pytest -q tests/test_smoke.py::test_smoke_graph_recorded_stub
```

### Auto (live if controller is up)

```bash
# Terminal 1 — from repo root
RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml

# Terminal 2
cd agent
python -m raphael_agent.scripts.smoke
# or force live:
python -m raphael_agent.scripts.smoke --sandbox-mode live
```

On `auto`, the runner calls `GET /health`. If reachable → live sandbox verbs against the mock controller (uses `sandbox/harness/scenarios/probe_port_mismatch`; validation plan omits Unix-only `true`). If not → recorded stubs and prints `sandbox_mode=recorded_stub`.

### pytest

```bash
cd agent
pytest -q
```

---

## Sandbox client

```python
from raphael_agent.sandbox_client import SandboxClient

client = SandboxClient()  # RAPHAEL_SANDBOX_URL or http://127.0.0.1:8090
client.health()
# create_sandbox / deploy_revision / observe_failure /
# run_validation / finalize_result / get_result / destroy_sandbox
```

Requests/responses are validated against `contracts/sandbox/` when `validate=True` (default).

---

## Phase 1 handoff (ingest)

See root session notes / `decision.md`. Next: real webhook intake + run correlation into `run_record`, still calling this graph entrypoint.
