# IDE / Cursor plugin — Product Requirements

**Document status:** P0 implemented (VSIX) — see [`README.md`](README.md)  
**Parent:** [`../prd.md`](../prd.md)  
**Folder:** `interface/IDE/`  
**Product stage:** I2 P0 shipped (`D-20260811-03`)  
**Primary users:** Application engineers and FDEs working in Cursor or VS Code  
**Companion surface:** [`../github-native/prd.md`](../github-native/prd.md)  
**Depends on:** Agent HTTP API (`GET /v1/runs`, feedback, future action APIs); GitHub auth for opening PRs

---

## 1. Vision

Bring Raphael’s **run context and proposed fix** into the editor where the engineer already changes manifests and app config. The IDE plugin is a **thin, trusted client**: it does not re-implement diagnosis or talk to the sandbox; it helps humans **inspect, apply, and follow through** on agent output (especially Route B fix snippets and draft PR review).

Target editors:

1. **Cursor** (primary) — extension compatible with Cursor’s VS Code lineage.  
2. **VS Code** (same codebase via VS Code Extension API) — secondary, same feature set unless Cursor-only APIs are required.

This is **not** a Cursor Cloud Agent product rewrite. Optional later integration with the Cursor SDK (programmatic agents) is explicitly **P2 / exploratory** and must not block P0.

---

## 2. Personas and jobs-to-be-done

| Persona | Job | Success look |
|---------|-----|--------------|
| App engineer | Apply Route B fix snippet without copy-paste errors | One command applies patch to workspace paths |
| App engineer | Review draft PR diff next to local tree | Side-by-side or SCM view with Raphael summary |
| App engineer | Record accept/reject without CLI | Feedback buttons → `POST /v1/feedback` |
| FDE | Point Cursor at local agent during pilot | Status bar shows agent URL + go/no-go |
| SRE | Open failing run from `run_id` in PR comment | Command palette → run timeline |

---

## 3. Product principles

1. **Workspace is sacred:** Never write outside the opened workspace without explicit confirm.
2. **Allowlist-aware:** Refuse to apply hunks that touch paths outside agent/repo allowlist metadata when provided.
3. **Dry-run first:** Default actions cannot live-publish; opening a PR means opening the URL the agent already created, or guiding the human through `gh`/GitHub.
4. **Offline-tolerant UX:** If agent unreachable, show last cached run summary; do not invent diagnosis.
5. **Same vocabulary** as GitHub-native and agent terminals.

---

## 4. Functional requirements

### 4.1 Connection and settings (P0)

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-001 | Setting `raphael.agentBaseUrl` (default `http://127.0.0.1:8091`) | P0 |
| IDE-002 | Setting `raphael.apiToken` (secret storage via SecretStorage API) | P0 |
| IDE-003 | Command **Raphael: Test Connection** → hits go-nogo or health-equivalent | P0 |
| IDE-004 | Status bar item: Connected / Degraded / Offline + partner mode if exposed by API | P0 |
| IDE-005 | Never store GitHub tokens in plaintext settings.json; use SecretStorage | P0 |

### 4.2 Run browser (P0)

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-010 | Tree/view **Raphael Runs**: list recent runs (API list endpoint — **new if missing**, else local cache of opened IDs) | P0 |
| IDE-011 | Run detail webview or markdown preview: status, class, confidence, evidence excerpts, patch, validation, PR URL | P0 |
| IDE-012 | Command **Raphael: Open Run…** prompt for `run_id` | P0 |
| IDE-013 | Command **Raphael: Open Run from Clipboard** if clipboard matches `run-…` | P1 |
| IDE-014 | Deep link handler `vscode://raphael.raphael-ide/run/{run_id}` (and Cursor equivalent) | P1 |
| IDE-015 | Button **Open Draft PR** → external browser to `pull_request_url` | P0 |
| IDE-016 | Button **Open in GitHub Issue** when Route B | P0 |

### 4.3 Apply fix snippet (P0 — core IDE value)

