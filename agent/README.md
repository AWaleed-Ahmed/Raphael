# Raphael Agent (Engineer B)

Phase 4: budgets, injection resistance, operator metrics, demo polish.

**Still non-goals:** auto-merge, production cluster writes, K8s watcher. LLM **off** by default. Publish default **dry_run**.

---

## Layout

```text
agent/
  fixtures/injection/       # hostile evidence fixtures
  raphael_agent/
    budgets.py              # wall/attempt/cost ceilings
    metrics.py              # RunStore aggregates
    feedback.py             # FR-065 stub interface
    publish/ diagnosis/ patch/ ingest/ graph/ ...
    scripts/smoke.py | metrics.py
```

---

## Setup

```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### Key env vars

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | `dry_run` \| `live` |
| `RAPHAEL_MAX_WALL_SECONDS` | `1800` | Graph wall-clock budget |
| `RAPHAEL_MAX_DIAGNOSIS_ATTEMPTS` | `2` | Diagnosis attempt cap |
| `RAPHAEL_MAX_PATCH_ATTEMPTS` | `3` | Patch loop budget |
| `RAPHAEL_MAX_COST_USD` | `0` | Cost ceiling (`0` = disabled) |
| `RAPHAEL_SANDBOX_HTTP_TIMEOUT` | `180` | Sandbox client timeout (s) |
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Optional LLM refine |
| `RAPHAEL_GITHUB_TOKEN` | unset | Live publish only |
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | RunStore root |

Budget exhaust → `escalated` / `failed_closed` with `escalation_report` — **never** speculative publish.

Sandbox namespace cleanup stays on the controller (`POST /v1/admin/force-cleanup`); the agent only reports metrics.

---

## Canonical demo (≤15 min, reviewer checklist)

Probe-port happy path with **recorded sandbox stubs** + **dry-run draft PR** (no Docker, no GitHub token):

```bash
cd agent
set RAPHAEL_PUBLISH_MODE=dry_run
set RAPHAEL_LLM_DIAGNOSIS=0

python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
# Expect: status=success_draft_pr_ready, result_id, pull_request_url with raphael_dry_run=1

pytest -q
python -m raphael_agent.scripts.metrics
# or: curl -s http://127.0.0.1:8091/v1/metrics   (with agent serve running)
```

Optional live sandbox (mock controller) — Terminal 1 from repo root:

```bash
RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml
```

Terminal 2:

```bash
cd agent
python -m raphael_agent.scripts.smoke --sandbox-mode live
```

Smoke prints: `run_id`, `fingerprint`, `result_id`, `pull_request_url`, `publish_mode`, `terminal_reason`, budget deadline.

---

## Operator metrics

```bash
python -m raphael_agent.scripts.metrics
python -m raphael_agent.scripts.metrics --json

# HTTP
python -m raphael_agent.http_api.app
curl -s http://127.0.0.1:8091/v1/metrics
```

---

## Phase 5 / pilot handoff

- Partner install path + permission matrix (read-only prod K8s; GitHub draft-only)
- Dry-run partner mode (diagnosis + sandbox validate, publish dry_run)
- Allowlisted failure classes for live draft PRs
- Optional App JWT + CODEOWNERS reviewers; FR-065 feedback recording beyond stub
