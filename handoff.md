# Raphael handoff

**Audience:** teammate picking up the repo  
**Repo:** https://github.com/AWaleed-Ahmed/Raphael (private)  
**Branch:** `main` (tracking `origin/main`)  
**Last agent work:** Phase 6 dual-path + Option B (K8s watcher, App JWT, CODEOWNERS, SQLite store)

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
| **Engineer B — Agent** | Ingest → diagnose → patch → publish | `agent/` + `contracts/agent/` | **Done** Phases 0–6 + Option B code |

---

## Phase history

| Phase | Status |
|-------|--------|
| Sandbox P0–P2 | Done |
| Agent 0–5 + pilot Option A scaffolding | Done |
| Phase 6 dual-path Issues + optional model | Done |
| Option B (K8s webhook, App JWT, CODEOWNERS, SQLite RunStore) | Done (code) |
| Real design-partner week (PRD Phase 5 exit) | **Ops remaining** |

Terminals: `success_draft_pr_ready` | `success_fix_proposed` | `escalated` | `failed_closed`

Decisions: `D-20260810-02` … `D-20260810-14`.

---

## Dual path + Option B knobs

| Knob | Default |
|------|---------|
| `RAPHAEL_ISSUE_TRIGGER_LABEL` | `raphael:fix` |
| `RAPHAEL_LLM_*` | off / OpenAI-compatible URL |
| `RAPHAEL_K8S_WATCHER` | `0` → enable `POST /v1/webhooks/k8s` |
| `RAPHAEL_GITHUB_APP_ID` / `INSTALLATION_ID` / key | unset (PAT first) |
| `RAPHAEL_REVIEWERS_FROM_CODEOWNERS` | `0` |
| `RAPHAEL_AGENT_STORE` | `json` (`sqlite` opt-in) |

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
3. **Interface layer (PRD only today)** — [`interface/README.md`](interface/README.md) + CLI guide [`interface/Usage.md`](interface/Usage.md); build later: GitHub-native + IDE/Cursor under `interface/github-native/` and `interface/IDE/`  
4. Broader Post-MVP adapters (GitLab, ChatOps, …) from prd §25  

Do **not** invent auto-merge or production remediation.
