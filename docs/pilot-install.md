# Pilot install guide (Phase 5)

**Audience:** design-partner platform/SRE engineer installing Raphael for a dry-run pilot.
**Invariant:** production Kubernetes stays **read-only**; durable fixes are **draft GitHub PRs only** (no auto-merge).

Canonical demo target: ≤15 minutes to `success_draft_pr_ready` with dry-run publish.

---

## 1. Prerequisites

| Tool | Required? | Notes |
|------|-----------|--------|
| Python 3.12+ | Yes | Agent package under `agent/` |
| Rust / Cargo | For real sandbox controller | Mock backend needs cargo run |
| Docker + kind | Optional | Only for real local Kubernetes fidelity |
| GitHub PAT or App | Optional for dry-run | Required only for live draft PRs |
| kubectl / helm | Optional | kind backend |

Clone:

```bash
git clone https://github.com/AWaleed-Ahmed/Raphael.git
cd Raphael
```

---

## 2. Environment matrix

### Agent (partner-safe defaults)

| Variable | Pilot default | Meaning |
|----------|---------------|---------|
| `RAPHAEL_PARTNER_MODE` | `dry_run` | Always dry-run publish |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | Raw publish preference |
| `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` | _(empty)_ | Empty ⇒ **no** live PRs; set e.g. `probe_misconfiguration` when ready |
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Keep off unless explicitly enabling |
| `RAPHAEL_LLM_PATCH` | `0` | Route B model patches; requires diagnosis=1 + key |
| `RAPHAEL_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible root (Ollama/LM Studio OK) |
| `RAPHAEL_LLM_MODEL` | `gpt-4o-mini` | Model id for chat/completions |
| `RAPHAEL_OPENAI_API_KEY` / `OPENAI_API_KEY` | unset | Bearer token when LLM on |
| `RAPHAEL_ISSUE_TRIGGER_LABEL` | `raphael:fix` | Issues label that starts Route B |
| `RAPHAEL_DEFAULT_COMMIT_SHA` | unset | Fallback SHA if issue omits `raphael-sha:` |
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Sandbox controller |
| `RAPHAEL_AGENT_LISTEN` | `127.0.0.1:8091` | Webhook/metrics server |
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | RunStore |
| `RAPHAEL_GITHUB_WEBHOOK_SECRET` | unset locally | Set in partner env for HMAC |
| `RAPHAEL_GITHUB_COMMANDS` | `0` | `1` parses `/raphael` on `issue_comment` (default **off**) |
| `RAPHAEL_GITHUB_AUTO_COMMENTS` | inherit commands | Unset follows `COMMANDS`; terminal comments + labels + sticky footer |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` | `1` enables advisory Check `Raphael (advisory)` (does **not** inherit commands) |
| `RAPHAEL_MAX_WALL_SECONDS` | `1800` | Run wall budget |
| `RAPHAEL_MAX_PATCH_ATTEMPTS` | `3` | Patch budget |
| `RAPHAEL_MAX_DIAGNOSIS_ATTEMPTS` | `2` | Diagnosis budget |
| `RAPHAEL_SANDBOX_HTTP_TIMEOUT` | `180` | Client timeout |

### Enabling live draft PRs (allowlisted classes only)

```bash
# Windows PowerShell examples
$env:RAPHAEL_PARTNER_MODE="allowlist"
$env:RAPHAEL_PUBLISH_MODE="live"
$env:RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES="probe_misconfiguration"
$env:RAPHAEL_GITHUB_TOKEN="ghp_..."   # contents:write + pull_requests:write; NO merge admin
```

Live draft PR requires **all** of: partner `allowlist`, `PUBLISH_MODE=live`, non-empty allowlist containing the run’s `failure_class`, and a token.

### Sandbox controller

| Variable | Typical pilot | Meaning |
|----------|---------------|---------|
| `RAPHAEL_CLUSTER_BACKEND` | `mock` then `kind` | Mock first; kind for fidelity |
| `RAPHAEL_LISTEN` | `127.0.0.1:8090` | Controller bind |

See [`sandbox/README.md`](../sandbox/README.md) for full list.

---

## 3. Install agent

```bash
cd agent
py -3.12 -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e .
```

---

## 4. Run sandbox (mock → kind)

### Mock (no Docker) — Terminal 1

```bash
# from repo root
RAPHAEL_CLUSTER_BACKEND=mock # Ignis endpoint is configured through RAPHAEL_SANDBOX_URL \
  cargo run --manifest-path the separately deployed Ignis executor (https://github.com/AWaleed-Ahmed/Ignis)
```

### Kind (optional fidelity)

```bash
the authorized Ignis deployment procedure
RAPHAEL_SANDBOX_URL=https://<authorized-ignis-endpoint> # Ignis endpoint is configured through RAPHAEL_SANDBOX_URL \
  cargo run --manifest-path the separately deployed Ignis executor (https://github.com/AWaleed-Ahmed/Ignis)
```

Force-cleanup of sandboxes is **controller-side**: `POST /v1/admin/force-cleanup` (agent does not mutate clusters).

