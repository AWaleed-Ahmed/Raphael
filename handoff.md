# Raphael handoff

**Audience:** teammate picking up the repo  
**Repo:** https://github.com/AWaleed-Ahmed/Raphael (private)  
**Branch:** `main` (tracking `origin/main`)  
**Last agent work:** Pilot-week Option A — runbook, FR-065 feedback, guardrail tests (`036f9fb`)

This file is the shortest path to context. Deeper sources: [`prd.md`](prd.md), [`CODING_RULE.md`](CODING_RULE.md), [`decision.md`](decision.md).

---

## What Raphael is

Self-healing **deployment** agent for Kubernetes + GitHub:

1. Detect CI / workload failure  
2. Collect evidence (redacted)  
3. Reproduce in an **isolated sandbox** (not production)  
4. Propose a **minimal** config/manifest fix  
5. Validate in the same sandbox → freeze `result_id`  
6. Open a **draft** GitHub PR (human merges)  

**Never:** auto-merge, production cluster writes, reading Kubernetes Secret payloads, free-form `kubectl` from the agent.

---

## Ownership split

| Track | Owner role | Location | Status |
|-------|------------|----------|--------|
| **Engineer A — Sandbox** | Reproduce / prove fixes | `sandbox/` + `contracts/sandbox/` | **Done** (P0–P2) |
| **Engineer B — Agent** | Ingest → diagnose → patch → publish | `agent/` + `contracts/agent/` | **Done** Phases 0–5 + pilot-week Option A |

Agent talks to sandbox **only** via typed HTTP (`create` → `deploy` → `observe` → `validate` → `finalize` → `destroy`). Sandbox never opens PRs.

---

## Phase history (what already shipped)

### Sandbox (Engineer A)

| Phase | What | Status |
|-------|------|--------|
| P0 | kind/mock, clone-at-SHA, fixtures, artifacts | Done |
| P1 | Probe/Helm/Kustomize benchmarks, fidelity, HTTP health | Done |
| P2 | Durable store, TTL/leak cleanup, PSA restricted, stress | Done |

Details: [`sandbox/CHECKLIST.md`](sandbox/CHECKLIST.md), [`sandbox/README.md`](sandbox/README.md).

### Agent (Engineer B)

| Phase | What | Commit (approx) | Status |
|-------|------|-----------------|--------|
| **0** | `agent/` skeleton, `contracts/agent/`, LangGraph stub, sandbox client | `dd9ad79` | Done |
| **1** | GitHub webhooks, RunStore, dedupe/cooldown/concurrency | `ab3adb2` | Done |
| **2** | Deterministic analyzers + constrained patch loop (LLM off by default) | `a17a1dd` | Done |
| **3** | Draft PR publish (`dry_run` default / live optional) | `7a4d0c0` | Done |
| **4** | Budgets, injection fixtures, metrics | `8467e14` | Done |
| **5** | Pilot docs + `PARTNER_MODE` / live failure-class allowlist | `73e2ae0` | Done |
| **Pilot week (Option A)** | 5-day runbook, FR-065 feedback jsonl, guardrail tests | `036f9fb` | Done |

Decisions: `D-20260810-02` … `D-20260810-08` in [`decision.md`](decision.md).

### Happy-path graph

```text
ingest → evidence → diagnose → reproduce → patch → validate → publish_or_escalate
```

Terminals: `success_draft_pr_ready` | `escalated` | `failed_closed`

---

## Repo map

```text
Raphael/
├── handoff.md                 ← you are here
├── README.md                  ← product overview
├── prd.md                     ← requirements + delivery plan
├── CODING_RULE.md             ← binding engineering rules (§13 = agent invariants)
├── decision.md                ← architecture decision log (append-only)
├── contracts/
│   ├── sandbox/               ← frozen sandbox HTTP schemas
│   └── agent/                 ← run_record, diagnosis, publish, feedback, …
├── docs/
│   ├── pilot-install.md
│   ├── permission-matrix.md
│   ├── pilot-acceptance.md
│   └── pilot-week-runbook.md  ← 5-day partner plan
├── agent/                     ← Python package `raphael_agent`
└── sandbox/                   ← Rust Axum controller + kind + tests
```

---

## Get running (Windows-friendly)

### Agent (no Docker)

```bash
cd agent
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e .

python -m raphael_agent.scripts.demo_partner
python -m raphael_agent.scripts.pilot_go_nogo
pytest -q
```

Expect: `status=success_draft_pr_ready`, PR URL with `raphael_dry_run=1`, go/no-go `go=True`, **~75 passed / 1 skipped**.

### Sandbox mock (optional live path)

```bash
# Terminal 1 — repo root
RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 `
  cargo run --manifest-path sandbox/controller/Cargo.toml

