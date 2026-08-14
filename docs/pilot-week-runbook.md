# Pilot week runbook (5 days)

Actionable day-by-day plan for a design partner. Builds on:

- [`pilot-install.md`](pilot-install.md)
- [`permission-matrix.md`](permission-matrix.md)
- [`pilot-acceptance.md`](pilot-acceptance.md)

**Hard rules:** partner `dry_run` until go; no auto-merge; no production writes; no Secret payload reads; empty live allowlist ⇒ no live PRs.

---

## Day 0 — Access & secrets (before kickoff)

- [ ] Partner provides: staging GitHub repo, webhook URL reachability, optional PAT (draft PR scopes only)
- [ ] Set `RAPHAEL_GITHUB_WEBHOOK_SECRET` (required in partner env; optional only for local unsigned curl)
- [ ] Confirm production evidence SA cannot get Secret `data` / cannot patch workloads ([permission-matrix](permission-matrix.md))
- [ ] Clone Raphael; `cd agent && pip install -e .`
- [ ] Run go/no-go:

```bash
cd agent
# Windows PowerShell
$env:RAPHAEL_PARTNER_MODE="dry_run"
$env:RAPHAEL_LLM_DIAGNOSIS="0"
python -m raphael_agent.scripts.pilot_go_nogo
```

Expect `go=True`.

---

## Day 1 — Install + local proof

- [ ] Start sandbox mock (or kind if available) per install doc
- [ ] `python -m raphael_agent.scripts.demo_partner` → `success_draft_pr_ready` + `raphael_dry_run=1`
- [ ] `pytest -q` in `agent/`
- [ ] `python -m raphael_agent.scripts.metrics`
- [ ] Point GitHub webhook at `POST /v1/webhooks/github` for `workflow_run`, `check_run`, `pull_request`, and **`issue_comment`**
- [ ] Leave GitHub-native knobs **off** until the smoke below: `RAPHAEL_GITHUB_COMMANDS=0`, `RAPHAEL_GITHUB_CHECK_RUNS=0` (`AUTO_COMMENTS` unset inherits commands)
- [ ] Also subscribe `issues` if using Route B (`raphael:fix`)

### Dry-run GitHub command smoke (GH-M1/M2)

Keep `RAPHAEL_PARTNER_MODE=dry_run`. Enable parse only for this smoke:

```powershell
$env:RAPHAEL_GITHUB_COMMANDS="1"
# AUTO_COMMENTS unset → follows COMMANDS (terminal comments/labels/sticky)
# Do not set RAPHAEL_GITHUB_CHECK_RUNS=1 unless Checks write is granted and still not required for merge
```

On a fixture Issue/PR linked to a finished dry-run (or pass an explicit `run_id`):

- [ ] `/raphael help` — lists implemented verbs + partner/publish mode; no secrets
- [ ] `/raphael status` (or `/raphael status run-…`) — `run_id`, class, confidence, mode
- [ ] `/raphael feedback rejected` — FR-065 event in `feedback.jsonl` (never merges)
- [ ] `/raphael retry` as admin/team — new `run_id` + `parent_run_id`; **never a live PR** under `PARTNER_MODE=dry_run` even if `RAPHAEL_PUBLISH_MODE=live` is mis-set

Local (no token; assert markdown on the webhook JSON):

```bash
cd agent
pytest -q tests/test_github_commands.py tests/test_github_check_runs.py
```

`cancel` / `diagnose` / `fix` are **not implemented** — expect a deferred reply. Do not require `Raphael (advisory)` on branch protection.

---

## Day 2–3 — Dry-run ≥5 real failures

- [ ] Keep `RAPHAEL_PARTNER_MODE=dry_run` (forces dry-run even if someone sets `PUBLISH_MODE=live`)
- [ ] Capture ≥5 eligible failures into RunStore / triage sheet:

| # | run_id | repo/sha | failure_class | terminal | false positive? | notes |
|---|--------|----------|---------------|----------|-----------------|-------|
| 1 | | | | | | |
| 2 | | | | | | |
| 3 | | | | | | |
| 4 | | | | | | |
| 5 | | | | | | |

- [ ] Record human judgment:

```bash
python -m raphael_agent.scripts.record_feedback `
  --outcome rejected `
  --run-id <run_id> `
  --result-id <result_id> `
  --notes "false positive: probe flapping"
```

Or `POST /v1/feedback` with the same fields.

---

## Day 4 — Triage + go/no-go for live allowlist

- [ ] Re-run `python -m raphael_agent.scripts.pilot_go_nogo`
- [ ] Security review of PAT scopes + SA deny list
- [ ] **GO** only if: ≥5 dry-runs reviewed, false-positive rate acceptable, narrow class chosen

### Live allowlist flip (optional, single class)

```powershell
$env:RAPHAEL_PARTNER_MODE="allowlist"
$env:RAPHAEL_PUBLISH_MODE="live"
$env:RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES="probe_misconfiguration"
$env:RAPHAEL_GITHUB_TOKEN="ghp_..."
python -m raphael_agent.scripts.pilot_go_nogo
```

**NO-GO if:** empty allowlist, missing token, `RAPHAEL_AUTO_MERGE` set, broad allowlist (>3 classes), LLM left on without review.

---

## Day 5 — Limited live drafts + feedback

- [ ] Allowlist live for **one** class only (recommend `probe_misconfiguration`)
- [ ] Confirm PRs are **draft**; humans merge
- [ ] On accept/reject/merge, ensure feedback lands:

```bash
python -m raphael_agent.scripts.record_feedback --outcome accepted --run-id ... --pr-url ...
python -m raphael_agent.scripts.record_feedback --outcome merged --run-id ... --pr-number ...
```

Webhook `pull_request` closed/merged also appends to `feedback.jsonl` under `RAPHAEL_AGENT_DATA_DIR`.

- [ ] Decide deferred engineering (Option B): K8s watcher, App JWT, full FR-065 learning — only from real gaps

---

## Guardrail regression (run anytime)

```bash
cd agent
pytest -q tests/test_guardrails.py tests/test_injection.py tests/test_partner_mode.py tests/test_feedback.py tests/test_github_commands.py
```

These encode the permission-matrix deny list in code.

---

## Related commands

| Command | Purpose |
|---------|---------|
| `python -m raphael_agent.scripts.demo_partner` | Happy-path dry-run demo |
| `python -m raphael_agent.scripts.pilot_go_nogo` | Env go/no-go |
| `python -m raphael_agent.scripts.record_feedback` | Manual FR-065 event |
| `python -m raphael_agent.scripts.metrics` | RunStore aggregates |
| `GET /v1/pilot/go-nogo` | Same verdict over HTTP |
| `POST /v1/feedback` | HTTP feedback ingest |
