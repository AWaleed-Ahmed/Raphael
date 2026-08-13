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
| `RAPHAEL_GITHUB_COMMANDS` | `0` | `1` enables `/raphael` comment commands on `issue_comment` |
| `RAPHAEL_GITHUB_COMMAND_PREFIX` | `/raphael` | Slash-command prefix |
| `RAPHAEL_GITHUB_COMMAND_TEAM` | unset | Privileged verb allowlist (slug and/or comma-separated logins) |
| `RAPHAEL_GITHUB_COMMAND_TEAM_MEMBERS` | unset | Extra privileged logins (tests / no Teams API) |
| `RAPHAEL_GITHUB_COMMAND_RATE_LIMIT` | `10` | Max commands per hour per repo+actor |
| `RAPHAEL_GITHUB_BOT_LOGIN` | `raphael-agent` | Ignore this account’s comments |
| `RAPHAEL_GITHUB_AUTO_COMMENTS` | inherit commands | Unset → same as `RAPHAEL_GITHUB_COMMANDS`; `0` off; `1` on |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` | **Deferred (GH-M4)** — do not enable yet |

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

## GitHub-native commands (GH-M1/M2, default off)

Hosted in this agent (`POST /v1/webhooks/github`, `X-GitHub-Event: issue_comment`). Parsing **does not run** unless `RAPHAEL_GITHUB_COMMANDS=1`. The command path never calls the sandbox HTTP API and never widens partner/publish gates.

Implemented: `status` `[run_id]`, `help`, `feedback accepted|rejected|edited`, **`retry`**, **`escalate`**.  
**Not implemented:** `cancel`, `diagnose`, `fix`, Check Runs.

ACL: GitHub `author_association` OWNER/MEMBER/COLLABORATOR may run `status`/`help`/`feedback`. `retry` / `escalate` require OWNER/admin or membership in `RAPHAEL_GITHUB_COMMAND_TEAM`.

`retry` copies fingerprint/seed, sets `parent_run_id`, and refuses if the source run is still `pending`/`running`. `escalate` marks in-flight runs `escalated`/`human_requested`; terminal runs get an audit/feedback note only.

Terminal auto-comments (draft-ready / snippet / escalated / failed) follow `RAPHAEL_GITHUB_AUTO_COMMENTS` (unset inherits `RAPHAEL_GITHUB_COMMANDS`).

Local tests (no GitHub token):

```bash
cd agent
pytest -q tests/test_github_commands.py tests/test_i0_runs.py
```

`status` / `retry` / `escalate` resolve `run_id` as: explicit arg → `<!-- raphael:run_id=… -->` / `raphael:run_id=…` on the Issue/PR body → latest store run for that Issue/PR number. Webhook JSON includes the markdown `reply`; posting that comment to GitHub needs `RAPHAEL_GITHUB_TOKEN` (or App installation token).

## Interface / I0

Human UIs: GitHub slash commands (GH-M1 above) and Cursor/VS Code under [`../interface/`](../interface/README.md). CLI remains fully supported — [`../interface/Usage.md`](../interface/Usage.md).

- Agent HTTP default listen: **`127.0.0.1:8091`** (`RAPHAEL_AGENT_LISTEN`). Sandbox controller stays on **`:8090`**.
- I0 APIs **served**: `GET/POST /v1/runs`, `POST /v1/runs/{id}/actions` — see [`../interface/prd-i0-api.md`](../interface/prd-i0-api.md).
- Decisions: `D-20260811-01` (locks), `D-20260811-02` (I0 HTTP), `D-20260814-02` (GH-M1), `D-20260814-03` (GH-M2).