# Terminal 2
cd agent
python -m raphael_agent.scripts.smoke --sandbox-mode live
```

Kind: see [`sandbox/README.md`](sandbox/README.md) (`bootstrap.sh`, backend=`kind`, port **8090** not 8080).

---

## Hard guardrails (do not break)

Encoded in code + [`docs/permission-matrix.md`](docs/permission-matrix.md) + `agent/tests/test_guardrails.py`:

1. **Partner default is dry-run** — `RAPHAEL_PARTNER_MODE=dry_run` forces dry-run even if `PUBLISH_MODE=live`.
2. **Live draft PR only if all of:** `PARTNER_MODE=allowlist` + `PUBLISH_MODE=live` + class in `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` + GitHub token.
3. **Empty allowlist ⇒ no live PRs.**
4. **No publish without** frozen sandbox `result_id` + passing validation.
5. **Draft only** — never merge / no `RAPHAEL_AUTO_MERGE`.
6. **LLM off by default** — `RAPHAEL_LLM_DIAGNOSIS=0`.
7. **Untrusted logs ≠ instructions** — injection fixtures must keep failing closed.
8. **Contracts-first** — change `contracts/**/*.json` before Python/Rust types.
9. Append decisions to `decision.md`; don’t rewrite history.

---

## Important env vars

| Variable | Default | Notes |
|----------|---------|--------|
| `RAPHAEL_SANDBOX_URL` | `http://127.0.0.1:8090` | Sandbox controller |
| `RAPHAEL_AGENT_LISTEN` | `127.0.0.1:8091` | Agent HTTP |
| `RAPHAEL_AGENT_DATA_DIR` | `.raphael-agent-data` | Runs + feedback jsonl |
| `RAPHAEL_PARTNER_MODE` | `dry_run` | `dry_run` \| `allowlist` \| `diagnosis_only` |
| `RAPHAEL_PUBLISH_MODE` | `dry_run` | Gated by partner mode |
| `RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES` | empty | e.g. `probe_misconfiguration` |
| `RAPHAEL_GITHUB_TOKEN` | unset | Live draft only |
| `RAPHAEL_GITHUB_WEBHOOK_SECRET` | unset | HMAC; set in real pilot |
| `RAPHAEL_LLM_DIAGNOSIS` | `0` | Keep off unless agreed |
| `RAPHAEL_FEEDBACK_ON_PUBLISH` | unset | `1` logs draft/dry-run events |

Full matrix: [`agent/README.md`](agent/README.md), [`docs/pilot-install.md`](docs/pilot-install.md).

---

## Useful commands

| Command | Purpose |
|---------|---------|
| `python -m raphael_agent.scripts.demo_partner` | End-to-end dry-run demo |
| `python -m raphael_agent.scripts.pilot_go_nogo` | Env go / no-go |
| `python -m raphael_agent.scripts.record_feedback` | Manual accept/reject/merge |
| `python -m raphael_agent.scripts.metrics` | RunStore aggregates |
| `python -m raphael_agent.http_api.app` | Webhooks + `/v1/feedback` + `/v1/pilot/go-nogo` |
| `pytest -q` | Agent suite |
| `pytest -q tests/test_guardrails.py tests/test_injection.py …` | Guardrail regression |

---

## What’s next (recommended order)

### 1. Real pilot week (ops — already documented)

Follow [`docs/pilot-week-runbook.md`](docs/pilot-week-runbook.md):

- Day 0–1: secrets, webhook, local proof  
- Day 2–3: ≥5 real dry-run failures + triage  
- Day 4: go/no-go for live allowlist  
- Day 5: optional **one** class live (`probe_misconfiguration` only) + feedback jsonl  

### 2. Deferred engineering (Option B) — after pilot gaps

Priority when coding again:

1. **Kubernetes workload-health watcher** (FR-002) → same ingest normalize path  
2. **GitHub App JWT** auth (alongside PAT)  
3. CODEOWNERS / reviewers hardening  
4. Fuller FR-065 (learning loop still out of MVP)  
5. Optional: sandbox JSON store → real SQLite (`sandbox/CHECKLIST.md`)

Do **not** invent auto-merge or production remediation.

### 3. Working style that worked here

- One phase (or Option) per PR/commit; test before commit  
- Prefer Sonnet for glue; **Fable/Sol High** for diagnosis/patch/policy  
- Smoke: `demo_partner` + `pytest -q` before claiming done  
- Update `decision.md` + READMEs when behavior/defaults change  

---

## Known footguns

- Controller listen port **8090** (plain `kubectl` without kubeconfig hits `:8080` and can confuse you).  
- Windows console: avoid exotic Unicode in CLI output (cp1252).  
- `gh` CLI may be missing; git HTTPS + credential manager is enough for this remote.  
- Live publish tests need mocked GitHub client or a real token; default CI/tests need **no** token.  
- Agent data dirs are gitignored (`.raphael-agent-data/`).

---

## Quick “am I synced?” checklist

- [ ] `git pull` on `main`  
- [ ] `cd agent && pip install -e . && pytest -q` green  
- [ ] `python -m raphael_agent.scripts.demo_partner` → dry-run success  
- [ ] Skim `CODING_RULE.md` §1 + §13 and latest `decision.md` entries  
- [ ] Read `docs/pilot-week-runbook.md` before partner work  

---

## Contact / continuity

If continuing with an AI coding agent: point it at this file + `prd.md` + `CODING_RULE.md` + `decision.md`, and ask for **Option B.1 (K8s watcher)** or **pilot-week Day N support** — not a rewrite of sandbox/agent phases already marked Done.
