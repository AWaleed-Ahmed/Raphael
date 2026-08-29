# Raphael Decision Log

**Purpose:** Track product/architecture decisions for Raphael so future work stays consistent.
**Format:** Each entry records the decision, why, alternatives considered, and status.
**Rule:** When we make a new meaningful choice, append a new dated entry here. Do not rewrite history — supersede with a new entry that references the old ID.

---

## How to use this file

1. Add a new entry at the **top of the log** (newest first) when a decision is made.
2. Use a stable ID: `D-YYYYMMDD-NN` (date + sequence that day).
3. If a decision changes later, mark the old one `superseded` and link the new ID.
4. Keep entries short. Link to `prd.md`, `CODING_RULE.md`, or PRs when useful.

### Entry template

```markdown
### D-YYYYMMDD-NN — Short title
- **Status:** accepted | superseded by D-... | deprecated
- **Date:** YYYY-MM-DD
- **Owners:** names / roles
- **Decision:** what we chose
- **Why:** reason(s)
- **Alternatives:** what else we considered and why not
- **Consequences:** what this forces or unlocks
```

---

## Decision log (newest first)

### D-20260829-01 — E2E harness verifies dispatch↔Ignis wire-protocol interop
- **Status:** accepted
- **Date:** 2026-08-29
- **Owners:** Engineer B + coding agent
- **Decision:** Raphael-core dispatch and Ignis's controller+connector binary have been verified to interoperate correctly over the real HTTP wire protocol via a three-scenario harness at `raphael/e2e/`. Neither side is mocked: dispatch runs as a real Starlette process with deterministic `AgentHooks`, and Ignis runs as the compiled release binary with `RAPHAEL_CLUSTER_BACKEND=mock`.
- **Why:** Prior milestones proved each side independently (Ignis sandbox tests, dispatch unit tests). No test exercised the full connector→dispatch→connector loop with real HTTP, real envelope validation, and real job state machine transitions.
- **What was proven:**
  - **Success path:** job reaches `fix_finalized` through create_sandbox → deploy_revision → observe_failure → patch → run_validation → finalize_result → terminal. Ignis calls `destroy_sandbox` and removes its cloned workspace from disk.
  - **Budget exhaustion:** validation fails repeatedly (same failure signature preserved across patch attempts), job escalates after exactly `RAPHAEL_MAX_PATCH_ATTEMPTS` patch deploys — counted in the trace, not inferred.
  - **Connector restart mid-flight:** Ignis killed during a 15s artificial delay in the diagnose hook (after create_sandbox + deploy_revision, before patch/finalize). Restarted connector resumes the same job with the same `sandbox_id` — confirmed by extracting sandbox_id from every result POST in the trace. No data loss, no sandbox recreation.
- **Known gaps (not proven by this milestone):**
  - **Dispatch-side restart safety.** `Orchestrator.jobs` is in-memory and does not rehydrate from `RunStore`. This harness kept dispatch up throughout; only Ignis was restarted. A dispatch restart mid-job would lose all in-flight state.
  - **Lease reaping is manual-only.** `POST /v1/leases/reap` exists but no scheduler or timer invokes it automatically. Expired leases are never reaped unless an external caller triggers the endpoint.
