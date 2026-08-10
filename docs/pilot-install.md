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
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Sandbox controller |
| `RAPHAEL_AGENT_LISTEN` | `127.0.0.1:8091` | Webhook/metrics server |
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | RunStore |
| `RAPHAEL_GITHUB_WEBHOOK_SECRET` | unset locally | Set in partner env for HMAC |
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
RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml
```

### Kind (optional fidelity)

```bash
./sandbox/kind/bootstrap.sh
RAPHAEL_CLUSTER_BACKEND=kind RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml
```

Force-cleanup of sandboxes is **controller-side**: `POST /v1/admin/force-cleanup` (agent does not mutate clusters).

---

## 5. Agent webhook server — Terminal 2

```bash
cd agent
# optional: $env:RAPHAEL_GITHUB_WEBHOOK_SECRET="..."
python -m raphael_agent.http_api.app
# health: http://127.0.0.1:8091/health
# metrics: http://127.0.0.1:8091/v1/metrics
```

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

## 7. GitHub scopes (draft PR only)

**PAT (fine-grained or classic):**

| Scope / permission | Required | Notes |
|--------------------|----------|--------|
| Contents: Read and write | Yes (live) | Agent branch + commit only |
| Pull requests: Read and write | Yes (live) | **Draft** PRs |
| Metadata: Read | Yes | |
| Administration / merge queue | **No** | Denied |
| Actions secrets | **No** | |

**GitHub App (when used):** same capabilities — create branches on agent refs, open draft PRs, no merge/admin. Optional: `RAPHAEL_GITHUB_APP_ID`, `RAPHAEL_GITHUB_INSTALLATION_ID`, `RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH` (JWT path reserved; PAT is the documented pilot path).

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