---

## 5. Raphael-core server (agent + dispatch) — Terminal 2

```bash
# from repo root
python run.py
# health: http://127.0.0.1:8091/health
# webhooks: http://127.0.0.1:8091/v1/webhooks/github
# dispatch queue: http://127.0.0.1:8091/v1/tenants/{tenant_id}/jobs/next
```

This starts both the agent webhook server and the dispatch orchestrator in a
single process, sharing one Orchestrator instance. The ingest→dispatch bridge
(`RAPHAEL_DISPATCH_BRIDGE_ENABLED=1`) submits jobs via direct Python call — no
HTTP overhead, no internal auth token needed (same trust domain).

> **Note:** This is the current single-process deployment model. Multi-process
> or multi-instance dispatch (with startup rehydration and durable lease
> ownership) is explicitly deferred future work. Do not run multiple instances
> of `run.py` without first implementing those features.

---

## 6. Partner dry-run smoke (≤15 min)

```bash
cd agent
$env:RAPHAEL_PARTNER_MODE="dry_run"
$env:RAPHAEL_PUBLISH_MODE="dry_run"
$env:RAPHAEL_LLM_DIAGNOSIS="0"

python -m raphael_agent.scripts.smoke --sandbox-mode recorded_stub
# Expect: status=success_draft_pr_ready
#         result_id=...
#         pull_request_url=...raphael_dry_run=1
#         publish_mode=dry_run

pytest -q
python -m raphael_agent.scripts.metrics
```

Or use the wrapper:

```bash
python -m raphael_agent.scripts.demo_partner
```

---

## 7. GitHub App / PAT (draft PR + optional GitHub-native)

**Webhook events** to subscribe on the App or repo webhook (`POST /v1/webhooks/github`):

| Event | Why |
|-------|-----|
| `workflow_run` | Route A ingest (CI failure) |
| `check_run` | Route A ingest (check failure) |
| `pull_request` | FR-065 feedback on close/merge/edit |
| `issues` | Route B (`raphael:fix` label) |
| `issue_comment` | GitHub-native commands (`/raphael …`) — parsed only if `RAPHAEL_GITHUB_COMMANDS=1` |

Leave `RAPHAEL_GITHUB_COMMANDS`, `RAPHAEL_GITHUB_AUTO_COMMENTS`, and `RAPHAEL_GITHUB_CHECK_RUNS` at default **off** until the partner opts in. Command parse does not run at `COMMANDS=0` even if `issue_comment` is delivered.

**PAT (fine-grained or classic):**

| Scope / permission | Required | Notes |
|--------------------|----------|--------|
| Contents: Read | Yes | Metadata / optional live commit |
| Contents: Read and write | Live draft only | Agent branch + commit only |
| Pull requests: Read and write | Live draft / labels | **Draft** PRs; additive GH-M3 labels |
| Issues: Read and write | Commands / Route B / sticky footer | `issue_comment` replies when commands are on |
| Checks: Read and write | **Optional** | Only if `RAPHAEL_GITHUB_CHECK_RUNS=1`; **never** a required merge check |
| Metadata: Read | Yes | |
| Administration / merge queue | **No** | Denied |
| Secrets | **No** | Denied |
| Environments (write) | **No** | Denied |
| Workflows (write) | **No** | Denied |

**GitHub App (pilot — same App as ingest):** permissions match [`interface/github-native/prd.md`](../interface/github-native/prd.md) §7.3 — Checks r/w optional, Issues r/w, Pull requests r/w, Metadata r, Actions r, Contents r (write only for live draft). **Must not request:** Administration, Secrets, Environments (write), Workflows (write). Optional App JWT: `RAPHAEL_GITHUB_APP_ID`, `RAPHAEL_GITHUB_INSTALLATION_ID`, `RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH` (PAT remains the documented dry-run path).

Live draft PR still requires **all** of: partner `allowlist`, `PUBLISH_MODE=live`, non-empty class allowlist, and a token. GitHub-native `retry` / `escalate` do **not** widen those gates.

---

## 8. Kubernetes permissions (evidence)

Production / customer cluster access for the **observer** identity:

| Verb | Resources | Allowed? |
|------|-----------|----------|
| get/list/watch | Pods, Events, Deployments, ReplicaSets, ReplicaSet status, Jobs | Yes (allowlisted namespaces) |
| get | ConfigMaps (non-secret config) | Yes if needed |
| get Secrets / read Secret payloads | Secrets | **Denied** |
| create/update/patch/delete | Any production resource | **Denied** |

Sandbox cluster writes are **only** via the sandbox controller identity — never from the agent process with a production kubeconfig.

Full matrix: [`permission-matrix.md`](permission-matrix.md).

---

## 9. Acceptance pointers

- Checklist: [`pilot-acceptance.md`](pilot-acceptance.md)
- Agent how-to: [`../agent/README.md`](../agent/README.md)
- Product rules: [`../CODING_RULE.md`](../CODING_RULE.md)
