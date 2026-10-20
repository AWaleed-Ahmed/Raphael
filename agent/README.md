# Raphael Agent (Engineer B)

Phase 6 dual-path: **Route A** CI templates â†’ draft PR; **Route B** labeled Issues â†’ optional custom model â†’ fix snippet (developer opens the PR).

**Still non-goals:** auto-merge, production cluster writes. K8s watcher is opt-in (`RAPHAEL_K8S_WATCHER=1`). LLM **off** by default.

Pilot docs:

- [`docs/pilot-install.md`](../docs/pilot-install.md)
- [`docs/permission-matrix.md`](../docs/permission-matrix.md)
- [`docs/pilot-acceptance.md`](../docs/pilot-acceptance.md)
- [`docs/pilot-week-runbook.md`](../docs/pilot-week-runbook.md) â† **5-day plan**

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

The local model artifacts are not currently runnable through a packaged
inference runtime. The prediction implementation lives under the ignored
`raphael/model/` training directory and is absent from fresh checkouts and
installed agent packages. Local inference is therefore deferred and disabled
by default; deterministic diagnosis, ranking, and patch behavior remain active.
Setting `RAPHAEL_MODEL_ENABLED=1` while the runtime is unavailable does not
stop normal execution. Each attempted graph capability records its unavailable
reason in `model_results` or the audit trail.

| Variable | Default | Meaning |
|---|---|---|
| `RAPHAEL_MODEL_ENABLED` | `0` | Opt in to local inference; currently unavailable in a clean checkout |
| `RAPHAEL_MODEL_ROOT` | repository `models/` in a source checkout | Directory containing model subdirectories and `model.joblib` files; set explicitly for an installed package |

Five trained artifact bundles are tracked under `models/`; their manifests list
Python 3.12.3 and joblib 1.5.3, NumPy 2.5.2, SciPy 1.18.0, and scikit-learn
1.9.0. Artifact presence and offline training metrics do not demonstrate live
inference. See
[`docs/local-inference-resolution-2026-10-20.md`](../docs/local-inference-resolution-2026-10-20.md)
for the resolution and acceptance plan.

### Optional external model (BYOK)

Diagnosis and patching share a bounded JSON transport. Supported providers are
`openai`, `gemini`, `anthropic`, `groq`, `openrouter`, `together`, `mistral`,
`deepseek`, `xai`, and `custom_openai`. All callers reuse `complete_json()`.
Azure/Bedrock native authentication and request-scoped tenant keys are outside
this module. Local classifier #40 is separate. See the
[live provider setup guide](../docs/byok-provider-guide.md) for endpoints, keys,
model compatibility and verification limits.

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Enable external diagnosis refinement |
| `RAPHAEL_LLM_PATCH` | `0` | Enable Route B model patches; also needs diagnosis=1 |
| `RAPHAEL_LLM_PROVIDER` | `openai` | Explicit supported provider |
| `RAPHAEL_LLM_API_KEY` | unset | Explicit key override for the selected provider |
| `RAPHAEL_OPENAI_API_KEY`, then `OPENAI_API_KEY` | unset | OpenAI-only key fallback |
| `RAPHAEL_GEMINI_API_KEY`, then `GEMINI_API_KEY`, then `GOOGLE_API_KEY` | unset | Gemini-only key fallback |
| `RAPHAEL_<PROVIDER>_API_KEY`, then provider key | unset | Other selected-provider key fallbacks; see guide |
| `RAPHAEL_LLM_BASE_URL` | provider default | OpenAI `/v1`, Gemini `/v1beta/openai`; custom requires a URL |
| `RAPHAEL_LLM_MODEL` | automatic | Set a model to pin it; unset/blank/`auto`/`random` discovers and randomly selects |
| `RAPHAEL_LLM_TIMEOUT_SECONDS` | `45` | Positive finite timeout, maximum 60 seconds |
| `RAPHAEL_LLM_MAX_TOKENS` | `2048` | Output token cap, 1–8192 |

Keys are resolved only after enable/safety checks. Missing keys skip the optional call;
invalid configuration, network/provider errors or invalid output fail closed. HTTPS is
required except for an explicitly configured loopback OpenAI-compatible endpoint.
URLs cannot contain embedded credentials, query strings or fragments. Redirects are disabled;
automatic mode rotates on 429 responses for non-OpenAI providers; qualify custom endpoint error semantics individually. For OpenAI it
rotates only when the documented error type/code identifies a rate limit, not
billing/account quota. Explicit models never rotate. Credentials and raw provider responses
are not added to RunState or telemetry. Responses echoing the configured key are rejected.

For Gemini, set `RAPHAEL_LLM_PROVIDER=gemini`, supply `GEMINI_API_KEY` locally, and
optionally set `RAPHAEL_LLM_MODEL` to pin a model available to that account.
The default endpoint follows [Google's compatibility documentation](https://ai.google.dev/gemini-api/docs/openai).
The 2026-10-20 Linux qualification verified authenticated discovery and a pinned
`gemini-3.1-flash-lite` one-line synthetic patch through `try_llm_patch`, using
255 prompt and 98 output tokens. Automatic smoke selected an incompatible
catalog candidate and failed safely; the candidate filter was tightened and
verified offline. Pin the demonstrated model for reproducibility; corrected
automatic selection has not been rerun live. The 128-token qualification cap
was specific to this tiny fixture, not a general diagnosis/patch output budget.

Local example (Ollama):

```bash
export RAPHAEL_LLM_DIAGNOSIS=1
export RAPHAEL_LLM_PATCH=1
export RAPHAEL_LLM_PROVIDER=custom_openai
export RAPHAEL_LLM_BASE_URL=http://127.0.0.1:11434/v1
export RAPHAEL_LLM_MODEL=llama3.2
export RAPHAEL_LLM_API_KEY=ollama
```

Automatic mode makes one authenticated catalog request (first page, at most 1,000
Gemini or Anthropic entries), filters text candidates, then attempts each selected model at most
once. It allows at most eight completion attempts within a shared deadline; catalog
requests have a maximum ten-second timeout. Catalog access does not guarantee
chat/JSON capability or remaining quota. Models sharing a quota pool may all fail;
exhaustion fails closed. There is no credential/model cache shared across keys.
OpenAI and compatible gateways use `/models`; Gemini uses native model metadata.
Anthropic uses `/models?limit=1000` and the native Messages protocol; JSON is
prompt-requested and strictly parsed locally. Compatible models must support
chat and JSON-object output; catalog visibility does not prove compatibility
or authorization. Public gateway catalogs are not key-specific entitlement lists.
Live qualification observations for the earlier three-provider snapshot are in
[`docs/byok-live-qualification-2026-10-20.md`](../docs/byok-live-qualification-2026-10-20.md).

An opt-in synthetic connectivity smoke is available after configuring a key:
`python -m raphael_agent.scripts.byok_smoke --live`. It invokes one JSON operation;
automatic mode can send a catalog GET plus up to eight completion attempts.
Pin a model for one completion attempt. It does not prove diagnosis correctness,
patch policy or live publication. Routine CI
uses stubbed responses and needs no live provider key.

Live draft PR only when: `PARTNER_MODE=allowlist` **and** `PUBLISH_MODE=live` **and** class allowlisted **and** token present.

---

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

```bash
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
