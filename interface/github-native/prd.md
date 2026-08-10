# GitHub-native interface — Product Requirements

**Document status:** Draft for later implementation  
**Parent:** [`../prd.md`](../prd.md)  
**Folder:** `interface/github-native/`  
**Product stage:** Post-MVP (I1 / I3 in parent plan)  
**Primary users:** Platform/SRE on-call, application engineers reviewing Raphael PRs  
**Depends on:** Agent webhooks + run store; GitHub App (PAT insufficient for rich Checks UX long-term)

---

## 1. Vision

Make **GitHub itself** the interactive console for Raphael: trigger, inspect, steer, and give feedback on remediation runs without a separate web app and without leaving the PR/Issue that already carries the audit story.

Root PRD §13 already requires PRs to be understandable without an agent console. This surface goes further: **actions** (retry, escalate, reject class, re-run validation) become first-class GitHub interactions.

---

## 2. Personas and jobs-to-be-done

| Persona | Job | Success look |
|---------|-----|--------------|
| On-call SRE | Understand why Raphael opened a draft / escalated | Comment or Check shows diagnosis + evidence links in &lt;30s |
| On-call SRE | Retry after flaky CI or missing workspace config | `/raphael retry` creates a new run, linked to prior `run_id` |
| App engineer | Reject a bad proposed fix without hunting CLI | PR comment or review → feedback `rejected` recorded |
| App engineer | Accept Route B snippet path | Issue command → “open PR from snippet” guidance or draft if allowlisted |
| Security admin | Constrain who can force live publish | Commands respect partner mode; no command widens allowlists |
| FDE / pilot | Demo on partner repo | Label + comment flow works in dry-run |

---

## 3. Relationship to existing agent behavior

| Existing today | GitHub-native adds |
|----------------|-------------------|
| `workflow_run` / `check_run` / deployment-status → ingest | Same; plus **interactive** issue/PR comment commands |
| Label `raphael:fix` → Route B | Keep; add command verbs and status replies |
| Draft PR body (FR-060–064) | Structured follow-up comments + Check annotations |
| `pull_request` webhook → feedback jsonl | Explicit `/raphael accept\|reject` and mapped review events |
| Partner dry-run placeholder PR URLs | Commands must not imply live publish when dry-run |

**Boundary:** Detection/normalization stays in `agent/raphael_agent/ingest`. This package owns **command parsing, reply templates, Check Run presentation, and GitHub App UX wiring** that call agent APIs.

---

## 4. Functional requirements

### 4.1 Command surface (P0)

Commands appear as Issue or PR comments (bot ignores its own comments). Prefix configurable; default:

```text
/raphael <verb> [args]
```

| ID | Verb | Behavior | Priority |
|----|------|----------|----------|
| GH-001 | `status` | Reply with run summary for linked `run_id` or latest run for Issue/PR | P0 |
| GH-002 | `retry` | Enqueue new run from same fingerprint/seed; link `parent_run_id` | P0 |
| GH-003 | `escalate` | Mark human-requested escalate; persist feedback/notes; do not invent a patch | P0 |
| GH-004 | `cancel` | Cancel in-flight run if agent supports cancel; else reply with kill-switch guidance | P1 |
| GH-005 | `feedback accepted\|rejected\|edited` | Write FR-065 feedback tied to PR/Issue | P0 |
| GH-006 | `diagnose` | Manual trigger: create run in `diagnosis_only` or partner-safe mode | P1 |
| GH-007 | `fix` | Route B-style: only if label/policy allows; never widens allowlist | P1 |
| GH-008 | `help` | List verbs + current partner/publish mode (no secrets) | P0 |

**ACL (default proposal):** collaborators with `write` on the repo may run P0 verbs; `diagnose` / `fix` / anything that can open a live draft requires repo `admin` **or** membership in a configured GitHub team (`RAPHAEL_GITHUB_COMMAND_TEAM`). Final choice is open question #5 in parent PRD.

### 4.2 Automatic comments (P0)

