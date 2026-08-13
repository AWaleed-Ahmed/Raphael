# Raphael Interface Layer

**Status:** Direction accepted · I0 HTTP **served** · **IDE P0 shipped** (VSIX) · **GitHub-native GH-M1 shipped in agent** (`status` / `help` / `feedback`, default off)  
**Interactive path today:** [CLI → `Usage.md`](Usage.md) · [IDE → `IDE/README.md`](IDE/README.md)  
**I0 API lock:** [`prd-i0-api.md`](prd-i0-api.md)  
**Decisions:** [`D-20260810-16`](../decision.md), [`D-20260811-01`](../decision.md), [`D-20260811-02`](../decision.md), [`D-20260811-03`](../decision.md), [`D-20260814-02`](../decision.md)

---

## What this folder is

`interface/` is the **human-facing product layer** for Raphael. It sits *above* the agent and *beside* GitHub/Cursor — never inside the sandbox controller.

| Layer | Path | Job |
|-------|------|-----|
| Sandbox | `sandbox/` | Reproduce & validate failures in isolation |
| Agent | `agent/` | Ingest → diagnose → patch → draft PR / issue snippet (+ future I0 actions / GitHub commands) |
| **Interface** | **`interface/`** | **How humans steer, inspect, apply, and give feedback** |

Until GitHub-native UX and the IDE package ship, **operators use the agent CLI and HTTP API** documented in [`Usage.md`](Usage.md). Those CLIs are **interface v0**; every planned UI action maps to one of them (or to an I0 API once implemented).

---

## Documents in this tree

| File | Purpose |
|------|---------|
| [`README.md`](README.md) | This overview — features, architecture, roadmap |
| [`Usage.md`](Usage.md) | **How to use Raphael interactively via CLI (now)** |
| [`prd.md`](prd.md) | Umbrella PRD — shared principles + locked decisions |
| [`prd-i0-api.md`](prd-i0-api.md) | **I0** endpoints, auth, escalate FSM, `delivery_patch`, correlation |
| [`github-native/prd.md`](github-native/prd.md) | GitHub Issues/PRs/Checks slash-command product spec |
| [`github-native/templates/`](github-native/templates/) | GH-M1 reply copy (`status.md`, `help.md`) |
| [`IDE/prd.md`](IDE/prd.md) | Cursor / VS Code extension product spec |
| [`IDE/README.md`](IDE/README.md) | **Install VSIX + use the P0 extension** |

```text
interface/
├── README.md
├── Usage.md
├── prd.md
├── prd-i0-api.md
├── github-native/
│   ├── prd.md
│   └── templates/
└── IDE/
    └── prd.md
```

Wire schemas (not served yet): `contracts/agent/run_list_response.json`, `run_create_*.json`, `run_action_*.json`.

---

## Product vision

Raphael already delivers remediation as **draft PRs** (Route A) and **issue fix snippets** (Route B). The interface layer makes those outcomes **interactive**:

1. **See** a run’s diagnosis, evidence, sandbox `result_id`, and delivery URL.  
2. **Steer** — retry, escalate, cancel, or start a safe diagnosis — without changing production.  
3. **Act** — apply a Route B snippet in the editor, or jump to the draft PR.  
4. **Learn** — record accepted / rejected / merged / deploy outcomes for offline learning.

Hard product promise (all surfaces, including CLI):

- No auto-merge  
- No production cluster writes  
- No direct calls to the sandbox HTTP API from human UI clients  
- Agent guardrails stay authoritative  

---

## Locked decisions (summary)

| Topic | Lock |
|-------|------|
| Agent listen | `127.0.0.1:8091` |
| Auth | Non-loopback requires `RAPHAEL_INTERFACE_TOKEN` bearer |
| Commands | `/raphael feedback accepted\|rejected\|edited` (no `/raphael accept`) |
| Command host | Agent (`RAPHAEL_GITHUB_COMMANDS=0` default) |
| ACL | write: status/help/feedback; privileged team: retry/diagnose/fix/escalate/cancel |
| Checks | Advisory; conclusion **`neutral`** by default |
| IDE I2 | Local agent only |
| IDE git P0 | Open draft PR URL only; no auto-push |
| GitHub App | Single App for pilot |
| Patch apply | `delivery_patch` resolution in I0 |

---

## Surfaces

### 1. CLI (available now — interface v0)

Full walkthrough: **[`Usage.md`](Usage.md)**.

| Capability | How (today) |
|------------|-------------|
| Safe preflight | `pilot_go_nogo` / `pilot_local_preflight` |
| End-to-end dry-run remediation | `demo_partner` |
| Live or stub sandbox smoke | `smoke` |
| HTTP webhooks + run GET | `raphael-agent-serve` (`:8091`) |
| Human feedback (FR-065) | `record_feedback` |
| Operator metrics | `metrics` |
| Offline learning snapshot | `learn` + `RAPHAEL_LEARNING=1` |