- **Referenced PRs:** connector HTTP transport (Ignis), dispatch job queue + auth fix (Raphael #10, #11), E2E harness (Raphael `feature/e2e-harness`).
- **Consequences:** The dispatch↔Ignis wire protocol is validated end-to-end. Remaining restart and lease-reaping gaps are tracked separately and do not block pilot.

### D-20260814-06 — GH-M5 closes github-native with docs only (no new verbs)
- **Status:** accepted
- **Date:** 2026-08-14
- **Owners:** Engineer B + coding agent
- **Decision:** Close GH-M5 as **documentation only**. Do **not** implement `cancel` / `diagnose` / `fix`. Finish the GitHub-native permission matrix (issue_comment replies, additive labels, sticky footer, opt-in Checks write that is never required for merge). Align `docs/pilot-install.md` webhook subscriptions (`issue_comment` plus `workflow_run` / `check_run` / `pull_request` / `issues`) and App permissions with github-native PRD §7.3 (Checks r/w optional; no Administration / Secrets / Environments write / Workflows write). Record default-off knobs `RAPHAEL_GITHUB_COMMANDS`, `RAPHAEL_GITHUB_AUTO_COMMENTS`, `RAPHAEL_GITHUB_CHECK_RUNS`. Add a dry-run command smoke to the pilot week runbook and acceptance checklist (`status` / `help` / `feedback` on a fixture Issue; `retry` under `PARTNER_MODE=dry_run` never live-publishes). Mark GH-M1–M4 **Proven (code)** and Checks **opt-in / never merge-gating**. Update `handoff.md` and root `README.md` so GitHub-native is no longer described as PRD-only.
- **Why:** The command/Check surface is already in the agent (GH-M1–M4). Pilot partners need an accurate permission and webhook picture before flipping knobs. Shipping `cancel`/`diagnose`/`fix` in the same change would mix product verbs with an ops-doc milestone.
- **Alternatives:** Implement the three remaining verbs in GH-M5 — rejected (explicitly out of this phase). Treat Checks as required for merge in the matrix — rejected (GH-033/034).
- **Consequences:** Enable GitHub-native with `RAPHAEL_GITHUB_COMMANDS=1` (and separately `RAPHAEL_GITHUB_CHECK_RUNS=1` if Checks write is granted). Branch protection must not require `Raphael (advisory)`. Remaining verbs stay deferred.

### D-20260814-05 — GH-M4 advisory Check Runs are a separate opt-in
- **Status:** accepted
- **Date:** 2026-08-14
- **Owners:** Engineer B + coding agent
- **Decision:** Implement GH-030–034 as in-agent GitHub Check Runs named **`Raphael (advisory)`**. **Knob:** `RAPHAEL_GITHUB_CHECK_RUNS` default **0** and does **not** inherit `RAPHAEL_GITHUB_COMMANDS` / `RAPHAEL_GITHUB_AUTO_COMMENTS` (Checks write is a distinct GitHub permission and must not surprise partners who only wanted slash commands). Start: `run_stub_graph` (ingest/graph, including `/raphael retry` children) POSTs an `in_progress` Check on `commit_sha`. Complete: on `success_draft_pr_ready` / `success_fix_proposed` / `escalated` / `failed_closed`, PATCH with diagnosis, validation matrix, draft PR or escalation reason, `run_id`, class, confidence, `result_id` when present; redacted. `check_run_id` lives in sidecar `github_check_runs.json` (same pattern as terminal comments) — never extra `run_record.json` fields. Annotations (notice only) for allowlisted patch paths; skip secret-like content and non-allowlisted files. **Conclusion:** always `neutral` unless `RAPHAEL_GITHUB_CHECK_ADVISORY_SUCCESS=1`, which may use `success` only on the two happy terminals. Never `failure`. Copy states the Check is advisory, does not replace human review, and offers no Merge action. Missing token → skip, do not fail the run. No sandbox HTTP. **Still deferred:** `cancel` / `diagnose` / `fix`, GH-M5 full pilot-doc pass.
- **Why:** Operators want a SHA-level advisory status without turning Raphael into a required merge gate. Coupling Checks to command/auto-comment flags would write Checks for partners who never granted `checks:write`.
- **Alternatives:** Inherit auto-comments — rejected (different permission + surprise). Default conclusion `success`/`failure` — rejected (looks required / blocking). Store `check_run_id` on `run_record` — rejected (`additionalProperties: false`).
- **Consequences:** Enable with `RAPHAEL_GITHUB_CHECK_RUNS=1` plus a token. GitHub App/PAT needs Checks write only when this flag is on; branch protection must not require `Raphael (advisory)`.

### D-20260814-04 — GH-M3 terminal labels + sticky footer share auto-comment gating
- **Status:** accepted
- **Date:** 2026-08-14
- **Owners:** Engineer B + coding agent
- **Decision:** Extend the GH-M2 `publish_or_escalate` terminal hook with GH-021 labels and a GH-041 sticky “Raphael actions” footer. **Labels:** `success_draft_pr_ready` → `raphael:draft`; `success_fix_proposed` → `raphael:needs-human`; `escalated` / `failed_closed` → `raphael:escalated` plus `raphael:needs-human` when a human still has a next step (snippet apply, takeover, or inspect/retry). Additive `GitHubPublisher.add_issue_labels` only — never DELETE, never strip `raphael:fix` (GH-023), do not apply `raphael:learning-demoted` (GH-022 P2). **Sticky footer:** one Issue/PR comment marked `<!-- raphael:sticky -->`; update in place if present. Lists `/raphael status`, `/raphael feedback accepted|rejected|edited`, `/raphael help` only (write-collaborator verbs). No Merge action (GH-044), no privileged verbs in the footer. Redacted; includes `run_id` like terminal comments. **Gating:** same knob as GH-M2 — `RAPHAEL_GITHUB_AUTO_COMMENTS` unset inherits `RAPHAEL_GITHUB_COMMANDS`; default off. Labels and comments stay coupled so partners who have not opted in get neither chatter nor label writes. **Still deferred:** `cancel`, `diagnose`, `fix`, Check Runs (GH-M4).
- **Why:** Operators need triage labels and a durable command cheat-sheet on the thread without a second diagnosis/publish path. Splitting a labels-only flag would surprise partners who enabled commands for inspect-only and suddenly saw GitHub label writes.
- **Alternatives:** Separate `RAPHAEL_GITHUB_LABELS` / sticky flags — rejected (no strong reason; more surprise modes). Strip `raphael:fix` on terminal — rejected (GH-023: that label only gates new Route B triggers). Put retry/escalate in the sticky footer — rejected (write collaborators must not be invited to privileged verbs).
- **Consequences:** Enable with `RAPHAEL_GITHUB_COMMANDS=1` (or `RAPHAEL_GITHUB_AUTO_COMMENTS=1`). Graph terminal handling posts/updates the sticky comment and POSTs labels when a token is present. Unit tests cover mapping, sticky create vs update, ACL, redaction, and knob-off.

### D-20260814-03 — GH-M2 retry/escalate + independently gated terminal auto-comments
- **Status:** accepted
- **Date:** 2026-08-14
- **Owners:** Engineer B + coding agent
- **Decision:** Extend in-agent GitHub commands with `retry` and `escalate` (admin / `RAPHAEL_GITHUB_COMMAND_TEAM` only). Retry resolves the source run like `status`, refuses while the parent is `pending`/`running`, and otherwise enqueues a new run from the same fingerprint/seed with `parent_run_id`. Escalate in-flight → `escalated` + `terminal_reason=human_requested` (no patch invented); already-terminal → audit/feedback notes only (never rewrite success → escalated). GitHub retry never uses `sandbox_mode=live` (maps live → `recorded_stub`) so this path does not call sandbox HTTP. Partner/publish/allowlist gates are unchanged — retry still goes through existing `publish()`. Terminal auto-comments (GH-010–014) render via the GH-M1 template helper + evidence redaction. **Knob:** `RAPHAEL_GITHUB_AUTO_COMMENTS` unset inherits `RAPHAEL_GITHUB_COMMANDS`; explicit `0` disables comments while commands stay on; explicit `1` enables comments without slash-command parse. Default remains off for partners who have not opted in. **Still deferred:** `cancel`, `diagnose`, `fix`, Check Runs (GH-M3/M4).
- **Why:** Operators need to retry/escalate from the PR/Issue without a console, and terminal runs should leave a reviewable comment. Auto-comments are independently toggleable because they fire on ingest/graph completion, not only on slash commands.
- **Alternatives:** Always couple auto-comments to `RAPHAEL_GITHUB_COMMANDS` with no override — too coarse (cannot demo commands without bot chatter, or comments without parse). Auto-comments default on — rejected (surprise for partners). Retry while in-flight — rejected (duplicate work).
- **Consequences:** Enable commands with `RAPHAEL_GITHUB_COMMANDS=1` (auto-comments follow unless overridden). Graph `publish_or_escalate` emits comments when the flag is on. I0 `POST /v1/runs/{id}/actions` retry now also refuses in-flight parents (`conflict_state`).

### D-20260814-02 — GitHub-native GH-M1 commands hosted in the agent
- **Status:** accepted
- **Date:** 2026-08-14
- **Owners:** Engineer B + coding agent
- **Decision:** Implement GH-M1 (`status` / `help` / `feedback`) inside the existing agent HTTP webhook, gated by `RAPHAEL_GITHUB_COMMANDS` (default **0**). Parse `/raphael <verb> [args]` (prefix from `RAPHAEL_GITHUB_COMMAND_PREFIX`). ACL: write collaborators → `status`/`help`/`feedback`; other verbs need repo admin or `RAPHAEL_GITHUB_COMMAND_TEAM` membership. Rate-limit 10/hour per repo+actor (GH-053). Idempotency via GitHub `comment_id` / delivery id (GH-054). Ignore the bot’s own comments. Reply templates live under `interface/github-native/templates/`. **Not implemented:** `retry`, `escalate`, `cancel`, `diagnose`, `fix`, Check Runs (GH-M2+). Command path must not call sandbox HTTP and must not widen partner/publish gates. I0 helpers stay in `agent/raphael_agent/runs.py` (file, not a gitignored `runs/` directory).
- **Why:** I1 needs GitHub as the operator console without a second process or a second diagnosis engine. Default-off avoids surprising partner webhooks. GH-M1 is inspect/feedback only so we can ship ACL + rate-limit + idempotency before privileged verbs.
- **Alternatives:** Separate `interface/github-native` worker — rejected for pilot (one webhook URL). Implement retry/escalate in the same change — rejected (explicitly GH-M2). Treat `/raphael accept` as feedback — rejected (locked grammar).
- **Consequences:** Enable with `RAPHAEL_GITHUB_COMMANDS=1`. Live reply comments need a GitHub token but unit tests assert the markdown on the webhook JSON. `raphael-agent-learn` already consumes `feedback.jsonl` (`source=github_webhook`). Partner mode / live allowlists unchanged.

### D-20260814-01 — Git branches: `feature/*` → `main` → `prod`; `stash/*` for parked WIP
- **Status:** accepted
- **Date:** 2026-08-14
- **Owners:** Engineer B + coding agent
- **Decision:** Stop landing work directly on `main`. Integration stays `main` (PR target). `prod` is a fast-forward-only promote from `main` for partner/demo pins. Day-to-day work uses `feature/<short-name>` (or `fix/`). Unfinished *commits* park on `stash/<short-name>` (not a shared immortal `stash` branch). Uncommitted dirt uses `git stash`. Documented in [`docs/BRANCHING.md`](docs/BRANCHING.md). Initial `prod` snapshot = `main` at `6c64964`.
- **Why:** Two-person repo had a single `main`; teammate and agents were colliding on the default branch. Need a stable pin (`prod`) without blocking integration.
- **Alternatives:** GitHub Flow with only `main` + features (no `prod`) — weaker demo pin. `develop` + `main` git-flow — extra hop for a two-person team. One shared `stash` branch — force-push fights.
- **Consequences:** Agents must create a feature branch before the first commit of a task. Protect `main`/`prod` on GitHub. First promote of `prod` is a no-op until `main` moves.

### D-20260811-03 — Raphael IDE extension P0 (VS Code / Cursor VSIX)
- **Status:** accepted
- **Date:** 2026-08-11
- **Owners:** Engineer B + coding agent
- **Decision:** Ship P0 under `interface/IDE/` as VS Code extension `raphael.raphael-ide` (works in Cursor). Features: agent client to `:8091`, Runs tree, Open Run markdown, Apply Fix (file contents / allowlist guards), Open Draft PR, Feedback accepted/rejected, status bar, SecretStorage token. Distribution via VSIX (`vsce package`) + GitHub Release instructions in `interface/IDE/README.md`. No Merge, no sandbox calls, local agent only.
- **Why:** IDE-first interface track after I0 APIs; partners can Install from VSIX from the GitHub repo.
- **Alternatives:** Marketplace-only publish — deferred. Cursor SDK cloud agent — out of scope for P0.
- **Consequences:** Maintainers build/attach VSIX; users need local `raphael-agent-serve`; GitHub-native commands remain next (I1).

### D-20260811-02 — Implement I0 run list/create/actions HTTP APIs
- **Status:** accepted
- **Date:** 2026-08-11
- **Owners:** Engineer B + coding agent
- **Decision:** Serve I0 routes on the agent: `GET /v1/runs`, `POST /v1/runs`, `POST /v1/runs/{run_id}/actions` (verbs `retry|escalate|cancel|feedback`) with `action_id` idempotency (`interface_actions.jsonl`). Interface bearer auth via `RAPHAEL_INTERFACE_TOKEN` (required when set on loopback; always required for non-loopback). Manual creates use `trigger_kind=manual_ui|manual_ide|manual_github` and default graph run unless `RAPHAEL_MANUAL_RUN_GRAPH=0`. Escalate in-flight → `escalated`/`human_requested`; terminal escalate is notes-only. Cancel in-flight → `cancelled`. Retry creates a new run with `parent_run_id`. Helper `delivery_patch_from_run` for IDE apply. Tests in `tests/test_i0_runs.py`. Product locks from D-20260811-01 remain in force.
- **Why:** Interfaces and operators need real steer/list/create APIs, not contracts-only.
- **Alternatives:** Leave routes unimplemented until GitHub/IDE code — rejected; blocks both. Separate microservice for actions — rejected for pilot.
- **Consequences:** `interface/prd-i0-api.md` and Usage mark routes as served; GitHub slash commands (I1) and IDE (I2) can call these next.

### D-20260811-01 — Interface I0 API lock + PRD consistency
- **Status:** accepted (contracts + docs; HTTP implemented by D-20260811-02)
- **Date:** 2026-08-11
- **Owners:** Engineer B + coding agent
- **Decision:** Freeze interface review resolutions in `interface/prd-i0-api.md` and additive contracts (`run_list_response`, `run_create_*`, `run_action_*`). Locked product table:
  - Manual triggers: `manual_ui` \| `manual_ide` \| `manual_github` + client `action_id`
  - Single GitHub App for pilot (ingest + commands)
  - IDE I2: local agent only (`127.0.0.1:8091`); cloud URL deferred to I5
  - IDE git P0: open agent PR URL only; local branch opt-in P1; no auto-push
  - Command grammar: `/raphael feedback accepted|rejected|edited` only (no `/raphael accept`)
  - Command host: agent behind `RAPHAEL_GITHUB_COMMANDS` (default off); `interface/github-native/` = docs/templates until split
  - ACL: write → `status`/`help`/`feedback`; privileged team/admin → `retry`/`diagnose`/`fix`/`escalate`/`cancel`
  - Checks: advisory name; conclusion **`neutral`** by default (never required for merge)
  - Agent listen: **`127.0.0.1:8091`**
  - Auth: loopback may omit token if unset; non-loopback requires Bearer + `RAPHAEL_INTERFACE_TOKEN`
  - `delivery_patch`: candidate `unified_diff` / hunks then `publish.fix_snippet`
  - Escalate: in-flight → `escalated`/`human_requested`; terminal → audit/notes only; never invent a patch
  - Correlation: `raphael:run_id=…` markers + `issue_number` / `pull_request_number` / `parent_run_id`
- **Why:** Close PRD blockers before I1/I2 coding; keep repo wording consistent without deleting existing CLI/Usage content.
- **Alternatives:** Implement full I0 HTTP in the same change — followed as D-20260811-02. Separate GitHub App for commands — rejected for pilot ops simplicity.
- **Consequences:** UI work uses these locks; schemas validated in agent tests.

### D-20260810-16 — Interface layer folder + deferred GitHub-native / IDE PRDs
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Add `interface/` as a separate product layer (not under `agent/` or `sandbox/`) with umbrella PRD plus `interface/github-native/prd.md` and `interface/IDE/prd.md`. Surfaces are GitHub-native interaction and a Cursor/VS Code extension. Implementation deferred; I0 (agent action API contracts) is a hard dependency before UX. Interfaces are thin clients: no sandbox calls, no auto-merge, no production writes. ChatOps remains out of this folder (root prd §25).
- **Why:** Lock product intent for the next interactive workstreams without blocking current agent/sandbox delivery.
- **Alternatives:** Build a full web operator console first — rejected for now (Git/editor-first). Put UI code inside `agent/` — rejected to keep core workflow free of presentation.
- **Consequences:** Future interface code lands only under `interface/`; agent gains shared action endpoints when I0 starts; handoff points here for “what’s next after learning.”

### D-20260810-15 — Post-MVP learning loop: offline feedback → diagnosis/patch priors
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Close the FR-065 loop offline: `python -m raphael_agent.scripts.learn` builds `learning_snapshot.json` from feedback outcomes (accepted/merged/edited/rejected/deploy_*). When `RAPHAEL_LEARNING=1`, diagnosis applies capped confidence deltas and optional `prefer_escalate`; templates with weight < 0.4 are skipped. Never widens allowlists, never unblocks blocked classes, never auto-merges. Default `RAPHAEL_LEARNING=0`. Contract: `contracts/agent/learning_snapshot.json`.
- **Why:** Partner feedback should improve next runs without training mid-incident or weakening guardrails.
- **Alternatives:** Online RL / fine-tune LLM from feedback — rejected for MVP safety. Docs-only metrics — does not change agent behavior.
- **Consequences:** Operators rebuild snapshots periodically; runs audit applied priors under `diagnosis.learning`.

### D-20260810-14 — Option B: K8s watcher ingest + App JWT + CODEOWNERS + SQLite store
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Ship FR-002 via `POST /v1/webhooks/k8s` + `normalize_k8s_workload` behind `RAPHAEL_K8S_WATCHER` (default off). GitHub auth resolves PAT first, then optional App installation token (`RAPHAEL_GITHUB_APP_*`). PR reviewers may merge CODEOWNERS user logins when `RAPHAEL_REVIEWERS_FROM_CODEOWNERS=1`. FR-065 audit deepened with issue-snippet outcomes + metrics `feedback` aggregates (still no learning loop). Agent `RunStore` may use stdlib SQLite when `RAPHAEL_AGENT_STORE=sqlite` (JSON remains default). Local pilot Day 0–1 proofs recorded in `docs/pilot-local-preflight.md`; real partner week remains ops.
- **Why:** Close deferred Option B scaffolding without waiting on a live design partner.
- **Alternatives:** Block all Option B until partner week — slower. Full in-cluster watch loop with kubeconfig in agent — rejected; prefer push webhook / file forwarder to keep Secret-free boundary.
- **Consequences:** Supplements D-20260810-09; pilot-acceptance still requires real partner for PRD Phase 5 exit.

### D-20260810-13 — Phase 6: dual-path CI templates + labeled Issues with optional model
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer A + coding agent
- **Decision:** Keep **Route A** (CI `workflow_run`/`check_run` → deterministic templates → sandbox → draft PR under partner gates). Add **Route B**: GitHub `issues` events with a developer-configured label (`RAPHAEL_ISSUE_TRIGGER_LABEL`, default `raphael:fix`). Route B loads preset `.raphael/issue-fix.yaml` or **derives ephemeral fix_rules** from bounded repo files (`.raphael/config.yaml`, `CONTRIBUTING.md`, `CODEOWNERS`); derived rules cannot widen global allowlist or disable budgets/redaction. Optional OpenAI-compatible model (`RAPHAEL_LLM_BASE_URL` / `RAPHAEL_LLM_MODEL` / API key) with `RAPHAEL_LLM_DIAGNOSIS` + `RAPHAEL_LLM_PATCH` may propose patches on Route B only; templates remain the only patch source on Route A. Route B **posts a fix snippet as an issue comment** and terminates `success_fix_proposed` — developer opens the PR; Raphael never opens a PR on Route B. Commit SHA from issue body `raphael-sha:` or default-branch HEAD (API/env fallback).
- **Why:** Partners who bring a custom model need an Issues-driven fix loop; partners who only want deploy CI healing keep the safe template path.
- **Alternatives:** Replace CI path with Issues-only — rejected. Always auto-open draft PRs from Issues — rejected (human owns PR on model path). Require model always on Route B — rejected; escalate when model/patch unavailable and no template class.
- **Consequences:** Contracts add `github_issue` trigger, `fix_rules`, `delivery_mode`, terminal `success_fix_proposed`. Supplements D-20260810-02…08.

### D-20260810-12 — Agent runtime defaults: terminals, confidence, ports, store, ingest
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Graph terminals are `success_draft_pr_ready` | `success_fix_proposed` | `escalated` | `failed_closed` (not the full PRD §9.3 set). Default diagnosis confidence threshold `0.7` (`RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD`). Agent HTTP listens on `:8091` (Starlette); sandbox controller on `:8090`. `sandbox_mode` is `live` | `recorded_stub` | `skipped`. Partner triad includes `diagnosis_only`. Durable agent state is JSON `RunStore` under `RAPHAEL_AGENT_DATA_DIR` (Postgres deferred). Ingest defaults: cooldown 900s, max concurrent 2. HMAC optional when webhook secret unset (local/dev only).
- **Why:** Freeze MVP inspectable outcomes and local-dev ergonomics without inventing SaaS persistence.
- **Alternatives:** Full PRD terminal taxonomy — deferred. Always-require webhook secret — blocks curl demos.
- **Consequences:** Phase 6 issue delivery uses `success_fix_proposed`; CI path keeps draft-PR terminal. Supplements D-20260810-02/03/07.

### D-20260810-11 — Sandbox P2: JSON durable store, PSA restricted, admin cleanup, artifacts
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer A + coding agent
- **Decision:** Durable sandbox state is a **JSON document store** with a SQLite-shaped API (`SqliteStore` → files under data dir); real SQLite/Postgres deferred. Enforce PSA `restricted` + inject restricted `securityContext` when enabled (`RAPHAEL_PSA_ENFORCE` / `RAPHAEL_INJECT_RESTRICTED_SC`). Admin `POST /v1/admin/force-cleanup` for operator TTL cleanup. Artifact disk retention default 48h (`RAPHAEL_ARTIFACT_RETENTION_HOURS`). Finalize invalidates on redeploy/re-validate until re-finalize. Cluster id `raphael-sandbox`; namespaces `raphael-run-<run_id>`; default TTL 20 minutes. No free-form kubectl API; kubeconfig stays controller-side. Layering: `api → domain → adapters`.
- **Why:** P2 hardening without blocking on crates.io SQLite; strong isolation for kind demos.
- **Alternatives:** Real SQLite in P2 — deferred. Soft isolation without PSA — weaker demo claims.
- **Consequences:** CHECKLIST P2 complete except optional real SQLite. Supplements D-20260809-08/09/11.

### D-20260810-10 — Sandbox P1 fidelity: listen :8090, svc health, full_validation gate
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer A + coding agent
- **Decision:** Controller default listen **`:8090`** (not `:8080`) so kubectl’s localhost fallback cannot hit Axum. HTTP health checks use `svc/<name>:<port>/<path>` via port-forward. Material fidelity gaps force `full_validation=false`. Record tool versions and image digests when available on fidelity/artifacts.
- **Why:** Avoided a real footgun (cluster_unavailable when kubeconfig missing and port=8080). Fidelity honesty is required by PRD.
- **Alternatives:** Stay on 8080 — rejected after incident. Claim full_validation under mock gaps — rejected.
- **Consequences:** Docs/tests/README use 8090; agent default `RAPHAEL_SANDBOX_URL=http://127.0.0.1:8090`.

### D-20260810-09 — Explicit pilot / Phase 6 deferrals
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Product / both engineers
- **Decision:** Still deferred: in-cluster K8s watcher (FR-002), GitHub App JWT as primary auth (PAT first), full FR-065 learning loop (jsonl audit only), multi-tenant SaaS, auto-merge / production remediation (forever out for MVP), GitLab/other CI hosts (Post-MVP). Real design-partner week (≥5 dry-run failures + permission approval) remains an ops exit for PRD Phase 5, not a code gate for Phase 6 dual-path work.
- **Why:** Keep MVP shippable; Option B waits for real pilot gaps.
- **Alternatives:** Block Phase 6 until partner week — slower product learning on Issues+model path.
- **Consequences:** README/CHECKLIST list these as open; do not invent ADRs that pretend they shipped.

### D-20260810-08 — Pilot week: runbook + FR-065 feedback + guardrail tests
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Add `docs/pilot-week-runbook.md` (5-day partner plan + go/no-go). Expand FR-065 to schema `feedback_event.json`, CLI `record_feedback`, `POST /v1/feedback`, optional `RAPHAEL_FEEDBACK_ON_PUBLISH`, and `pull_request` webhook → jsonl. Centralize permission-matrix checks in `guardrails.py` + `tests/test_guardrails.py` / `pilot_go_nogo` / `GET /v1/pilot/go-nogo`. Still no auto-merge / production writes / learning loop.
- **Why:** Option A after Phase 5 — ops path must be enforceable in tests, not docs-only.
- **Alternatives:** Docs-only runbook — drifts. Full FR-065 ML loop — premature.
- **Consequences:** Option B (K8s watcher / App JWT) can wait for pilot gaps. Supplements D-20260810-07.

### D-20260810-07 — Pilot: partner dry-run default + failure-class live allowlist
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Default `RAPHAEL_PARTNER_MODE=dry_run` forces dry-run publish regardless of `RAPHAEL_PUBLISH_MODE`. Live draft PRs require `PARTNER_MODE=allowlist`, `PUBLISH_MODE=live`, non-empty `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` containing the run’s `failure_class`, and a GitHub token. Empty allowlist ⇒ no live publishes. Docs: `docs/pilot-install.md`, `permission-matrix.md`, `pilot-acceptance.md`.
- **Why:** Design-partner safety; PRD Phase 5 dry-run period before enabling draft PRs per class.
- **Alternatives:** Docs-only dry-run (not enforceable) — rejected. Always-on live with mode=live — too risky for pilot.
- **Consequences:** Existing “live” tests must set allowlist + partner allowlist mode. Supplements D-20260810-05.

### D-20260810-06 — Agent Phase 4: budget defaults + injection-test policy
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Enforce env budgets: `RAPHAEL_MAX_WALL_SECONDS` (default 1800), `RAPHAEL_MAX_DIAGNOSIS_ATTEMPTS` (2), `RAPHAEL_MAX_PATCH_ATTEMPTS` (3), `RAPHAEL_MAX_COST_USD` (0=off), `RAPHAEL_SANDBOX_HTTP_TIMEOUT` (180s). Snapshot onto `run_record.budget_snapshot`. Exhaust → escalate/fail closed with structured report — never publish. Prompt-injection fixtures under `agent/fixtures/injection/` assert policy/publish remain code-gated (LLM off). Operator metrics via `GET /v1/metrics` + `raphael_agent.scripts.metrics` over RunStore only (sandbox cleanup stays controller-side).
- **Why:** PRD Phase 4 / §9.4 budgets; CODING_RULE untrusted logs ≠ instructions.
- **Alternatives:** Soft warnings without halt — rejected. Full SaaS metrics stack — premature.
- **Consequences:** Pilot can tune budgets per tenant via env without contract breaks (additive snapshot). Supplements D-20260810-02…05.

### D-20260810-05 — Agent Phase 3: draft-only GitHub publish, dry_run default
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Publish opens **draft** PRs only (never merge). Default `RAPHAEL_PUBLISH_MODE=dry_run` builds branch/title/body and a documented compare placeholder URL without GitHub mutation. Live mode uses REST Contents + Pulls APIs with `RAPHAEL_GITHUB_TOKEN` (optional App JWT vars reserved/documented for later). Branch format `raphael/<run-id>-<summary>`. Base branch `RAPHAEL_GITHUB_BASE_BRANCH` (default `main`). Fail closed without `result_id` or when run is escalated/failed_closed. Idempotent: reuse `pull_request_url` on the run and/or an existing open PR for the head branch. Contract: `contracts/agent/publish_result.json`.
- **Why:** FR-060–064 + FR-074; keeps CI credential-free; human-controlled delivery.
- **Alternatives:** Always live publish — breaks CI. Shell `git push` — heavier, harder to mock. Merge PRs — rejected for MVP.
- **Consequences:** Phase 4 can harden budgets/metrics without changing draft-only semantics. Supplements D-20260810-02…04.

### D-20260810-04 — Agent Phase 2: analyzer-first diagnosis + optional LLM + patch allowlist
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Diagnosis runs **deterministic analyzers first** (probe/port, bad image, missing ConfigMap key, Helm/Kustomize render, blocked secret/privilege). Optional structured LLM refine is behind `RAPHAEL_LLM_DIAGNOSIS` (default `0`); malformed/unkeyed LLM output is ignored (fail closed to deterministic). Patch generation uses deterministic fix templates within default allowlisted prefixes (`deploy/`, `k8s/`, `manifests/`, `charts/`, `overlays/`, `.github/workflows/`, overridable via `RAPHAEL_PATCH_ALLOWLIST`). Policy rejects secret-like strings and privilege/host escapes in code. Max patch attempts: `RAPHAEL_MAX_PATCH_ATTEMPTS` (default 3). Graph may loop validate→patch within budget. Publish remains a no-op requiring `result_id` (no GitHub PR).
- **Why:** Matches FR-020–025 / FR-040–045 and CODING_RULE “deterministic before LLM”; keeps CI/tests free of API keys.
- **Alternatives:** LLM-first diagnosis — rejected (nondeterministic, costly). Always require fixed_path tree — weaker than real file patches. Durable LangGraph checkpointer — deferred; RunStore + run_record remain SoT.
- **Consequences:** Phase 3 can open draft PRs from frozen `result_id` without changing diagnosis/patch contracts. Supplements D-20260810-02/03.

### D-20260810-03 — Agent Phase 1: GitHub ingest + JSON run store + policy gates
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Implement FR-001/003–006 under `agent/raphael_agent/ingest` with Starlette webhook (`/v1/webhooks/github`), HMAC via `RAPHAEL_GITHUB_WEBHOOK_SECRET` (optional in local dev when unset), durable JSON `RunStore` under `RAPHAEL_AGENT_DATA_DIR`, and fingerprint `tenant|repo|commit|env|provisional_failure_key`. Cooldown + max concurrent runs are env-configurable. Evidence facade calls GitHub Actions adapter then fixture stub; redaction helpers land now. K8s watcher deferred. Graph auto-run from webhook is opt-in (`RAPHAEL_INGEST_RUN_GRAPH`).
- **Why:** Keeps Phase 0 entry shape (`normalize → initial_run_state → graph`) while making ingest real and fail-closed on duplicates/runaway concurrency.
- **Alternatives:** Require secret always (blocks local curl demos); SQLite immediately (premature); always run full graph on webhook (too heavy for intake).
- **Consequences:** Phase 2 can attach analyzers/patch without redesigning fingerprints or webhook auth. Supplements D-20260810-02.

### D-20260810-02 — Agent Phase 0: `agent/` package + in-memory LangGraph stub
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Place the agent track under top-level `agent/` with importable package `raphael_agent` (not under `sandbox/`, not named `raphael_agent/` at repo root). Freeze agent wire shapes in `contracts/agent/`. Phase 0 LangGraph uses an **in-memory** compiled graph (no checkpointer); the inspectable durable object is the `run_record` / `RunState` dict. Sandbox HTTP base URL defaults to `http://127.0.0.1:8090` via `RAPHAEL_SANDBOX_URL`. Offline smoke uses recorded fixtures when `/health` is down.
- **Why:** Matches CODING_RULE boundary (agent outside `sandbox/`); `agent/` is the suggested short layout; checkpointer/persistence can land in Phase 2 without rewriting node contracts.
- **Alternatives:**
  - `raphael_agent/` at repo root — clearer package name, noisier tree next to `sandbox/`.
  - Sqlite/Postgres LangGraph checkpointer in Phase 0 — premature before real ingest.
  - Put orchestration under the core dispatch service — rejected; harness is not the agent.
- **Consequences:** Engineer B extends `agent/raphael_agent/{ingest,evidence,...}`; publish remains a no-op until a sandbox `result_id` exists. Supersedes the “do not start agent” portion of D-20260809-02 for this explicit Phase 0 request.

### D-20260810-01 — P0: clone-at-SHA, secret fixtures, observe artifacts; Docker blocked without sudo
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer A + coding agent
- **Decision:** Implement FR-030 clone-at-SHA via `repository.clone_url`, apply synthetic secret fixtures on create, capture bounded event/log artifacts on observe. Install kubectl/kind/helm to `~/.local/bin`. Docker install left to the user (`the customer-approved Ignis deployment procedure`) because sudo password is required.
- **Why:** Unblocks P0 code paths without waiting on Docker; kind bake-off remains the remaining P0 gate.
- **Alternatives:** Block all P0 until Docker works — slower. Embed a rootless container runtime — out of MVP scope.
- **Consequences:** Mock tests cover new P0 features; kind verification still required before demo claims.

### D-20260809-11 — Add `finalize_result` as sixth sandbox verb (Option B)
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Add `finalize_result(sandbox_id) -> result_id` that freezes an **immutable** validated-fix record (patch/files or rendered manifests, before/after signatures, validation matrix, fidelity, artifact ids). Sandbox still does **not** open PRs or push Git. Agent later publishes the PR from this `result_id`. Also expose `GET /v1/sandboxes/{id}/result` to read the frozen record.
- **Why:** The five lifecycle verbs prove a fix worked but did not mint an auditable “this exact fix passed” object. Relying on agent memory alone is weaker for audit/replay.
- **Alternatives:**
  - **Option A:** only enrich `run_validation` response / soft result fields — smaller, but no explicit freeze/idempotent handoff.
  - Put `open_pull_request` in sandbox — rejected; GitHub publishing is Engineer B / agent track.
  - Keep five verbs only — rejected after product discussion.
- **Consequences:** Agent-facing control plane is now six verbs (+ health/GET result). `CODING_RULE.md` and contracts updated. Finalize fails closed unless validation passed.

### D-20260809-10 — Decision log file lives at repo root as `decision.md`
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Keep a running decision log in [`decision.md`](decision.md) at the repository root.
- **Why:** First-time sandbox project; need a durable record of “why we chose X” without digging through chat.
- **Alternatives:**
  - Only chat history — gets lost / hard to search.
  - ADR folder with many files — better later at scale; overkill for MVP.
- **Consequences:** Update this file whenever architecture or process choices change.

---

### D-20260809-09 — Mock cluster backend for local/CI without Docker
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Default local development uses `RAPHAEL_CLUSTER_BACKEND=mock`. Real kind/kubectl is optional via `kind` / `kubeconfig` backend.
- **Why:** This environment had no Docker; we still needed to finish phases and tests. Mock preserves the same five JSON APIs.
- **Alternatives:**
  - Require Docker/kind for every test — blocks progress here.
  - Fake only at the HTTP layer — would not exercise domain/render/observe logic.
- **Consequences:** Mock is for contracts + deterministic signatures. Real fidelity still needs kind before production claims. Fidelity report must disclose mock gaps.

---

### D-20260809-08 — Isolation defaults: namespace-per-run + policy blocks
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** On create: labeled namespace, ResourceQuota, LimitRange, default-deny NetworkPolicy, dedicated ServiceAccount. Policy rejects privileged, hostNetwork, hostPID, hostPath, and non-fixture Secrets. Destroy is idempotent. TTL reaper cleans expired sandboxes.
- **Why:** PRD trust boundary; cheapest strong isolation inside one shared cluster.
- **Alternatives:**
  - Cluster-per-run — stronger isolation, too slow/expensive for MVP.
  - Soft isolation without NetworkPolicy — unsafe for demos that claim isolation.
- **Consequences:** Real kubectl backend applies isolation manifests; mock simulates create/destroy and policy checks in-process.

---

### D-20260809-07 — Failure signatures are deterministic structured objects
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** `observe_failure` returns a typed `failure_signature` (class, key, normalized fields, evidence refs). Analyzers run in code, not via LLM.
- **Why:** Saves agent tokens; makes before/after validation machine-checkable; matches “deterministic before probabilistic.”
- **Alternatives:**
  - Free-form prose diagnosis in the sandbox — burns tokens and is hard to test.
  - Only non-zero exit codes — too weak (PRD requires signature match).
- **Consequences:** Agent later ranks hypotheses using these signatures; sandbox never “explains” with an LLM.

---

### D-20260809-06 — Pluggable manifest renderers: YAML → Helm → Kustomize
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** `ManifestRenderer` selected by `manifests.type`. Implement order: plain YAML first, then Helm, then Kustomize. Same `deploy_revision` API for all.
- **Why:** Scalable without rewrite; YAML is cheapest to learn; Helm matches PRD config examples; Kustomize needed for overlay failure classes.
- **Alternatives:**
  - Helm-only from day one — steeper learning curve; locks format.
  - YAML-only forever — not realistic for customer repos.
  - k3d-specific tooling baked into render path — rejected; renderers stay backend-agnostic.
- **Consequences:** Adding a new packager means a new adapter, not a new controller API.

---

### D-20260809-05 — Local cluster tool: kind (not k3d); one cluster, many namespaces
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Use **kind** for the local/demo Kubernetes backend. Create **one shared cluster**, and **one namespace per run** (`raphael-run-<run_id>`). Bootstrap is owned by the external Ignis executor; core has no local bootstrap.
- **Why:** Closer to standard customer Kubernetes; better long-term fidelity; cheaper than cluster-per-run; API can later point at a remote sandbox cluster without caller changes.
- **Alternatives:**
  - **k3d** — faster/lighter, but k3s can differ from full upstream K8s.
  - New kind cluster per run — slow, heavy, expensive.
  - Only namespaces on a random shared laptop cluster with no bootstrap — hard to reproduce.
- **Consequences:** Need Docker to run real kind. Until then, use mock backend. Scripts must stay idempotent.

---

### D-20260809-04 — Shared contracts in `contracts/sandbox/` (JSON Schema)
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent (shared with future Engineer B)
- **Decision:** Freeze the five sandbox verb request/response shapes (plus `failure_signature`, `fidelity_report`, `error_envelope`) as JSON Schema under `contracts/sandbox/`. Change contracts before Rust/Python types.
- **Why:** Sandbox and future agent can be built in different rooms and still plug together. Saves agent tokens by forcing structured I/O.
- **Alternatives:**
  - Types only inside Rust — agent/Python would guess shapes.
  - Protobuf/gRPC first — stronger typing, heavier for MVP HTTP demo.
  - OpenAPI-only without schemas — fine later; JSON Schema is enough now.
- **Consequences:** Contract tests in the harness must catch drift. Breaking changes need a version bump story.

---

### D-20260809-03 — Rust controller + Python harness only
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Production sandbox controller is **Rust** (Axum HTTP JSON service). **Python** is only for demo scenarios, contract tests, and e2e calls to the API — not a second controller.
- **Why:** Matches PRD (Rust for infra orchestration, Python for later agent). Keeps heavy K8s work out of the agent tool loop. Clean boundary for LangGraph later.
- **Alternatives:**
  - **Python-only sandbox** — faster early demos, higher risk of “just shell kubectl,” weaker long-term controller.
  - Rust everywhere including tests — slower scenario authoring.
  - Agent shells out to kubectl directly — burns tokens and breaks isolation.
- **Consequences:** Harness must use HTTP (`httpx`). Controller owns kubeconfig. Five verbs only for agent-facing control plane.

---

### D-20260809-02 — All sandbox work under `sandbox/` until agent connect is requested
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Implement sandbox subsystem only under `sandbox/` (plus shared `contracts/` and root rules). Do not start LangGraph/agent code until explicitly asked to connect.
- **Why:** Split ownership (Engineer A sandbox vs Engineer B agent); avoid one-shot sprawl; keep agent token use low by finishing deterministic APIs first.
- **Alternatives:**
  - Build agent and sandbox together immediately — higher coupling and token cost.
  - Put controller at repo root without `sandbox/` prefix — muddier ownership.
- **Consequences:** Integration with agent is a later explicit phase.

---

### D-20260809-01 — Process: co-plan, coding rules first, then co-develop by phase
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** User (Engineer A) + coding agent
- **Decision:** Plan together; write [`CODING_RULE.md`](CODING_RULE.md) first; after plan approval, co-develop phase by phase (not a blind one-shot). User may also request full-phase execution in one pass (as done for the initial sandbox implementation).
- **Why:** User is new to K8s/sandboxes; needs shared rules and stepwise clarity while still shipping.
- **Alternatives:**
  - Agent-only planning, user-only coding — slower feedback.
  - Pure one-shot with no rules doc — architecture drifts.
- **Consequences:** [`CODING_RULE.md`](CODING_RULE.md) is binding for sandbox code. Phase exit criteria matter even when multiple phases land together.

---

### D-20260809-00 — Product baseline from `prd.md`
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Product / both engineers
- **Decision:** Raphael MVP is a self-healing deployment agent that observes CI/K8s failures, reproduces in an isolated sandbox, proposes a minimal Git fix via PR, and never writes to production. Sandbox APIs are the five verbs in PRD §20.1.
- **Why:** Core product differentiator is evidence-backed, reproduced, validated fixes under human Git controls.
- **Alternatives:**
  - Auto-remediate production in-place — rejected for MVP (too dangerous).
  - Advice-only chatbot with no sandbox — rejected (weak trust).
- **Consequences:** All sandbox design must support reproduce → validate → report, fail closed, and secret non-exfiltration.

---

## Quick index

| ID | Topic |
|---|---|
| D-20260814-06 | GH-M5 permission matrix + pilot docs (no new verbs) |
| D-20260814-05 | GH-M4 advisory Check Runs (separate opt-in) |
| D-20260814-04 | GH-M3 labels + sticky footer |
| D-20260814-03 | GH-M2 retry/escalate + auto-comments |
| D-20260814-02 | GH-M1 GitHub-native commands in the agent |
| D-20260814-01 | Git `feature/*` → `main` → `prod`; `stash/*` WIP |
| D-20260811-03 | Raphael IDE extension P0 (VS Code/Cursor VSIX) |
| D-20260811-02 | Implement I0 run list/create/actions HTTP APIs |
| D-20260811-01 | Interface I0 API lock + PRD consistency |
| D-20260810-16 | Interface layer PRDs (GitHub-native + IDE/Cursor; deferred) |
| D-20260810-15 | Post-MVP learning loop (offline feedback → priors) |
| D-20260810-14 | Option B K8s watcher + App JWT + CODEOWNERS + SQLite store |
| D-20260810-13 | Phase 6 dual-path CI + labeled Issues + optional model |
| D-20260810-12 | Agent terminals / confidence / ports / RunStore / ingest defaults |
| D-20260810-11 | Sandbox P2 JSON store / PSA / admin cleanup / artifacts |
| D-20260810-10 | Sandbox P1 :8090 / svc health / full_validation gate |
| D-20260810-09 | Explicit pilot / Phase 6 deferrals |
| D-20260810-08 | Pilot week runbook + FR-065 feedback + guardrail tests |
| D-20260810-07 | Pilot partner dry-run default + live failure-class allowlist |
| D-20260810-06 | Agent Phase 4 budgets + injection tests + metrics |
| D-20260810-05 | Agent Phase 3 draft PR publish (dry_run default) |
| D-20260810-04 | Agent Phase 2 analyzers + optional LLM + patch allowlist |
| D-20260810-03 | Agent Phase 1 GitHub ingest + RunStore |
| D-20260810-02 | Agent Phase 0 `agent/` + in-memory LangGraph |
| D-20260810-01 | P0 clone-at-SHA / fixtures / Docker sudo gate |
| D-20260809-00 | Product baseline (PRD) |
| D-20260809-01 | Co-plan / rules-first / phased co-dev |
| D-20260809-02 | `sandbox/` boundary until agent connect |
| D-20260809-03 | Rust controller + Python harness |
| D-20260809-04 | JSON Schema contracts |
| D-20260809-05 | kind + namespace-per-run |
| D-20260809-06 | YAML → Helm → Kustomize renderers |
| D-20260809-07 | Deterministic failure signatures |
| D-20260809-08 | Isolation + policy + TTL |
| D-20260809-09 | Mock backend for no-Docker/CI |
| D-20260809-11 | `finalize_result` sixth verb (Option B) |
| D-20260809-10 | This decision log |
