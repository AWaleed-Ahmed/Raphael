# Raphael Agent (Engineer B)

Phase 6 dual-path: **Route A** CI templates â†’ draft PR; **Route B** labeled Issues â†’ optional custom model â†’ fix snippet (developer opens the PR).

**Still non-goals:** auto-merge, production cluster writes. K8s watcher is opt-in (`RAPHAEL_K8S_WATCHER=1`). LLM **off** by default.

Pilot docs:

- [`docs/pilot-install.md`](../docs/pilot-install.md)
- [`docs/permission-matrix.md`](../docs/permission-matrix.md)
- [`docs/pilot-acceptance.md`](../docs/pilot-acceptance.md)
- [`docs/pilot-week-runbook.md`](../docs/pilot-week-runbook.md) â† **milestone gates**

---

## Dual path

| Route | Trigger | Patch source | Delivery |
|-------|---------|--------------|----------|
| **A â€” CI** | `workflow_run` / `check_run` / deployment-status | Deterministic templates | Draft PR (partner dry-run / allowlist) |
| **B â€” Issues** | `issues` with `RAPHAEL_ISSUE_TRIGGER_LABEL` (default `raphael:fix`) | Optional model (`RAPHAEL_LLM_PATCH`) or template if `raphael-failure-class:` set | Issue comment with fix snippet; **human opens PR** |

Issue body helpers:

```text
raphael-sha: <commit>
raphael-failure-class: probe_misconfiguration
```

Fix rules: `.raphael/issue-fix.yaml` if present; otherwise derived from `.raphael/config.yaml`, `CONTRIBUTING.md`, `CODEOWNERS` (cannot widen global allowlist).

---

## Setup

Follow the [canonical pilot installation](../docs/pilot-install.md) for the
verified source pair, virtual environment and explicit shell profile. Start the
complete core with `python run.py` from the repository root; agent-only uvicorn
is not a combined dispatch deployment. Python does not automatically load `.env`.

The sections below describe component options, not a second pilot installer.

### Partner / publish env

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_PARTNER_MODE` | `dry_run` | `dry_run` \| `allowlist` \| `diagnosis_only` |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | Raw preference; gated by partner mode |
| `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` | _(empty)_ | Empty â‡’ **no** live PRs; e.g. `probe_misconfiguration` |
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
| `RAPHAEL_GITHUB_BOT_LOGIN` | `raphael-agent` | Ignore this accountâ€™s comments |
| `RAPHAEL_GITHUB_AUTO_COMMENTS` | inherit commands | Unset â†’ same as `RAPHAEL_GITHUB_COMMANDS`; `0` off; `1` on. Also gates GH-M3 labels + sticky footer |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` | `1` enables advisory Check Runs (`Raphael (advisory)`). Does **not** inherit commands/auto-comments |
| `RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS` | `0` | `1` may use Check conclusion `success` on draft-ready / snippet terminals only; default remains `neutral` |

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

### Local ML model adapters

The inference-only runtime is packaged under `raphael_agent.local_inference`.
Install the qualified dependency set with `pip install './agent[local-inference]'`
and deploy the approved bundles separately using `RAPHAEL_MODEL_ROOT`.
Local inference remains **off by default** (`RAPHAEL_MODEL_ENABLED=0`), including
in the pilot. Missing, unapproved or incompatible artifacts preserve the
unavailable/deterministic path. Incident retrieval requires an explicit backend
`RAPHAEL_AGENT_TENANT_ID` / `RAPHAEL_COMPANY_ID` / `RAPHAEL_CLIENT_ID` binding and
a format-2 index with exact ownership partitions. See [scope, migration and
public-data isolation proof](../docs/incident-isolation-64.md). Full graph/pilot
qualification remains separate under #40; default-off is unchanged.
See [installation, artifact trust and verification](../docs/local-inference-runtime.md).

### Optional external model (BYOK)

Shipped main implements `openai`, `gemini`, `anthropic`, `groq`, `openrouter`,
`together`, `mistral`, `deepseek`, `xai`, and `custom_openai`. Anthropic uses its
native Messages transport; Gemini uses the OpenAI-compatible completion endpoint.
Adapter support does not establish live qualification for every provider/model.
Native Azure/Bedrock auth and request/tenant-scoped keys remain outside this cut.

External diagnosis and patching default off (`RAPHAEL_LLM_DIAGNOSIS=0`,
`RAPHAEL_LLM_PATCH=0`); patching also requires diagnosis enabled. Select
`RAPHAEL_LLM_PROVIDER` explicitly. Keys resolve in order:
`RAPHAEL_LLM_API_KEY`, then `RAPHAEL_<PROVIDER>_API_KEY`, then the selected
provider's standard key variables (Gemini: `GEMINI_API_KEY`, then `GOOGLE_API_KEY`).
There is no fallback to another provider's key. HTTPS is required except an
explicit loopback compatible endpoint; keep credentials in the backend environment.

`RAPHAEL_LLM_MODEL` pins a model; unset/blank/`auto`/`random` discovers and
randomly selects candidates. Discovery is bounded (one page, at most 1,000
Gemini/Anthropic entries, ten-second catalog timeout); completion attempts are
bounded at eight under a shared deadline. `RAPHAEL_LLM_TIMEOUT_SECONDS` defaults
to 45, maximum 60; `RAPHAEL_LLM_MAX_TOKENS` defaults to 2048, range 1–8192.
Discovery does not prove JSON/chat capability or available quota. Explicit
models do not rotate. Invalid configuration/provider/output errors fail closed.