| ID | Requirement | Priority |
|----|-------------|----------|
| GH-010 | On run terminal `success_draft_pr_ready`, ensure PR exists (agent publish) and post a short “how to review” comment if missing | P0 |
| GH-011 | On `success_fix_proposed`, post/refresh Issue comment with snippet fence + IDE deep link (see IDE PRD) | P0 |
| GH-012 | On `escalated` / `failed_closed`, post terminal reason + evidence pointers + suggested next human step | P0 |
| GH-013 | All bot comments include `run_id`, failure class, confidence, sandbox `result_id` when present | P0 |
| GH-014 | Comments never include secret-like values; reuse agent redaction | P0 |

### 4.3 Labels (P0/P1)

| ID | Requirement | Priority |
|----|-------------|----------|
| GH-020 | Keep `RAPHAEL_ISSUE_TRIGGER_LABEL` (default `raphael:fix`) as Route B trigger | P0 (exists) |
| GH-021 | Apply `raphael:draft`, `raphael:escalated`, `raphael:needs-human` on PRs/Issues from terminal state | P1 |
| GH-022 | `raphael:learning-demoted` optional label when diagnosis.learning.prefer_escalate | P2 |
| GH-023 | Removing `raphael:fix` does not delete history; only stops new Route B triggers | P0 |

### 4.4 Checks and commit status (P1 → I3)

| ID | Requirement | Priority |
|----|-------------|----------|
| GH-030 | Create/update a Check Run `Raphael` on the failing SHA when a run starts | P1 |
| GH-031 | Check output summarizes diagnosis, validation matrix, link to draft PR or escalation | P1 |
| GH-032 | Annotations point at allowlisted file paths when patch touches them | P1 |
| GH-033 | Check conclusion: `neutral` for dry-run success, `success` only when policy says validation passed, `failure` for failed_closed, `cancelled` for cancel | P1 |
| GH-034 | Never mark GitHub “success” in a way that bypasses required human review for merge | P0 |

### 4.5 Pull request experience extensions (P0/P1)

| ID | Requirement | Priority |
|----|-------------|----------|
| GH-040 | Preserve root PRD §13 body sections (agent publish remains authoritative) | P0 |
| GH-041 | Add a sticky “Raphael actions” footer comment: status / feedback commands | P1 |
| GH-042 | Map `pull_request` closed/merged/edited to feedback (exists); surface ack comment optional | P1 |
| GH-043 | Request reviewers from `RAPHAEL_GITHUB_REVIEWERS` + optional CODEOWNERS (exists) | P0 |
| GH-044 | Draft-only: interface must not offer a “Merge” action | P0 |

### 4.6 Safety and policy (P0)

| ID | Requirement | Priority |
|----|-------------|----------|
| GH-050 | Commands respect `RAPHAEL_PARTNER_MODE` / `RAPHAEL_PUBLISH_MODE` / live class allowlist | P0 |
| GH-051 | No command may widen path allowlists or unblock blocked failure classes | P0 |
| GH-052 | Global kill switch / per-repo disable honored; reply explains disabled state | P0 |
| GH-053 | Rate-limit commands per repo and per actor (default: 10/hour) | P0 |
| GH-054 | Idempotent command handling via GitHub `comment_id` / delivery id | P0 |
| GH-055 | All command invocations append audit events on the run record | P0 |

---

## 5. Non-goals

- ChatOps outside GitHub (Slack/Teams).
- Editing production Kubernetes from a comment.
- Auto-merge on `/raphael accept`.
- Replacing branch protection or required checks with Raphael Checks alone.
- Hosting a separate comment parser inside the sandbox controller.
- Scraping arbitrary Issue HTML; only GitHub API + webhook payloads.

---

## 6. UX copy guidelines

- Voice: concise, evidence-first, same as PR body tone.
- Always state **mode**: `dry_run` | `allowlist` | `diagnosis_only`.
- On uncertainty: prefer escalate copy over fake confidence.
- Deep links: prefer GitHub URLs; optional `cursor://` / IDE URI for snippets (coordinate with IDE PRD).

Example `status` reply:

