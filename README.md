# Raphael

**Raphael** is a self-healing deployment agent for Kubernetes teams.

When a deploy fails in CI or a workload goes unhealthy, Raphael’s job is to:

1. **Detect** the failure from CI / Kubernetes signals  
2. **Investigate** with logs, events, manifests, and commit context  
3. **Reproduce** the failure in an isolated sandbox (not production)  
4. **Propose** a minimal, reviewable fix  
5. **Validate** that fix in the same sandbox  
6. **Open a pull request** with evidence, risk notes, and rollback guidance  

Production stays **read-only** in the MVP. Durable changes only enter through your normal Git review and CI path.

Full product intent: [`prd.md`](prd.md).

---

## What exists today

| Area | Status |
|------|--------|
| **Sandbox controller** (Rust / Axum) | Done — create → deploy → observe → validate → finalize → destroy |
| **Contracts** (JSON Schema) | Frozen under [`contracts/sandbox/`](contracts/sandbox/) + [`contracts/agent/`](contracts/agent/) (skeleton) |
| **Local kind cluster + tests** | P0–P2 complete (58 manual feature tests green on kind) |
| **LangGraph agent / GitHub PRs** | **Phase 2** — deterministic diagnosis + constrained patch under [`agent/`](agent/); publish still no-op (no GitHub PRs yet) |

The sandbox is the safe “reproduce + prove the fix” engine. The agent track calls it with typed HTTP verbs instead of free-form `kubectl`.

---

## Repo map

```text
Raphael/
├── README.md                 ← you are here (what & why)
├── prd.md                    ← product requirements
├── CODING_RULE.md            ← engineering rules for this codebase
├── decision.md               ← architecture decision log
├── contracts/
│   ├── sandbox/              ← frozen sandbox API schemas
│   └── agent/                ← frozen agent run/evidence/diagnosis schemas
├── agent/                    ← Engineer B (Phase 0–2)
│   └── README.md             ← how to run smoke / env vars
└── sandbox/                  ← Engineer A implementation
    ├── README.md             ← detailed how-to / all commands
    ├── controller/           ← Rust HTTP service
    ├── tests/                ← manual feature / stress suite
    ├── harness/              ← scenarios + contract tests
    ├── kind/                 ← local kind bootstrap
    └── fixtures/             ← synthetic secrets, expected signatures
```

---

## Quick start (mock — no Docker)

```bash
cd ~/Documents/work/Projects/Raphael

# Terminal 1 — controller
RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090 \
  cargo run --manifest-path sandbox/controller/Cargo.toml

# Terminal 2 — tests
python3 -m venv sandbox/tests/.venv
sandbox/tests/.venv/bin/pip install httpx
sandbox/tests/.venv/bin/python sandbox/tests/test.py
```

For kind (real local Kubernetes), env vars, APIs, and troubleshooting, see the detailed guide:

**→ [`sandbox/README.md`](sandbox/README.md)**

---

## Design principles (short)

- **Evidence before action** — diagnosis cites signals  
- **Reproduce before repair** — fix is validated in a sandbox  
- **Smallest safe change** — prefer narrow config/code patches  
- **Human-controlled delivery** — PRs, not silent production edits  
- **Uncertainty is visible** — escalate instead of guessing  

Rules that implementers must follow: [`CODING_RULE.md`](CODING_RULE.md).  
Why we chose things: [`decision.md`](decision.md).

---

## Status

Sandbox P0–P2 is complete. Agent Phase 0–2 are under [`agent/`](agent/) (ingest, deterministic diagnosis, constrained patch loop). Next: Phase 3 draft GitHub PR from sandbox `result_id`.
