# Raphael handoff

**Audience:** teammate picking up the repo  
**Repo:** https://github.com/AWaleed-Ahmed/Raphael (private)  
**Branches:** `feature/*` → `main` (PRs) → `prod` (promote). Park WIP on `stash/*`. See [`docs/BRANCHING.md`](docs/BRANCHING.md).  
**Last agent work:** GitHub-native GH-M1–M5, telemetry fingerprints, Supabase healthy-trace catalog, source localization, and sandbox candidate handoff

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
| **Engineer B — Agent** | Ingest → diagnose → localize → patch → publish + GitHub-native commands | `agent/` + `contracts/agent/` | **Done** Phases 0–6 + Option B + GH-M1–M5 + FLE/Supabase catalog |

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
| Telemetry fingerprints + APM evidence adapters | **Done** (Prometheus/Alertmanager and provider-neutral evidence paths) |
| Supabase healthy-trace catalog + normalized multi-company identity | **Done** (migrations applied to linked project) |
| Runtime failure → source localization + candidate ranking | **Done** (stack/trace/route/Kubernetes anchors; deterministic scoring) |
| Candidate → sandbox validation handoff | **Done** (patch-file handoff and audit-visible candidate match) |
| ML model research and hosting plan | **In progress** — see below |
| Real design-partner week (PRD Phase 5 exit) | **Ops remaining** |

Terminals: `success_draft_pr_ready` | `success_fix_proposed` | `escalated` | `failed_closed`

Decisions: `D-20260810-02` … `D-20260814-06` (branching `D-20260814-01`). GitHub-native: `D-20260814-02` … `D-20260814-06`.

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

## Git (required from here on)

Do **not** commit on `main` or `prod`.

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feature/short-name
# work, then: git push -u origin HEAD  →  PR into main
```

- **`prod`:** partner/demo pin. Promote with `git checkout prod && git merge --ff-only main && git push`.
- **`stash/<name>`:** parked commits. **`git stash`:** uncommitted local dirt only.
- Never force-push `main` or `prod`.

---

## Get running

```bash
cd agent && pip install -e .
python -m raphael_agent.scripts.pilot_local_preflight
python -m raphael_agent.scripts.demo_partner
pytest -q
```

## ML model and hosting research

The first implementation should not depend on an LLM. Keep diagnosis, candidate
ranking, causality checks, and promotion gates deterministic. Train small models
only where they improve a measurable step, using incidents generated through
controlled fault injection and sandbox outcomes as labels.

### Models we expect to evaluate

| Model | Purpose | Initial approach | Deployment plan |
|-------|---------|------------------|-----------------|
| Failure classifier | Map telemetry to a normalized failure class | Rules first; logistic regression/LightGBM later | Load into the main Raphael API |
| Candidate ranker | Rank files/lines from stack, diff, trace, and history signals | Current weighted deterministic scorer; gradient-boosted ranker later | Load into the main Raphael API |
| Incident similarity | Find prior incidents and fixes | TF-IDF/cosine or compact embeddings | Main API or Supabase-backed batch job |
| Trace/metric anomaly detector | Detect deviations from healthy baselines | Thresholds, edit distance, Isolation Forest | Main API; no separate service initially |
| Patch-template selector | Choose a safe known fix | Deterministic registry/rules | Main API |
| Optional 0.5B explainer | Turn structured evidence into readable rationale/tests | Quantized model + optional LoRA tuning | Separate, optional inference service |

We are researching how these models will be trained, versioned, evaluated, and
served by us. Training data should include the exact candidate, patch, sandbox
result, revert result, and regression result—not only a failure description.
Model output may suggest or explain; deterministic policy and sandbox evidence
must decide whether a fix is causal.

### Hosting plan under a free/demo budget

Start with one `raphael-api` container containing the deterministic engine and
small classical models. Do not deploy one service per model. This avoids network
failures, idle costs, and model-version drift.

The optional explainer is the only model that should initially be separated. A
0.5B model should be quantized and treated as a low-confidence fallback; a
512 MB container may be too small once runtime overhead and context memory are
included. For an always-on demo, an Always Free VM or local machine is more
appropriate than a sleeping free web service. SnapDeploy/Koyeb/Render remain
useful for a public API demo, but free tiers have small memory or sleep limits.

Required service boundaries:

```text
raphael-api       deterministic diagnosis, ML rankers, Supabase, sandbox client
optional-llm      explanation/test suggestions only; never the causal gate
supabase          catalog, incidents, fingerprints, model versions, outcomes
sandbox           isolated customer-environment reproduction and validation
```

Model artifacts must be versioned and accompanied by an evaluation report. Every
inference request should include `model_name`, `model_version`, `run_id`, and an
audit ID. The inference service must have timeouts, authentication, retries, and
a fail-open fallback to deterministic behavior.

Local Day 0–1 proofs: [`docs/pilot-local-preflight.md`](docs/pilot-local-preflight.md).  
Real partner week: [`docs/pilot-week-runbook.md`](docs/pilot-week-runbook.md).

---

## What’s next

1. **Real partner week** — secrets, ≥5 dry-run failures, permission approval  
2. **Accumulate feedback → rebuild learning snapshots** in partner envs (`RAPHAEL_LEARNING=1`)  
3. **Interface layer** — CLI + I0 HTTP ([`interface/Usage.md`](interface/Usage.md), [`interface/prd-i0-api.md`](interface/prd-i0-api.md)); **IDE P0**: [`interface/IDE/README.md`](interface/IDE/README.md); **GitHub-native GH-M1–M5** in the agent ([`interface/github-native/prd.md`](interface/github-native/prd.md), default off). `cancel` / `diagnose` / `fix` remain unimplemented.  
4. Broader Post-MVP adapters (GitLab, ChatOps, …) from prd §25

Do **not** invent auto-merge or production remediation.