```markdown
### Raphael run `run-abc123`
- **Status:** success_draft_pr_ready
- **Class:** probe_misconfiguration (confidence 0.81)
- **Sandbox result:** `res-…`
- **Delivery:** draft PR → https://github.com/org/repo/pull/42
- **Mode:** partner=dry_run publish=dry_run

Commands: `/raphael feedback accepted` · `/raphael feedback rejected` · `/raphael retry` · `/raphael help`
```

---

## 7. Technical design (implement later)

### 7.1 Suggested package layout

```text
interface/github-native/
  prd.md                 ← this file
  README.md              ← setup (when implemented)
  src/                   ← TypeScript or Python client/handlers (TBD at I0)
  templates/             ← markdown reply templates
  tests/
```

Language choice at I0: prefer **TypeScript** if the GitHub App runs as a small Node service, or **Python** if handlers live beside `agent/` as an optional extra package. Product requirement is language-agnostic; **do not** put handlers inside `sandbox/`.

### 7.2 Event flow

```mermaid
sequenceDiagram
  participant User
  participant GitHub
  participant GHN as github-native
  participant Agent
  User->>GitHub: comment /raphael retry
  GitHub->>GHN: issue_comment webhook
  GHN->>GHN: ACL + rate limit + parse
  GHN->>Agent: POST /v1/runs/{id}/actions retry
  Agent-->>GHN: new run_id
  GHN->>GitHub: create comment status
```

### 7.3 GitHub App permissions (proposed)

| Permission | Access | Why |
|------------|--------|-----|
| Checks | Read & write | Check Runs / annotations |
| Contents | Read | Optional; agent publish may already use PAT/App |
| Issues | Read & write | Commands + Route B comments |
| Pull requests | Read & write | Draft PR comments / labels |
| Metadata | Read | Required |
| Actions | Read | Correlate workflow_run (if not solely via webhook payload) |

**Must not request:** Administration, Secrets, Environments (write), Workflows (write).

### 7.4 Config knobs (proposed)

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAPHAEL_GITHUB_COMMAND_PREFIX` | `/raphael` | Command prefix |
| `RAPHAEL_GITHUB_COMMANDS` | `1` when package enabled | Master switch |
| `RAPHAEL_GITHUB_COMMAND_TEAM` | unset | Optional team slug for privileged verbs |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` | Enable Checks (I3) |
| `RAPHAEL_INTERFACE_AGENT_URL` | agent base URL | Where to call API |

---

## 8. Acceptance criteria

1. On a fixture repo, posting `/raphael status` on an Issue linked to a finished dry-run returns a bot comment with correct `run_id` and mode.
2. `/raphael feedback rejected` appends a schema-valid feedback event and is visible to `raphael-agent-learn`.
3. `/raphael retry` under `PARTNER_MODE=dry_run` never opens a live PR even if `PUBLISH_MODE=live` is mis-set (partner gate wins — same as agent).
4. Check Run (when enabled) never alone satisfies “merge without human.”
5. Unit tests cover command parse, ACL deny, rate limit, and idempotent duplicate delivery.
6. No new code path calls the sandbox HTTP API from this package.

---

## 9. Test plan

| Layer | What |
|-------|------|
| Unit | Verb parser, ACL, template rendering |
| Contract | Action API request/response schemas |
| Integration | Webhook fixture → agent TestClient → comment payload asserted |
| Partner | Dry-run week: ≥5 command interactions recorded |

---

## 10. Milestones

| Milestone | Deliverable |
|-----------|-------------|
| GH-M1 | Parser + `status` / `help` / `feedback` against agent API |
| GH-M2 | `retry` / `escalate` + terminal auto-comments |
| GH-M3 | Labels + sticky PR footer |
| GH-M4 | Check Runs + annotations |
| GH-M5 | Permission-matrix + pilot doc updates |

---

## 11. Open questions

1. Single App vs ingest App + commands App?
2. Should `/raphael accept` mean feedback-only, or also approve the GitHub PR review (still not merge)?
3. Deep link format for IDE (“Open in Cursor”) — custom protocol vs https landing page?
4. Store command transcripts only on run audit, or also a dedicated `interface_events.jsonl`?

---

## 12. Document control

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | 2026-08-10 | Initial github-native PRD; implementation deferred |
