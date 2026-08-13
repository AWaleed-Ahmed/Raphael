# Raphael Interface — Usage (CLI)

**Audience:** operators, FDEs, and engineers using Raphael **today**  
**Status:** CLI is the full operator path. GitHub-native **GH-M1–M4** (`status` / `help` / `feedback` / `retry` / `escalate` + labels/sticky footer + opt-in Check Runs) is in the agent behind default-off knobs. IDE P0 is a VSIX — [`IDE/README.md`](IDE/README.md).  
**Requires:** Python 3.12+, repo checkout, optional kind + sandbox controller for live mode  

GitHub `cancel` / `diagnose` / `fix` are **not implemented**. Everything below uses the **agent CLI** and **agent HTTP API** — the same backends GitHub commands and the IDE call.

For product intent, see [`README.md`](README.md) and the PRDs. For agent env reference, see [`../agent/README.md`](../agent/README.md).

---

## Table of contents

1. [Mental model](#1-mental-model)  
2. [One-time setup](#2-one-time-setup)  
3. [Command map](#3-command-map)  
4. [Safe pilot loop (recommended)](#4-safe-pilot-loop-recommended)  
5. [Smoke & partner demo](#5-smoke--partner-demo)  
6. [Live sandbox (kind)](#6-live-sandbox-kind)  
7. [Serve the agent HTTP API](#7-serve-the-agent-http-api) (includes [I0 action API](#i0-action-api-served))  
8. [Feedback (accept / reject / merge)](#8-feedback-accept--reject--merge)  
9. [Learning loop](#9-learning-loop)  
10. [Metrics & go/no-go](#10-metrics--gono-go)  
11. [Dual-path reminders (CI vs Issues)](#11-dual-path-reminders-ci-vs-issues)  
12. [Environment cheat sheet](#12-environment-cheat-sheet)  
13. [Mapping CLI → future GitHub / IDE](#13-mapping-cli--future-github--ide)  
14. [Troubleshooting](#14-troubleshooting)  

---

## 1. Mental model

```text
You (CLI) ──► Agent (diagnose / patch / publish gates)
                  │
                  ├──► Sandbox controller :8090   (only if sandbox_mode=live)
                  └──► GitHub                 (only if live publish / live comments)
```

| Terminal status | Meaning |
|-----------------|---------|
| `success_draft_pr_ready` | Route A: draft PR (or dry-run compare URL) ready |
| `success_fix_proposed` | Route B: fix snippet posted/prepared; **you** open the PR |
| `escalated` | Safe stop — needs human; no forced speculative fix |
| `failed_closed` | Hard fail (policy, budget, sandbox, etc.) |
| `pending` / `running` | Ingested or in graph |

Default posture for pilots: **`RAPHAEL_PARTNER_MODE=dry_run`** and **`RAPHAEL_PUBLISH_MODE=dry_run`**. That never opens a live GitHub PR even if other knobs look “live.”

---

## 2. One-time setup

From the repo root:

```bash
cd /path/to/Raphael/agent

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e .

# Optional: isolate run/feedback files from other experiments
export RAPHAEL_AGENT_DATA_DIR="$PWD/.raphael-agent-data-local"
mkdir -p "$RAPHAEL_AGENT_DATA_DIR"
```

Verify entry points (either form works after `pip install -e .`):

```bash
raphael-agent-go-nogo --help
# same as:
python -m raphael_agent.scripts.pilot_go_nogo --help
```

| Console script | Module form |
|----------------|-------------|
| `raphael-agent-smoke` | `python -m raphael_agent.scripts.smoke` |
| `raphael-agent-demo` | `python -m raphael_agent.scripts.demo_partner` |
| `raphael-agent-go-nogo` | `python -m raphael_agent.scripts.pilot_go_nogo` |
| `raphael-agent-feedback` | `python -m raphael_agent.scripts.record_feedback` |
| `raphael-agent-metrics` | `python -m raphael_agent.scripts.metrics` |
| `raphael-agent-learn` | `python -m raphael_agent.scripts.learn` |
| `raphael-agent-serve` | `python -m raphael_agent.http_api.app` |

Also useful (module only):

```bash
python -m raphael_agent.scripts.pilot_local_preflight
```

---

## 3. Command map

| Goal | Command |
|------|---------|
| Check env is safe for pilot | `raphael-agent-go-nogo` |
| Day-0 local proof (go-nogo + demo + pytest + metrics) | `python -m raphael_agent.scripts.pilot_local_preflight` |
| Full dry-run remediation demo | `raphael-agent-demo` |
| Smoke with stub or live sandbox | `raphael-agent-smoke [--sandbox-mode …]` |
| Start webhook / run HTTP API | `raphael-agent-serve` |
| Record human / deploy outcome | `raphael-agent-feedback --outcome …` |
| Aggregate run stats | `raphael-agent-metrics` |
| Rebuild learning priors | `raphael-agent-learn` |
| Run agent tests | `pytest -q` (from `agent/`) |

---

## 4. Safe pilot loop (recommended)

Copy-paste sequence for a clean laptop demo (no GitHub token, no kind required):

```bash
cd agent
source .venv/bin/activate

# 1) Confirm safe gates
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_PUBLISH_MODE=dry_run
unset RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES
unset RAPHAEL_AUTO_MERGE
export RAPHAEL_LLM_DIAGNOSIS=0
export RAPHAEL_LLM_PATCH=0

raphael-agent-go-nogo
# expect: go=True / recommendation contains GO

# 2) Run the partner dry-run graph (recorded sandbox stubs)
raphael-agent-demo
# expect:
#   status=success_draft_pr_ready
#   pull_request_url=...&raphael_dry_run=1
#   result_id=res-recorded-001   (or similar)

# 3) Optional: full local preflight (includes pytest)
python -m raphael_agent.scripts.pilot_local_preflight

# 4) Inspect aggregates
raphael-agent-metrics
```

If go/no-go fails, **do not** flip publish to live. Fix the failing check first (`raphael-agent-go-nogo --json` for machine-readable detail).

---

## 5. Smoke & partner demo

### 5.1 Partner demo (always dry-run publish)

Forces partner/publish dry-run for the process, then runs the probe-port-mismatch fixture through the graph with **recorded_stub** sandbox responses.

```bash
cd agent
source .venv/bin/activate
raphael-agent-demo
```

Typical success lines:

```text
status=success_draft_pr_ready
result_id=res-recorded-001
pull_request_url=https://github.com/...&raphael_dry_run=1
publish_mode=dry_run dry_run=True draft=True
```

### 5.2 Smoke runner

```bash
# Auto: live sandbox if http://127.0.0.1:8090/health is up, else recorded_stub
raphael-agent-smoke

# Force stub (no controller needed)
raphael-agent-smoke --sandbox-mode recorded_stub

# Force live controller (kind + controller must be up)
raphael-agent-smoke --sandbox-mode live

# Persist through ingest policy (RunStore + cooldown rules)
raphael-agent-smoke --via-ingest

# Machine-readable final run_record
raphael-agent-smoke --sandbox-mode recorded_stub --json | head
```

| Flag | Meaning |
|------|---------|
| `--sandbox-mode auto` | Default — probe controller health |
| `--sandbox-mode live` | Call real sandbox verbs on `RAPHAEL_SANDBOX_URL` |
| `--sandbox-mode recorded_stub` | Deterministic fixtures; offline |
| `--via-ingest` | `accept_and_run_graph` (fingerprint, cooldown, store) |
| `--json` | Print full run JSON |

---

## 6. Live sandbox (kind)

Only needed when you want real reproduce/validate against a cluster.

**Terminal A — sandbox controller** (from repo root):

```bash
# kind cluster should already exist (name raphael-sandbox)
export RAPHAEL_CLUSTER_BACKEND=kind
export RAPHAEL_KUBE_CONTEXT=kind-raphael-sandbox
export RAPHAEL_LISTEN=127.0.0.1:8090

cargo run --manifest-path sandbox/controller/Cargo.toml
# wait for: sandbox controller listening … backend=kind
```

**Terminal B — agent**:

```bash
cd agent
source .venv/bin/activate

export RAPHAEL_SANDBOX_URL=http://127.0.0.1:8090
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_PUBLISH_MODE=dry_run

curl -sS "$RAPHAEL_SANDBOX_URL/health"
raphael-agent-smoke --sandbox-mode live
```

Kind-gated tests (optional):

```bash
cd agent
RAPHAEL_SANDBOX_URL=http://127.0.0.1:8090 pytest -m kind -v
```

Remember: the **CLI still does not call the sandbox** for publish — only the agent graph does, when `sandbox_mode=live`.

---

## 7. Serve the agent HTTP API

Start the HTTP surface that GitHub webhooks (and later interface packages) hit:

```bash
cd agent
source .venv/bin/activate

export RAPHAEL_AGENT_DATA_DIR="$PWD/.raphael-agent-data-local"
export RAPHAEL_PARTNER_MODE=dry_run
export RAPHAEL_PUBLISH_MODE=dry_run
export RAPHAEL_AGENT_LISTEN=127.0.0.1:8091   # default if unset

# Optional: require bearer even on loopback (recommended when RAPHAEL_INTERFACE_TOKEN is set)
# export RAPHAEL_INTERFACE_TOKEN='…'
# Non-loopback binds MUST set RAPHAEL_INTERFACE_TOKEN (I0 lock — enforced when auth middleware lands)

# Optional: auto-run graph on webhook (off by default — ingest only → pending)
# export RAPHAEL_INGEST_RUN_GRAPH=1
# export RAPHAEL_AGENT_SANDBOX_MODE=recorded_stub   # or live

raphael-agent-serve
```

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/webhooks/github` | POST | CI / PR / Issue events |
| `/v1/webhooks/k8s` | POST | Workload health (needs `RAPHAEL_K8S_WATCHER=1`) |
| `/v1/runs/{run_id}` | GET | Fetch run record |
| `/v1/feedback` | POST | Same as CLI feedback |
| `/v1/metrics` | GET | Metrics JSON |
| `/v1/pilot/go-nogo` | GET | Pilot gate JSON |
| `/v1/runs` | GET | List runs (I0) |
| `/v1/runs` | POST | Manual create run (I0) |
| `/v1/runs/{id}/actions` | POST | retry / escalate / cancel / feedback (I0) |

### I0 action API (served)

Contract: [`prd-i0-api.md`](prd-i0-api.md). Decisions: `D-20260811-01`, `D-20260811-02`.

```bash
# List
curl -sS "http://127.0.0.1:8091/v1/runs?owner=raphael&repo=demo&limit=20"

# Create (runs graph by default unless RAPHAEL_MANUAL_RUN_GRAPH=0)
curl -sS -X POST "http://127.0.0.1:8091/v1/runs" \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_kind": "manual_ui",
    "action_id": "demo-create-1",
    "repository": {"owner": "raphael", "name": "demo"},
    "commit_sha": "abcdef1234567",
    "workspace_path": "'"$PWD"'/../sandbox/harness/scenarios/probe_port_mismatch",
    "manifests": {"type": "yaml", "path": "deploy/manifests", "fixed_path": "deploy/manifests_fixed"},
    "sandbox_mode": "recorded_stub"
  }'

# Action retry (set RAPHAEL_INTERFACE_TOKEN + Bearer when token is configured)
curl -sS -X POST "http://127.0.0.1:8091/v1/runs/<run_id>/actions" \
  -H "Content-Type: application/json" \
  -d '{"verb":"retry","action_id":"demo-retry-1","sandbox_mode":"recorded_stub"}'
```

### Example: inspect a run

```bash
# after a webhook or smoke --via-ingest created a run_id
curl -sS "http://127.0.0.1:8091/v1/runs/<run_id>" | python -m json.tool | less
```

### Example: GitHub workflow_run failure (local fixture)

```bash
curl -sS -X POST "http://127.0.0.1:8091/v1/webhooks/github" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -H "X-GitHub-Delivery: local-demo-1" \
  --data-binary @fixtures/github_workflow_run_failure.json
```

Without `RAPHAEL_INGEST_RUN_GRAPH=1`, expect `status=pending` (ingest only).  
With it set, expect a terminal status from the graph (`success_*` / `escalated` / `failed_closed`).

### Auto-detect reality check

A deployment failure is **not** detected by magic:

1. Something must **POST** a webhook (or you run CLI fixtures), **and**  
2. Optional: `RAPHAEL_INGEST_RUN_GRAPH=1` to run the graph immediately, **and**  
3. For live sandbox: `RAPHAEL_AGENT_SANDBOX_MODE=live` + controller up.

---

## 8. Feedback (accept / reject / merge)

Feedback is how humans teach Raphael (FR-065). It feeds the offline learning loop.

```bash
raphael-agent-feedback --help
```

### Record outcomes

```bash
# Reviewer likes the draft
raphael-agent-feedback \
  --outcome accepted \
  --run-id agent-smoke-001 \
  --failure-class probe_misconfiguration \
  --owner raphael --repo demo \
  --notes "lgtm — probe port was wrong"

# Reviewer rejects
raphael-agent-feedback \
  --outcome rejected \
  --run-id agent-smoke-001 \
  --failure-class probe_misconfiguration \
  --notes "wrong root cause"

# PR merged on GitHub
raphael-agent-feedback \
  --outcome merged \
  --pr-number 42 \
  --owner raphael --repo demo \
  --failure-class probe_misconfiguration

# Post-merge deploy observation
raphael-agent-feedback --outcome deploy_succeeded --run-id agent-smoke-001
raphael-agent-feedback --outcome deploy_failed --run-id agent-smoke-001 --notes "still CrashLoop"
```

| Flag | Use |
|------|-----|
| `--outcome` | Required — see help for enum |
| `--run-id` | Tie to agent run |
| `--result-id` | Sandbox result if known |
| `--pr-url` / `--pr-number` | GitHub PR identity |
| `--owner` / `--repo` | Repository |
| `--failure-class` | Important for learning buckets |
| `--actor` | Who recorded |
| `--notes` | Free text (keep free of secrets) |
| `--json` | Print the stored event |

Events append to:

```text
$RAPHAEL_AGENT_DATA_DIR/feedback.jsonl
```

HTTP equivalent while serve is running:

```bash
curl -sS -X POST "http://127.0.0.1:8091/v1/feedback" \
  -H "Content-Type: application/json" \
  -d '{
    "outcome": "rejected",
    "run_id": "agent-smoke-001",
    "failure_class": "probe_misconfiguration",
    "source": "manual",
    "notes": "from curl"
  }'
```

`pull_request` GitHub webhooks (closed/merged/edited) also append feedback when the agent receive them.

---

## 9. Learning loop

Learning is **offline** and **off by default**. It never widens allowlists or auto-merges.

```bash
cd agent
source .venv/bin/activate
export RAPHAEL_AGENT_DATA_DIR="$PWD/.raphael-agent-data-local"

# After you have ≥ RAPHAEL_LEARNING_MIN_SAMPLES (default 3) per class:
raphael-agent-learn
# or:
raphael-agent-learn --min-samples 3 --out "$RAPHAEL_AGENT_DATA_DIR/learning_snapshot.json"

# Apply on subsequent runs
export RAPHAEL_LEARNING=1
export RAPHAEL_LEARNING_SNAPSHOT="$RAPHAEL_AGENT_DATA_DIR/learning_snapshot.json"

raphael-agent-demo
# diagnosis may include a "learning" audit block; heavy rejects → escalate sooner
```

| Step | Command |
|------|---------|
| Collect | `raphael-agent-feedback --outcome …` |
| Build snapshot | `raphael-agent-learn` |
| Enable | `export RAPHAEL_LEARNING=1` |
| Observe | Next `demo` / `smoke` / webhook graph run |

---

## 10. Metrics & go/no-go

```bash
# Human-readable
raphael-agent-go-nogo
raphael-agent-metrics

# JSON
raphael-agent-go-nogo --json
raphael-agent-metrics --json

# HTTP (serve must be up)
curl -sS "http://127.0.0.1:8091/v1/pilot/go-nogo" | python -m json.tool
curl -sS "http://127.0.0.1:8091/v1/metrics" | python -m json.tool
```

Go/no-go checks partner mode, empty live allowlist, no auto-merge, LLM off for pilot, etc. Treat **NO-GO** as a hard stop for partner demos.

---

## 11. Dual-path reminders (CI vs Issues)

| Route | Trigger | CLI relevance |
|-------|---------|----------------|
| **A — CI** | `workflow_run` / `check_run` / deployment-status webhook | Use `serve` + fixtures, or `smoke` / `demo_partner` |
| **B — Issues** | Issue labeled `raphael:fix` (configurable) | Needs live GitHub + token for real comments; snippet → human opens PR |

Issue body helpers (when using Route B against GitHub):

```text
raphael-sha: <commit>
raphael-failure-class: probe_misconfiguration
```

Optional LLM (off by default):

```bash
export RAPHAEL_LLM_DIAGNOSIS=1
export RAPHAEL_LLM_PATCH=1
export RAPHAEL_LLM_BASE_URL=http://127.0.0.1:11434/v1
export RAPHAEL_LLM_MODEL=llama3.2
export RAPHAEL_OPENAI_API_KEY=ollama
```

### Flip one class to live draft PR (after security review)

```bash
export RAPHAEL_PARTNER_MODE=allowlist
export RAPHAEL_PUBLISH_MODE=live
export RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES=probe_misconfiguration
export RAPHAEL_GITHUB_TOKEN=ghp_...   # or App installation token path

raphael-agent-go-nogo    # must still make sense for your org
# then run graph / webhook as usual
```

If allowlist is empty, code **forces dry-run** even when publish says live.

---

## 12. Environment cheat sheet

| Variable | Default | CLI impact |
|----------|---------|------------|
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | Runs, feedback, learning files |
| `RAPHAEL_PARTNER_MODE` | `dry_run` | `dry_run` \| `allowlist` \| `diagnosis_only` |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | Gated by partner mode |
| `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` | empty | Empty ⇒ no live PRs |
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Live smoke / live graph |
| `RAPHAEL_AGENT_LISTEN` | `127.0.0.1:8091` | `raphael-agent-serve` bind |
| `RAPHAEL_INTERFACE_TOKEN` | unset | I0: required for non-loopback agent API |
| `RAPHAEL_GITHUB_COMMANDS` | `0` | `1` enables in-agent `/raphael` comment commands |
| `RAPHAEL_GITHUB_COMMAND_PREFIX` | `/raphael` | Command prefix |
| `RAPHAEL_GITHUB_COMMAND_TEAM` | unset | Privileged verbs (admin or these logins/slug) |
| `RAPHAEL_GITHUB_COMMAND_RATE_LIMIT` | `10` | Per repo+actor per hour |
| `RAPHAEL_GITHUB_AUTO_COMMENTS` | inherit commands | Terminal comments + GH-M3 labels/sticky footer; unset follows `COMMANDS` |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` | `1` enables advisory Check Runs (does not inherit commands) |
| `RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS` | `0` | Opt-in `success` conclusion on happy terminals only |
| `RAPHAEL_INGEST_RUN_GRAPH` | off | Webhook auto-runs graph |
| `RAPHAEL_AGENT_SANDBOX_MODE` | `skipped` | Mode used when webhook autorun |
| `RAPHAEL_K8S_WATCHER` | `0` | Enable `/v1/webhooks/k8s` |
| `RAPHAEL_LEARNING` | `0` | Apply learning snapshot |
| `RAPHAEL_LEARNING_SNAPSHOT` | under data dir | Snapshot path |
| `RAPHAEL_LEARNING_MIN_SAMPLES` | `3` | Learner threshold |
| `RAPHAEL_GITHUB_TOKEN` | unset | Live draft / live issue comments |
| `RAPHAEL_LLM_*` | off | Optional model path |

---

## 13. Mapping CLI → future GitHub / IDE

Use this table when the UIs land — behavior should stay equivalent.

| Human intent | CLI now | GitHub-native | IDE |
|--------------|---------|---------------|-----|
| “Is pilot config safe?” | `raphael-agent-go-nogo` | `/raphael help` (GH-M1; shows mode) | Pilot / status bar |
| “Run the happy path” | `raphael-agent-demo` | Label + webhook / `/raphael diagnose` (**not implemented**) | Start Diagnosis |
| “Show me this run” | `smoke --json` / `GET /v1/runs/{id}` | `/raphael status` (GH-M1) | Open Run |
| “I accept / merged” | `--outcome accepted\|merged` | `/raphael feedback accepted` (GH-M1) + PR webhook | Feedback Accepted |
| “I reject this fix” | `raphael-agent-feedback --outcome rejected` | `/raphael feedback rejected` (GH-M1) | Feedback Rejected |
| “Apply the snippet” | manual edit / copy from Issue | comment + IDE deep link | **Apply Fix from Run** |
| “Retry” | re-run smoke / new webhook | `/raphael retry` (GH-M2; not while in-flight) | Manual trigger |
| “Learn from history” | `raphael-agent-learn` | (ops job; not a chat command that widens policy) | read-only badge |

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `go=False` on go-nogo | Live allowlist / LLM / auto-merge mis-set | Reset to dry-run pilot env (§4) |
| Smoke hangs / connection errors in `live` | Controller down | Start sandbox on `:8090` or use `--sandbox-mode recorded_stub` |
| Webhook returns `pending` only | Autorun off | Expected; set `RAPHAEL_INGEST_RUN_GRAPH=1` to run graph |
| No live PR created | Partner/publish gates | Empty live class allowlist forces dry-run — intentional |
| Feedback “not learning” | `RAPHAEL_LEARNING=0` or &lt; min samples | Record ≥3 outcomes/class, run `learn`, set `RAPHAEL_LEARNING=1` |
| `pytest` kind tests skipped | No controller | Start kind controller or ignore `-m kind` |
| Permission denied on GitHub | Missing token | Set `RAPHAEL_GITHUB_TOKEN` only after go-nogo + security review |

---

## Quick reference card

```bash
cd agent && source .venv/bin/activate

export RAPHAEL_PARTNER_MODE=dry_run RAPHAEL_PUBLISH_MODE=dry_run

raphael-agent-go-nogo
raphael-agent-demo
raphael-agent-metrics

raphael-agent-feedback --outcome rejected --run-id agent-smoke-001 \
  --failure-class probe_misconfiguration --notes "demo reject"

raphael-agent-learn
export RAPHAEL_LEARNING=1

raphael-agent-serve   # RAPHAEL_AGENT_LISTEN=127.0.0.1:8091
```

**Next interfaces:** [`README.md`](README.md) · [`github-native/prd.md`](github-native/prd.md) · [`IDE/prd.md`](IDE/prd.md)