The [shipped provider guide](https://github.com/AWaleed-Ahmed/Raphael/blob/0dc46c47b976a42dd958ad4d8e56dcfaf8b154ab/docs/byok-provider-guide.md)
records provider endpoints and key names. [PR #58](https://github.com/AWaleed-Ahmed/Raphael/pull/58)
is merged: it integrates Gemini candidate filtering and stricter OpenAI 429
semantics while preserving main's adapters. Corrected automatic selection still
needs live qualification.

[Earlier Linux qualification](../docs/byok-live-qualification-2026-10-20.md)
used authenticated discovery and a pinned `gemini-3.1-flash-lite` one-line synthetic
patch through the actual helper and schema/policy checks: 255 prompt + 98 output
tokens. Automatic selection failed safely on an incompatible candidate; the
corrected filter has no live rerun. No cluster apply, publication, live quota
rotation or other provider success was demonstrated by that check. It was on
an earlier three-adapter snapshot, not a ten-provider live acceptance run.

An optional `python -m raphael_agent.scripts.byok_smoke --live` makes paid/network
requests when configured; it is not part of installation. Pin a model for one
completion attempt; automatic mode may make a catalog request plus eight attempts.
Model output cannot override deterministic blocks or sandbox/policy gates.
Live draft delivery additionally needs approved partner/publish modes, a class
allowlist and scoped GitHub credentials.

## Partner dry-run demo (â‰¤15 min)

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
# Webhook: X-GitHub-Event: pull_request (closed/merged/edited) â†’ feedback.jsonl
```

---

## Guardrails

```bash
pytest -q tests/test_guardrails.py tests/test_injection.py tests/test_partner_mode.py tests/test_feedback.py tests/test_phase6_issues.py
# HTTP: GET /v1/pilot/go-nogo
```

---

## Flip one class to live draft (after security review)

```powershell
$env:RAPHAEL_PARTNER_MODE="allowlist"
$env:RAPHAEL_PUBLISH_MODE="live"
$env:RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES="probe_misconfiguration"
$env:RAPHAEL_GITHUB_TOKEN="ghp_..."
python -m raphael_agent.scripts.pilot_go_nogo
```

---

## GitHub-native commands (GH-M1â€“M5, default off)

Hosted in this agent (`POST /v1/webhooks/github`, `X-GitHub-Event: issue_comment`). Parsing **does not run** unless `RAPHAEL_GITHUB_COMMANDS=1`. The command path never calls the sandbox HTTP API and never widens partner/publish gates.

Implemented: `status` `[run_id]`, `help`, `feedback accepted|rejected|edited`, **`retry`**, **`escalate`**.
**Not implemented:** `cancel`, `diagnose`, `fix` (deferred; GH-M5 was docs only).

ACL: GitHub `author_association` OWNER/MEMBER/COLLABORATOR may run `status`/`help`/`feedback`. `retry` / `escalate` require OWNER/admin or membership in `RAPHAEL_GITHUB_COMMAND_TEAM`.

`retry` copies fingerprint/seed, sets `parent_run_id`, and refuses if the source run is still `pending`/`running`. `escalate` marks in-flight runs `escalated`/`human_requested`; terminal runs get an audit/feedback note only.

Terminal auto-comments (draft-ready / snippet / escalated / failed) plus GH-M3 labels (`raphael:draft` / `raphael:needs-human` / `raphael:escalated`) and a sticky â€œRaphael actionsâ€ footer follow `RAPHAEL_GITHUB_AUTO_COMMENTS` (unset inherits `RAPHAEL_GITHUB_COMMANDS`). The footer lists write-collaborator verbs only (no Merge, no retry/escalate). Labels are additive and never strip `raphael:fix`.

**Check Runs (GH-M4):** `RAPHAEL_GITHUB_CHECK_RUNS=1` (default `0`, does not inherit commands) creates/updates a Check named `Raphael (advisory)` on `commit_sha`. Conclusion defaults to `neutral`. Optional `RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS=1` may use `success` on draft-ready / snippet only. Never `failure`, never a required merge check, never a Merge action. `check_run_id` is stored in `github_check_runs.json`, not on `run_record.json`. Annotations are notice-level on allowlisted patch paths only.

Local tests (no GitHub token):

```bash
cd agent
pytest -q tests/test_github_commands.py tests/test_github_check_runs.py tests/test_i0_runs.py
```

`status` / `retry` / `escalate` resolve `run_id` as: explicit arg â†’ `<!-- raphael:run_id=â€¦ -->` / `raphael:run_id=â€¦` on the Issue/PR body â†’ latest store run for that Issue/PR number. Webhook JSON includes the markdown `reply`; posting that comment to GitHub needs `RAPHAEL_GITHUB_TOKEN` (or App installation token).

## Interface / I0

Human UIs: GitHub slash commands (GH-M1 above) and Cursor/VS Code under [`../interface/`](../interface/README.md). CLI remains fully supported â€” [`../interface/Usage.md`](../interface/Usage.md).

- Agent HTTP default listen: **`127.0.0.1:8091`** (`RAPHAEL_AGENT_LISTEN`). Sandbox controller stays on **`:8090`**.
- I0 APIs **served**: `GET/POST /v1/runs`, `POST /v1/runs/{id}/actions` â€” see [`../interface/prd-i0-api.md`](../interface/prd-i0-api.md).
- Decisions: `D-20260811-01` (locks), `D-20260811-02` (I0 HTTP), `D-20260814-02` (GH-M1), `D-20260814-03` (GH-M2).
