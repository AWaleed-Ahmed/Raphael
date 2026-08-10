# Raphael Agent (Engineer B)

Phase 2: deterministic diagnosis + constrained patch loop. Phase 1 ingest + Phase 0 graph remain.

**Still non-goals:** opening GitHub PRs, K8s watcher, production writes. LLM diagnosis is **off by default**.

---

## Layout

```text
agent/
  pyproject.toml
  README.md
  fixtures/
  tests/
  raphael_agent/
    ingest/                 # GitHub HMAC, policy, accept/persist
    store/                  # durable JSON run_record
    evidence/               # adapters + redaction
    diagnosis/              # deterministic analyzers (+ optional LLM)
    patch/                  # fix templates + allowlist policy
    publish/                # PR publish — no-op; requires result_id
    graph/                  # LangGraph (validate may retry patch)
    sandbox_client/
    http_api/
    scripts/smoke.py
```

Graph: `ingest → evidence → diagnose → reproduce → patch → validate ⇄ patch → publish_or_escalate`

Terminals: `success_draft_pr_ready` | `escalated` | `failed_closed`

---

## Setup

```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e .
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Sandbox controller |
| `RAPHAEL_AGENT_LISTEN` | `127.0.0.1:8091` | Agent HTTP bind |
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | Run + raw event store |
| `RAPHAEL_GITHUB_WEBHOOK_SECRET` | unset | If set, require HMAC |
| `RAPHAEL_INGEST_COOLDOWN_SECONDS` | `900` | FR-006 cooldown |
| `RAPHAEL_INGEST_MAX_CONCURRENT_RUNS` | `2` | FR-006 concurrency |
| `RAPHAEL_INGEST_RUN_GRAPH` | unset | If `1`, webhook runs graph |
| `RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD` | `0.7` | Select hypothesis only above this |
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | `1` enables optional LLM refine |
| `RAPHAEL_OPENAI_API_KEY` / `OPENAI_API_KEY` | unset | Required only if LLM on |
| `RAPHAEL_MAX_PATCH_ATTEMPTS` | `3` | Patch loop budget |
| `RAPHAEL_PATCH_ALLOWLIST` | deploy/,k8s/,… | Comma-separated path prefixes |

---

## Smoke path

```bash
cd agent

# Offline — recorded sandbox stubs (no LLM)
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub

# Via ingest
python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub --via-ingest

# Live mock controller (optional)
# Terminal 1 (repo root):
#   RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 \
#     cargo run --manifest-path sandbox/controller/Cargo.toml
python -m raphael_agent.scripts.smoke --sandbox-mode live

pytest -q
```

Default pytest path does **not** call any LLM / API keys.

---

## GitHub webhook server

```bash
python -m raphael_agent.http_api.app
```

See Phase 1 notes in git history / `decision.md` D-20260810-03.

---

## Phase 3 handoff (validate + publish)

- Open **draft** GitHub PR from frozen sandbox `result_id` (GitHub App)
- PR body: diagnosis, evidence, validation matrix, risk, rollback
- Branch naming `raphael/<run-id>-<summary>`; still no production writes
- Keep publish gated on mandatory validation pass + `result_id`
- Optional: observe human/merge outcome later (FR-065)
