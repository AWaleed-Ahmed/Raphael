# Raphael handoff

**Audience:** teammate picking up the repo  
**Repo:** https://github.com/AWaleed-Ahmed/Raphael (private)  
**Branch:** `main` (tracking `origin/main`)  
**Last agent work:** GitHub-native GH-M1–M5 (commands, auto-comments, labels/sticky footer, opt-in Checks, pilot docs)

This file is the shortest path to context. Deeper sources: [`prd.md`](prd.md), [`CODING_RULE.md`](CODING_RULE.md), [`decision.md`](decision.md).

---

## What Raphael is

Self-healing **deployment** agent for Kubernetes + GitHub:

1. Detect CI / workload failure **or** a labeled GitHub Issue  
2. Collect evidence (redacted)  
3. Reproduce in an **isolated sandbox** (not production)  
4. Propose a **minimal** config/manifest fix (templates on CI path; optional model on Issues path)  
5. Validate in the same sandbox → freeze `result_id`  
6. Deliver via **draft PR** (Route A) or **issue fix snippet** (Route B; human opens PR)  

**Never:** auto-merge, production cluster writes, reading Kubernetes Secret payloads, free-form `kubectl` from the agent.

---

## Ownership split

| Track | Owner role | Location | Status |
|-------|------------|----------|--------|
| **Engineer A — Sandbox** | Reproduce / prove fixes | `sandbox/` + `contracts/sandbox/` | **Done** (P0–P2) |
| **Engineer B — Agent** | Ingest → diagnose → patch → publish + GitHub-native commands | `agent/` + `contracts/agent/` | **Done** Phases 0–6 + Option B + GH-M1–M4 (GH-M5 = docs) |

---

## Phase history

| Phase | Status |
|-------|--------|
| Sandbox P0–P2 | Done |
| Agent 0–5 + pilot Option A scaffolding | Done |
| Phase 6 dual-path Issues + optional model | Done |
| Option B (K8s webhook, App JWT, CODEOWNERS, SQLite RunStore) | Done (code) |
| GitHub-native GH-M1–M4 (agent, default off) | **Done** — `status`/`help`/`feedback`/`retry`/`escalate` + comments/labels/sticky + opt-in Checks |
| GitHub-native GH-M5 (permission matrix + pilot docs) | **Done** (docs only; no `cancel`/`diagnose`/`fix`) |
| Real design-partner week (PRD Phase 5 exit) | **Ops remaining** |

Terminals: `success_draft_pr_ready` | `success_fix_proposed` | `escalated` | `failed_closed`

Decisions: `D-20260810-02` … `D-20260814-06`. GitHub-native: `D-20260814-02` … `D-20260814-06`.

---

## Dual path + GitHub-native knobs

| Knob | Default |
|------|---------|
| `RAPHAEL_ISSUE_TRIGGER_LABEL` | `raphael:fix` |
| `RAPHAEL_LLM_*` | off / OpenAI-compatible URL |
| `RAPHAEL_K8S_WATCHER` | `0` → enable `POST /v1/webhooks/k8s` |
| `RAPHAEL_GITHUB_APP_ID` / `INSTALLATION_ID` / key | unset (PAT first) |
| `RAPHAEL_REVIEWERS_FROM_CODEOWNERS` | `0` |
| `RAPHAEL_AGENT_STORE` | `json` (`sqlite` opt-in) |
| `RAPHAEL_GITHUB_COMMANDS` | `0` — `1` parses `/raphael` on `issue_comment` |
| `RAPHAEL_GITHUB_AUTO_COMMENTS` | unset inherits commands (comments + labels + sticky footer) |
| `RAPHAEL_GITHUB_CHECK_RUNS` | `0` — opt-in advisory Checks; never a required merge gate |

---

## Get running

```bash
cd agent && pip install -e .
python -m raphael_agent.scripts.pilot_local_preflight
python -m raphael_agent.scripts.demo_partner
pytest -q
```

Local Day 0–1 proofs: [`docs/pilot-local-preflight.md`](docs/pilot-local-preflight.md).  
Real partner week: [`docs/pilot-week-runbook.md`](docs/pilot-week-runbook.md).

---

## What’s next

1. **Real partner week** — secrets, ≥5 dry-run failures, permission approval  
2. **Accumulate feedback → rebuild learning snapshots** in partner envs (`RAPHAEL_LEARNING=1`)  
3. **Interface layer** — CLI + I0 HTTP ([`interface/Usage.md`](interface/Usage.md), [`interface/prd-i0-api.md`](interface/prd-i0-api.md)); **IDE P0**: [`interface/IDE/README.md`](interface/IDE/README.md); **GitHub-native GH-M1–M5** in the agent ([`interface/github-native/prd.md`](interface/github-native/prd.md), default off). `cancel` / `diagnose` / `fix` remain unimplemented.  
4. Broader Post-MVP adapters (GitLab, ChatOps, …) from prd §25

Do **not** invent auto-merge or production remediation.
