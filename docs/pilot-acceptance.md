# Pilot / MVP acceptance checklist (Phase 5)

Mapped to PRD §23 with current Raphael status. Use during design-partner dry-run week.

Legend: **Proven** = covered by agent/sandbox demos or tests · **Partial** = scaffolded · **Deferred** = explicitly out of this pilot cut.

---

## In scope now

| # | PRD §23 criterion | Status | Evidence / notes |
|---|-------------------|--------|------------------|
| 1 | GitHub Actions events trigger idempotent runs | **Proven** | Webhook ingest + fingerprint dedupe/cooldown (`agent/`) |
| 1b | Kubernetes events trigger runs | **Deferred** | K8s watcher not shipped |
| 2 | Evidence with provenance + redaction | **Proven** | Evidence facade + redaction + injection tests |
| 3 | ≥5 supported failures reproduce in sandbox | **Partial** | Sandbox harness scenarios exist; partner demo uses probe path |
| 4 | ≥4/5 correct minimal patches pass checks | **Partial** | Deterministic templates for probe/image/configmap; expand in pilot eval |
| 5 | Before/after failure-signature behavior | **Proven** | Sandbox validate + agent graph |
| 6 | Draft GitHub PRs with required sections | **Proven** | Dry-run always; live draft behind allowlist + token |
| 7 | Unsupported/low-confidence/policy-blocked → no PR | **Proven** | Escalate paths + publish gates |
| 8 | Production K8s read-only; no Secret payloads | **Proven (policy)** | Documented matrix; enforce in partner SA |
| 9 | Sandboxes isolated + TTL cleanup | **Proven** | Sandbox P0–P2 |
| 10 | Inspectable audit trail + terminal reason | **Proven** | `run_record` + RunStore + metrics |
| 11 | Duplicate events ≠ duplicate PRs | **Proven** | Ingest dedupe + publish idempotency |
| 12 | Canonical demo ≤10–15 min ×3 | **Proven (local)** | `recorded_stub` + dry-run smoke / `demo_partner` |
| 13 | GitHub-native commands (GH-M1/M2) | **Proven (code)** | `/raphael status` / `help` / `feedback` / `retry` / `escalate`; default `RAPHAEL_GITHUB_COMMANDS=0`. Retry under `PARTNER_MODE=dry_run` never live-publishes |
| 14 | Terminal comments, labels, sticky footer (GH-M2/M3) | **Proven (code)** | `RAPHAEL_GITHUB_AUTO_COMMENTS` (unset inherits commands). No Merge in the footer; never strips `raphael:fix` |
| 15 | Advisory Check Runs (GH-M4) | **Proven (code), opt-in** | `RAPHAEL_GITHUB_CHECK_RUNS=1`; name `Raphael (advisory)`; conclusion `neutral`; **never** a required merge check |

---

## Partner dry-run week checklist

### Local preflight (no partner required)

- [x] Local Day 0–1 proofs recorded in [`pilot-local-preflight.md`](pilot-local-preflight.md) (`pilot_go_nogo`, `demo_partner`, `pytest`, `metrics`)

### Real partner install

- [ ] Read [`pilot-install.md`](pilot-install.md) + [`permission-matrix.md`](permission-matrix.md)
- [ ] `RAPHAEL_PARTNER_MODE=dry_run` (default)
- [ ] Smoke: `python -m raphael_agent.scripts.demo_partner` → `success_draft_pr_ready`
- [ ] `pytest -q` green in `agent/`
- [ ] Review metrics: `python -m raphael_agent.scripts.metrics`
- [ ] Confirm GitHub token **not** required for dry-run
- [ ] Dry-run command smoke on a fixture Issue (`RAPHAEL_GITHUB_COMMANDS=1`, partner still `dry_run`): `/raphael help`, `/raphael status`, `/raphael feedback rejected`; `/raphael retry` must not live-publish
- [ ] Do **not** add `Raphael (advisory)` as a required branch-protection check
- [ ] Confirm production kubeconfig used by observer (if any) cannot patch/delete or read Secret data
- [ ] Optional: enable **one** class live — `probe_misconfiguration` only — after security review
- [ ] Follow day-by-day plan: [`pilot-week-runbook.md`](pilot-week-runbook.md)
- [ ] Capture accept/reject/merge via `record_feedback` or `pull_request` webhook → `feedback.jsonl`

---

## Explicitly deferred (pilot)

| Item | Notes |
|------|--------|
| In-cluster Kubernetes watcher | Interface stub / future Engineer A+B |
| GitHub App JWT as primary auth | PAT documented; App env vars reserved |
| Full FR-065 learning loop | Jsonl feedback recorder only |
| Multi-tenant SaaS control plane | Out of MVP |
| Auto-merge / production remediation | Forever out for MVP |
| `/raphael cancel` / `diagnose` / `fix` | **Deferred** — GH-M1–M4 shipped; these verbs are not in the pilot cut |
| GitLab / other CI hosts | Post-MVP |

---

## What’s left for a real pilot week

1. Install with partner secrets manager (webhook secret + optional PAT).  
2. Map one repo + staging namespace; confirm SA deny list.  
3. Run dry-run on ≥5 real eligible failures; triage false positives.  
4. Smoke GitHub-native commands on a fixture Issue (`status` / `help` / `feedback`; `retry` stays dry-run).  
5. Optionally flip `RAPHAEL_PARTNER_MODE=allowlist` for `probe_misconfiguration` only.  
6. Collect human accept/reject notes into feedback jsonl.