Route B today posts a unified diff or fenced patch on the Issue. The IDE must make that safe to apply.

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-020 | **Raphael: Apply Fix from Run** loads **`delivery_patch`** per [`../prd-i0-api.md`](../prd-i0-api.md) §5 (`candidate_patches[].unified_diff` → hunks → `publish.fix_snippet`) | P0 |
| IDE-021 | Show diff preview before write; require confirm | P0 |
| IDE-022 | Apply via workspace edit; honor `.gitignore` / binary refusal | P0 |
| IDE-023 | Block apply if any path escapes workspace or fails allowlist metadata | P0 |
| IDE-024 | After apply, offer **Create local branch** `raphael/<run-id>-…` (opt-in setting, default off for P0) | P1 |
| IDE-025 | After apply, offer **Open PR on GitHub** via `gh` CLI if available, else open compare URL — **human completes PR**; plugin does not merge | P1 |
| IDE-026 | Record feedback `edited` if user tweaks files after apply before marking accepted | P2 |

### 4.4 Draft PR assist (P0/P1)

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-030 | For `success_draft_pr_ready`, show validation matrix from run in side panel | P0 |
| IDE-031 | **Checkout PR branch** if `gh`/`git` available and user confirms | P1 |
| IDE-032 | Highlight changed files from patch in explorer decoration | P1 |
| IDE-033 | No “Merge Pull Request” command in the extension | P0 |

### 4.5 Feedback and learning (P0/P1)

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-040 | Buttons: Accepted / Rejected / Edited → `POST /v1/feedback` | P0 |
| IDE-041 | Optional note field (bounded length) | P1 |
| IDE-042 | Surface learning snapshot info read-only when `diagnosis.learning` present | P2 |
| IDE-043 | Do not expose a “Rebuild learning snapshot” button that writes production policy | P0 |

### 4.6 Manual trigger (P1)

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-050 | **Raphael: Start Diagnosis for Workspace** → `POST /v1/runs` with `trigger_kind=manual_ide`, `action_id`, commit SHA from git, repo from `git remote` (I0; local agent only in I2) | P1 |
| IDE-051 | Default sandbox mode from settings: `recorded_stub` \| `live` \| `skipped`; live only if user confirms | P1 |
| IDE-052 | Respect agent partner/publish gates; show errors inline | P0 |

### 4.7 Safety (P0)

| ID | Requirement | Priority |
|----|-------------|----------|
| IDE-060 | Refuse to send full `.env` / credential files as “extra evidence” uploads | P0 |
| IDE-061 | Redact paste-into-chat helpers if any (no unconstrained “send workspace to LLM” bypassing agent) | P0 |
| IDE-062 | Telemetry opt-in only; default off for pilot | P1 |
| IDE-063 | Extension must not embed or call `RAPHAEL_SANDBOX_URL` | P0 |

---

## 5. Non-goals

- Replacing the LangGraph agent with Cursor Chat prompts for production remediation.
- Auto-merge from the IDE.
- Cluster explorer / `kubectl` apply UI.
- Multi-root monorepo magic beyond “workspace folder contains the failing service.”
- Shipping a full Cursor SDK cloud-agent workflow as P0 (see §8).
- Windows-only or macOS-only features without Linux parity for pilot FDEs.

---

## 6. UX outline

### 6.1 Activity bar

Icon **Raphael** → views:

1. **Runs** — list + detail  
2. **Actions** — Apply fix, Feedback, Test connection  
3. **Pilot** — go/no-go summary (read-only)

### 6.2 Command palette (P0 set)

```text
Raphael: Test Connection
Raphael: Open Run…
Raphael: Refresh Runs
Raphael: Apply Fix from Run
Raphael: Open Draft PR
Raphael: Feedback Accepted
Raphael: Feedback Rejected
Raphael: Show Run Markdown
```

### 6.3 Apply-fix confirm dialog

Must show:

- `run_id`, failure class, confidence  
- file list + line counts  
- partner/publish mode from agent  
- warning if dry-run PR URL is placeholder  

Primary button: **Apply to workspace**  
Secondary: **Cancel**

---

## 7. Technical design (implement later)

### 7.1 Suggested package layout

```text
interface/IDE/
  prd.md
  README.md                 ← when implemented
  package.json              ← VS Code extension manifest
  src/
    extension.ts            ← activate, commands
    agentClient.ts          ← HTTP client for agent API
    runView.ts              ← tree + webview
    applyPatch.ts           ← diff apply + allowlist checks
    feedback.ts
  media/                    ← icons
  tests/
```