### 2. GitHub-native (GH-M1 in agent — default off)

Runtime lives in the **agent** (`raphael_agent.github_commands`), not a split worker. `interface/github-native/` owns the PRD and reply templates.

Enable with `RAPHAEL_GITHUB_COMMANDS=1`. Parsing does **not** run at default `0`. Bot self-comments are ignored. This path does **not** call the sandbox HTTP API and does **not** widen partner/publish allowlists.

| Knob | Default | Meaning |
|------|---------|---------|
| `RAPHAEL_GITHUB_COMMANDS` | `0` | Master switch for `issue_comment` command parse |
| `RAPHAEL_GITHUB_COMMAND_PREFIX` | `/raphael` | Command prefix |
| `RAPHAEL_GITHUB_COMMAND_TEAM` | unset | Privileged-verb team slug and/or comma-separated logins |
| `RAPHAEL_GITHUB_COMMAND_TEAM_MEMBERS` | unset | Extra privileged logins (no Teams API in GH-M1) |
| `RAPHAEL_GITHUB_COMMAND_RATE_LIMIT` | `10` | Max commands / hour / repo+actor (GH-053) |
| `RAPHAEL_GITHUB_BOT_LOGIN` | `raphael-agent` | Ignore this login (and `login[bot]`) |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` | **Deferred (GH-M4)** |

| Verb | GH-M1 |
|------|--------|
| `status [run_id]` | Implemented — explicit arg → thread marker → store lookup by Issue/PR number |
| `help` | Implemented — verbs + partner/publish mode (no secrets) |
| `feedback accepted\|rejected\|edited` | Implemented — FR-065 jsonl, never merge |
| `retry` / `escalate` / `cancel` / `diagnose` / `fix` | **Not implemented** (GH-M2+) |
| Check Runs | **Not implemented** (GH-M4); advisory `neutral` when it lands |

ACL: write collaborators (`OWNER` / `MEMBER` / `COLLABORATOR`) → `status` / `help` / `feedback`. Everything else requires admin (`OWNER`) or team membership.

Local test (no GitHub token; webhook JSON includes the markdown `reply`):

```bash
cd agent
pytest -q tests/test_github_commands.py
# optional live webhook against raphael-agent-serve:
#   RAPHAEL_GITHUB_COMMANDS=1
#   POST /v1/webhooks/github  X-GitHub-Event: issue_comment
```

`status` / `feedback` correlation: `/raphael status run-abc123`, then `<!-- raphael:run_id=… -->` or `raphael:run_id=…` on the Issue/PR body, then latest run for that number. Duplicate GitHub deliveries are idempotent (`comment_id` / `X-GitHub-Delivery`).

### 3. IDE / Cursor plugin (P0 shipped)

See [`IDE/README.md`](IDE/README.md). Install via VSIX; Runs panel, Apply Fix, Open Draft PR, Feedback.

ChatOps (Slack/Teams) is **not** in this folder — root [`prd.md`](../prd.md) §25.

---

## Architecture

```mermaid
flowchart TB
  subgraph now [Available_now]
    CLI[Agent_CLI_and_serve]
    GH[GitHub_native_GH_M1]
    IDE[Cursor_VSCode]
  end
  subgraph later [Deferred_UI]
    GH2[retry_escalate_Checks]
  end
  subgraph core [Core]
    API[Agent_HTTP_8091]
    AG[LangGraph]
    SB[Sandbox_8090]
  end
  CLI --> API
  GH --> API
  IDE --> API
  API --> AG
  AG --> SB
```

**Rule:** Interfaces never talk to `RAPHAEL_SANDBOX_URL`. Only the agent does.

---

## Delivery phases

| Phase | Focus | Exit |
|-------|--------|------|
| **I0** | Contracts (docs+schemas done; HTTP next) | [`prd-i0-api.md`](prd-i0-api.md) |
| **I1** | GitHub-native P0 commands in agent | GH-M1 `status`/`help`/`feedback` (this change); retry/escalate still GH-M2 |
| **I2** | IDE P0 vs local agent | Apply fix + feedback |
| **I3** | Advisory Checks | `neutral` default |
| **I4** | IDE decorations / branch opt-in | |
| **I5** | Non-loopback auth, harden | Permission-matrix |

---

## Related docs

| Doc | Why |
|-----|-----|
| [`Usage.md`](Usage.md) | CLI operator manual |
| [`prd-i0-api.md`](prd-i0-api.md) | Action API lock |
| [`../agent/README.md`](../agent/README.md) | Agent setup |
| [`../docs/permission-matrix.md`](../docs/permission-matrix.md) | May / may not |
| [`../handoff.md`](../handoff.md) | Team context |

**Use Raphael today:** open [`Usage.md`](Usage.md).
