# Raphael Agent (Engineer B)

Phase 6 dual-path: **Route A** CI templates → draft PR; **Route B** labeled Issues → optional custom model → fix snippet (developer opens the PR).

**Still non-goals:** auto-merge, production cluster writes. K8s watcher is opt-in (`RAPHAEL_K8S_WATCHER=1`). LLM **off** by default.

Pilot docs:

- [`docs/pilot-install.md`](../docs/pilot-install.md)
- [`docs/permission-matrix.md`](../docs/permission-matrix.md)
- [`docs/pilot-acceptance.md`](../docs/pilot-acceptance.md)
- [`docs/pilot-week-runbook.md`](../docs/pilot-week-runbook.md) ← **5-day plan**

---

## Dual path

| Route | Trigger | Patch source | Delivery |
|-------|---------|--------------|----------|
| **A — CI** | `workflow_run` / `check_run` / deployment-status | Deterministic templates | Draft PR (partner dry-run / allowlist) |
| **B — Issues** | `issues` with `RAPHAEL_ISSUE_TRIGGER_LABEL` (default `raphael:fix`) | Optional model (`RAPHAEL_LLM_PATCH`) or template if `raphael-failure-class:` set | Issue comment with fix snippet; **human opens PR** |

Issue body helpers:

```text
raphael-sha: <commit>
raphael-failure-class: probe_misconfiguration
```

Fix rules: `.raphael/issue-fix.yaml` if present; otherwise derived from `.raphael/config.yaml`, `CONTRIBUTING.md`, `CODEOWNERS` (cannot widen global allowlist).

---

## Setup

```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### Partner / publish env

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_PARTNER_MODE` | `dry_run` | `dry_run` \| `allowlist` \| `diagnosis_only` |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | Raw preference; gated by partner mode |
| `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` | _(empty)_ | Empty ⇒ **no** live PRs; e.g. `probe_misconfiguration` |
| `RAPHAEL_GITHUB_TOKEN` | unset | Required for live draft / live issue comments |
| `RAPHAEL_GITHUB_REVIEWERS` | unset | Optional reviewer logins |
| `RAPHAEL_ISSUE_TRIGGER_LABEL` | `raphael:fix` | Route B label |
| `RAPHAEL_K8S_WATCHER` | `0` | Enable `POST /v1/webhooks/k8s` (FR-002) |
| `RAPHAEL_AGENT_STORE` | `json` | `json` \| `sqlite` |
| `RAPHAEL_REVIEWERS_FROM_CODEOWNERS` | `0` | Merge CODEOWNERS user logins into PR reviewers |
| `RAPHAEL_LEARNING` | `0` | Apply offline learning_snapshot priors |
| `RAPHAEL_LEARNING_MIN_SAMPLES` | `3` | Min feedback samples per class before prior |
| `RAPHAEL_LEARNING_SNAPSHOT` | data dir file | Path to frozen snapshot |

### Learning loop (Post-MVP; off by default)

```bash
# 1) Collect feedback during/after runs (already wired)
python -m raphael_agent.scripts.record_feedback --outcome merged --run-id ...

# 2) Rebuild offline priors (does not change live policy/allowlists)
python -m raphael_agent.scripts.learn

# 3) Apply on subsequent runs
export RAPHAEL_LEARNING=1
python -m raphael_agent.scripts.demo_partner
```

Priors nudge diagnosis confidence / escalate sooner on chronically rejected classes, and can demote weak templates. Still draft-PR / human merge only.

### Optional model (OpenAI-compatible, including local)

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Enable LLM diagnosis refine |
| `RAPHAEL_LLM_PATCH` | `0` | Enable Route B model patches (also needs diagnosis=1) |
| `RAPHAEL_LLM_BASE_URL` | `https://api.openai.com/v1` | API root; client POSTs `{base}/chat/completions` |
| `RAPHAEL_LLM_MODEL` | `gpt-4o-mini` | Model name |
| `RAPHAEL_OPENAI_API_KEY` or `OPENAI_API_KEY` | unset | Bearer token (required when LLM on) |

Local example (Ollama):

```bash
export RAPHAEL_LLM_DIAGNOSIS=1
export RAPHAEL_LLM_PATCH=1
export RAPHAEL_LLM_BASE_URL=http://127.0.0.1:11434/v1
export RAPHAEL_LLM_MODEL=llama3.2
export RAPHAEL_OPENAI_API_KEY=ollama
```

Live draft PR only when: `PARTNER_MODE=allowlist` **and** `PUBLISH_MODE=live` **and** class allowlisted **and** token present.

---

## Partner dry-run demo (≤15 min)

```bash
cd agent
python -m raphael_agent.scripts.demo_partner
python -m raphael_agent.scripts.pilot_go_nogo
pytest -q
python -m raphael_agent.scripts.metrics
```

Expect `status=success_draft_pr_ready`, `result_id`, `pull_request_url` with `raphael_dry_run=1`.

---

## Feedback (FR-065 audit)

```bash
python -m raphael_agent.scripts.record_feedback --outcome accepted --run-id ... --notes "lgtm"
python -m raphael_agent.scripts.record_feedback --outcome merged --pr-number 12 --owner raphael --repo demo
# HTTP: POST /v1/feedback
# Webhook: X-GitHub-Event: pull_request (closed/merged/edited) → feedback.jsonl
```

---

## Guardrails

```bash
pytest -q tests/test_guardrails.py tests/test_injection.py tests/test_partner_mode.py tests/test_feedback.py tests/test_phase6_issues.py
# HTTP: GET /v1/pilot/go-nogo
```

---

## Flip one class to live draft (after security review)

```bash
$env:RAPHAEL_PARTNER_MODE="allowlist"
$env:RAPHAEL_PUBLISH_MODE="live"
$env:RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES="probe_misconfiguration"
$env:RAPHAEL_GITHUB_TOKEN="ghp_..."
python -m raphael_agent.scripts.pilot_go_nogo
```

---

## Interface / I0 (deferred)

Human UIs (GitHub slash commands, Cursor/VS Code) are specified under [`../interface/`](../interface/README.md). **CLI remains the interactive path today** — see [`../interface/Usage.md`](../interface/Usage.md).

- Agent HTTP default listen: **`127.0.0.1:8091`** (`RAPHAEL_AGENT_LISTEN`). Sandbox controller stays on **`:8090`**.
- I0 APIs **served**: `GET/POST /v1/runs`, `POST /v1/runs/{id}/actions` — see [`../interface/prd-i0-api.md`](../interface/prd-i0-api.md).
- Decisions: `D-20260811-01` (locks), `D-20260811-02` (implementation).