**Language:** TypeScript (VS Code Extension API). Publish as:

- `raphael.raphael-ide` (proposed publisher/name)  
- Installable in Cursor via VSIX for pilot before Marketplace.

### 7.2 Agent API client

```text
GET  {base}/v1/runs/{run_id}
GET  {base}/v1/pilot/go-nogo
GET  {base}/v1/metrics
POST {base}/v1/feedback
POST {base}/v1/runs                 # future — manual trigger
POST {base}/v1/runs/{id}/actions/*  # future — parity with github-native
```

Auth header: `Authorization: Bearer <raphael.apiToken>` (exact scheme fixed at I0 with agent).

### 7.3 Patch apply algorithm

1. Load **delivery_patch** from the run (I0 resolution order).  
2. Parse unified diff.  
3. Verify every `+++` path is under workspace and allowlisted.  
4. Preview in webview.  
5. Apply with VS Code `WorkspaceEdit`.  
6. On failure, show file-level errors; do not partial-commit silently (setting: atomic apply default **on**).

### 7.4 Deep links from GitHub-native

GitHub bot comments may include:

```text
Open in IDE: vscode://raphael.raphael-ide/run/run-abc123
```

Cursor: use the same VS Code URI handler where supported; document fallback “copy run_id → Open Run”.

---

## 8. Cursor SDK (explicitly deferred)

| Use | Priority | Notes |
|-----|----------|-------|
| Extension UI calling agent HTTP | P0 | This PRD |
| Cursor SDK `Agent.prompt` to generate extra local refactors | P2 | Must still pass agent policy if changes are “Raphael remediations”; do not bypass sandbox validation for durable fixes |
| Cloud agent runtime for customer repos | Out of scope | Separate security review |

If SDK is used later, durable remediations still require agent validation + human PR.

---

## 9. Acceptance criteria

1. With local agent serving and a `success_fix_proposed` run, **Apply Fix from Run** updates the correct files after confirm.  
2. Apply refused when diff touches `../outside-workspace` or non-allowlisted path.  
3. Feedback Rejected creates schema-valid feedback event.  
4. Extension never calls port `8090` sandbox API in code or settings defaults.  
5. No Merge command registered.  
6. Works in Cursor and VS Code against the same VSIX for P0 features.  
7. Automated tests: patch apply unit tests + smoke launch (vsix packaging in CI optional for I2).

---

## 10. Test plan

| Layer | What |
|-------|------|
| Unit | Diff parse, allowlist guard, feedback payload |
| Integration | Agent TestClient / recorded HTTP fixtures |
| Manual | Cursor install → demo_partner run_id → apply → feedback |
| Kind pilot | Live sandbox runs still initiated by **agent**, not IDE; IDE only displays |

---

## 11. Milestones

| Milestone | Deliverable |
|-----------|-------------|
| IDE-M1 | Settings, connection, Open Run, markdown detail |
| IDE-M2 | Apply fix + confirm + allowlist guard |
| IDE-M3 | Feedback buttons + Open Draft PR |
| IDE-M4 | Deep links + consume I0 `GET /v1/runs` list |
| IDE-M5 | Manual start diagnosis (`manual_ide`) + local branch opt-in (no auto-push) |
| IDE-M6 | Optional Cursor SDK experiment (doc-only gate); cloud agent URL only after I5 auth |

---

## 12. Resolved questions

1. Agent listen port: **`127.0.0.1:8091`** (`RAPHAEL_AGENT_LISTEN`).  
2. Patch source: **`delivery_patch`** resolution in I0 (not Issue-body scrape as primary).  
3. Publisher / VSIX signing: decide at IDE-M1 packaging; pilot may sideload unsigned VSIX.  
4. Multi-root workspaces: **P2** (single folder P0/P1).  
5. “Open PR” assist: open agent `pull_request_url` in P0; `gh`/PAT optional in P1; no merge.

**I2 network lock:** extension talks to **local** agent only; non-loopback + bearer is I5.

---

## 13. Document control

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | 2026-08-10 | Initial IDE/Cursor PRD; implementation deferred |
| 0.2.0 | 2026-08-11 | Port 8091, delivery_patch, I2 local-only, resolved questions |
