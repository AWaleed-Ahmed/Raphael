# Raphael Decision Log

**Purpose:** Track product/architecture decisions for Raphael so future work stays consistent.  
**Format:** Each entry records the decision, why, alternatives considered, and status.  
**Rule:** When we make a new meaningful choice, append a new dated entry here. Do not rewrite history — supersede with a new entry that references the old ID.

---

## How to use this file

1. Add a new entry at the **top of the log** (newest first) when a decision is made.
2. Use a stable ID: `D-YYYYMMDD-NN` (date + sequence that day).
3. If a decision changes later, mark the old one `superseded` and link the new ID.
4. Keep entries short. Link to `prd.md`, `CODING_RULE.md`, or PRs when useful.

### Entry template

```markdown
### D-YYYYMMDD-NN — Short title
- **Status:** accepted | superseded by D-... | deprecated
- **Date:** YYYY-MM-DD
- **Owners:** names / roles
- **Decision:** what we chose
- **Why:** reason(s)
- **Alternatives:** what else we considered and why not
- **Consequences:** what this forces or unlocks
```

---

## Decision log (newest first)

### D-20260810-03 — Agent Phase 1: GitHub ingest + JSON run store + policy gates
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Implement FR-001/003–006 under `agent/raphael_agent/ingest` with Starlette webhook (`/v1/webhooks/github`), HMAC via `RAPHAEL_GITHUB_WEBHOOK_SECRET` (optional in local dev when unset), durable JSON `RunStore` under `RAPHAEL_AGENT_DATA_DIR`, and fingerprint `tenant|repo|commit|env|provisional_failure_key`. Cooldown + max concurrent runs are env-configurable. Evidence facade calls GitHub Actions adapter then fixture stub; redaction helpers land now. K8s watcher deferred. Graph auto-run from webhook is opt-in (`RAPHAEL_INGEST_RUN_GRAPH`).
- **Why:** Keeps Phase 0 entry shape (`normalize → initial_run_state → graph`) while making ingest real and fail-closed on duplicates/runaway concurrency.
- **Alternatives:** Require secret always (blocks local curl demos); SQLite immediately (premature); always run full graph on webhook (too heavy for intake).
- **Consequences:** Phase 2 can attach analyzers/patch without redesigning fingerprints or webhook auth. Supplements D-20260810-02.

### D-20260810-02 — Agent Phase 0: `agent/` package + in-memory LangGraph stub
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer B + coding agent
- **Decision:** Place the agent track under top-level `agent/` with importable package `raphael_agent` (not under `sandbox/`, not named `raphael_agent/` at repo root). Freeze agent wire shapes in `contracts/agent/`. Phase 0 LangGraph uses an **in-memory** compiled graph (no checkpointer); the inspectable durable object is the `run_record` / `RunState` dict. Sandbox HTTP base URL defaults to `http://127.0.0.1:8090` via `RAPHAEL_SANDBOX_URL`. Offline smoke uses recorded fixtures when `/health` is down.
- **Why:** Matches CODING_RULE boundary (agent outside `sandbox/`); `agent/` is the suggested short layout; checkpointer/persistence can land in Phase 2 without rewriting node contracts.
- **Alternatives:**
  - `raphael_agent/` at repo root — clearer package name, noisier tree next to `sandbox/`.
  - Sqlite/Postgres LangGraph checkpointer in Phase 0 — premature before real ingest.
  - Put orchestration under `sandbox/harness` — rejected; harness is not the agent.
- **Consequences:** Engineer B extends `agent/raphael_agent/{ingest,evidence,...}`; publish remains a no-op until a sandbox `result_id` exists. Supersedes the “do not start agent” portion of D-20260809-02 for this explicit Phase 0 request.

### D-20260810-01 — P0: clone-at-SHA, secret fixtures, observe artifacts; Docker blocked without sudo
- **Status:** accepted
- **Date:** 2026-08-10
- **Owners:** Engineer A + coding agent
- **Decision:** Implement FR-030 clone-at-SHA via `repository.clone_url`, apply synthetic secret fixtures on create, capture bounded event/log artifacts on observe. Install kubectl/kind/helm to `~/.local/bin`. Docker install left to the user (`sandbox/kind/install-docker.sh`) because sudo password is required.
- **Why:** Unblocks P0 code paths without waiting on Docker; kind bake-off remains the remaining P0 gate.
- **Alternatives:** Block all P0 until Docker works — slower. Embed a rootless container runtime — out of MVP scope.
- **Consequences:** Mock tests cover new P0 features; kind verification still required before demo claims.

### D-20260809-11 — Add `finalize_result` as sixth sandbox verb (Option B)
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Add `finalize_result(sandbox_id) -> result_id` that freezes an **immutable** validated-fix record (patch/files or rendered manifests, before/after signatures, validation matrix, fidelity, artifact ids). Sandbox still does **not** open PRs or push Git. Agent later publishes the PR from this `result_id`. Also expose `GET /v1/sandboxes/{id}/result` to read the frozen record.
- **Why:** The five lifecycle verbs prove a fix worked but did not mint an auditable “this exact fix passed” object. Relying on agent memory alone is weaker for audit/replay.
- **Alternatives:**
  - **Option A:** only enrich `run_validation` response / soft result fields — smaller, but no explicit freeze/idempotent handoff.
  - Put `open_pull_request` in sandbox — rejected; GitHub publishing is Engineer B / agent track.
  - Keep five verbs only — rejected after product discussion.
- **Consequences:** Agent-facing control plane is now six verbs (+ health/GET result). `CODING_RULE.md` and contracts updated. Finalize fails closed unless validation passed.

### D-20260809-10 — Decision log file lives at repo root as `decision.md`
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Keep a running decision log in [`decision.md`](decision.md) at the repository root.
- **Why:** First-time sandbox project; need a durable record of “why we chose X” without digging through chat.
- **Alternatives:**
  - Only chat history — gets lost / hard to search.
  - ADR folder with many files — better later at scale; overkill for MVP.
- **Consequences:** Update this file whenever architecture or process choices change.

---

### D-20260809-09 — Mock cluster backend for local/CI without Docker
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Default local development uses `RAPHAEL_CLUSTER_BACKEND=mock`. Real kind/kubectl is optional via `kind` / `kubeconfig` backend.
- **Why:** This environment had no Docker; we still needed to finish phases and tests. Mock preserves the same five JSON APIs.
- **Alternatives:**
  - Require Docker/kind for every test — blocks progress here.
  - Fake only at the HTTP layer — would not exercise domain/render/observe logic.
- **Consequences:** Mock is for contracts + deterministic signatures. Real fidelity still needs kind before production claims. Fidelity report must disclose mock gaps.

---

### D-20260809-08 — Isolation defaults: namespace-per-run + policy blocks
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** On create: labeled namespace, ResourceQuota, LimitRange, default-deny NetworkPolicy, dedicated ServiceAccount. Policy rejects privileged, hostNetwork, hostPID, hostPath, and non-fixture Secrets. Destroy is idempotent. TTL reaper cleans expired sandboxes.
- **Why:** PRD trust boundary; cheapest strong isolation inside one shared cluster.
- **Alternatives:**
  - Cluster-per-run — stronger isolation, too slow/expensive for MVP.
  - Soft isolation without NetworkPolicy — unsafe for demos that claim isolation.
- **Consequences:** Real kubectl backend applies isolation manifests; mock simulates create/destroy and policy checks in-process.

---

### D-20260809-07 — Failure signatures are deterministic structured objects
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** `observe_failure` returns a typed `failure_signature` (class, key, normalized fields, evidence refs). Analyzers run in code, not via LLM.
- **Why:** Saves agent tokens; makes before/after validation machine-checkable; matches “deterministic before probabilistic.”
- **Alternatives:**
  - Free-form prose diagnosis in the sandbox — burns tokens and is hard to test.
  - Only non-zero exit codes — too weak (PRD requires signature match).
- **Consequences:** Agent later ranks hypotheses using these signatures; sandbox never “explains” with an LLM.

---

### D-20260809-06 — Pluggable manifest renderers: YAML → Helm → Kustomize
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** `ManifestRenderer` selected by `manifests.type`. Implement order: plain YAML first, then Helm, then Kustomize. Same `deploy_revision` API for all.
- **Why:** Scalable without rewrite; YAML is cheapest to learn; Helm matches PRD config examples; Kustomize needed for overlay failure classes.
- **Alternatives:**
  - Helm-only from day one — steeper learning curve; locks format.
  - YAML-only forever — not realistic for customer repos.
  - k3d-specific tooling baked into render path — rejected; renderers stay backend-agnostic.
- **Consequences:** Adding a new packager means a new adapter, not a new controller API.

---

### D-20260809-05 — Local cluster tool: kind (not k3d); one cluster, many namespaces
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Use **kind** for the local/demo Kubernetes backend. Create **one shared cluster**, and **one namespace per run** (`raphael-run-<run_id>`). Bootstrap lives under `sandbox/kind/`.
- **Why:** Closer to standard customer Kubernetes; better long-term fidelity; cheaper than cluster-per-run; API can later point at a remote sandbox cluster without caller changes.
- **Alternatives:**
  - **k3d** — faster/lighter, but k3s can differ from full upstream K8s.
  - New kind cluster per run — slow, heavy, expensive.
  - Only namespaces on a random shared laptop cluster with no bootstrap — hard to reproduce.
- **Consequences:** Need Docker to run real kind. Until then, use mock backend. Scripts must stay idempotent.

---

### D-20260809-04 — Shared contracts in `contracts/sandbox/` (JSON Schema)
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent (shared with future Engineer B)
- **Decision:** Freeze the five sandbox verb request/response shapes (plus `failure_signature`, `fidelity_report`, `error_envelope`) as JSON Schema under `contracts/sandbox/`. Change contracts before Rust/Python types.
- **Why:** Sandbox and future agent can be built in different rooms and still plug together. Saves agent tokens by forcing structured I/O.
- **Alternatives:**
  - Types only inside Rust — agent/Python would guess shapes.
  - Protobuf/gRPC first — stronger typing, heavier for MVP HTTP demo.
  - OpenAPI-only without schemas — fine later; JSON Schema is enough now.
- **Consequences:** Contract tests in the harness must catch drift. Breaking changes need a version bump story.

---

### D-20260809-03 — Rust controller + Python harness only
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Production sandbox controller is **Rust** (Axum HTTP JSON service). **Python** is only for demo scenarios, contract tests, and e2e calls to the API — not a second controller.
- **Why:** Matches PRD (Rust for infra orchestration, Python for later agent). Keeps heavy K8s work out of the agent tool loop. Clean boundary for LangGraph later.
- **Alternatives:**
  - **Python-only sandbox** — faster early demos, higher risk of “just shell kubectl,” weaker long-term controller.
  - Rust everywhere including tests — slower scenario authoring.
  - Agent shells out to kubectl directly — burns tokens and breaks isolation.
- **Consequences:** Harness must use HTTP (`httpx`). Controller owns kubeconfig. Five verbs only for agent-facing control plane.

---

### D-20260809-02 — All sandbox work under `sandbox/` until agent connect is requested
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Engineer A + coding agent
- **Decision:** Implement sandbox subsystem only under `sandbox/` (plus shared `contracts/` and root rules). Do not start LangGraph/agent code until explicitly asked to connect.
- **Why:** Split ownership (Engineer A sandbox vs Engineer B agent); avoid one-shot sprawl; keep agent token use low by finishing deterministic APIs first.
- **Alternatives:**
  - Build agent and sandbox together immediately — higher coupling and token cost.
  - Put controller at repo root without `sandbox/` prefix — muddier ownership.
- **Consequences:** Integration with agent is a later explicit phase.

---

### D-20260809-01 — Process: co-plan, coding rules first, then co-develop by phase
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** User (Engineer A) + coding agent
- **Decision:** Plan together; write [`CODING_RULE.md`](CODING_RULE.md) first; after plan approval, co-develop phase by phase (not a blind one-shot). User may also request full-phase execution in one pass (as done for the initial sandbox implementation).
- **Why:** User is new to K8s/sandboxes; needs shared rules and stepwise clarity while still shipping.
- **Alternatives:**
  - Agent-only planning, user-only coding — slower feedback.
  - Pure one-shot with no rules doc — architecture drifts.
- **Consequences:** [`CODING_RULE.md`](CODING_RULE.md) is binding for sandbox code. Phase exit criteria matter even when multiple phases land together.

---

### D-20260809-00 — Product baseline from `prd.md`
- **Status:** accepted
- **Date:** 2026-08-09
- **Owners:** Product / both engineers
- **Decision:** Raphael MVP is a self-healing deployment agent that observes CI/K8s failures, reproduces in an isolated sandbox, proposes a minimal Git fix via PR, and never writes to production. Sandbox APIs are the five verbs in PRD §20.1.
- **Why:** Core product differentiator is evidence-backed, reproduced, validated fixes under human Git controls.
- **Alternatives:**
  - Auto-remediate production in-place — rejected for MVP (too dangerous).
  - Advice-only chatbot with no sandbox — rejected (weak trust).
- **Consequences:** All sandbox design must support reproduce → validate → report, fail closed, and secret non-exfiltration.

---

## Quick index

| ID | Topic |
|---|---|
| D-20260810-03 | Agent Phase 1 GitHub ingest + run store/policy |
| D-20260810-02 | Agent Phase 0 `agent/` + in-memory LangGraph |
| D-20260810-01 | P0 clone-at-SHA / fixtures / Docker sudo gate |
| D-20260809-00 | Product baseline (PRD) |
| D-20260809-01 | Co-plan / rules-first / phased co-dev |
| D-20260809-02 | `sandbox/` boundary until agent connect |
| D-20260809-03 | Rust controller + Python harness |
| D-20260809-04 | JSON Schema contracts |
| D-20260809-05 | kind + namespace-per-run |
| D-20260809-06 | YAML → Helm → Kustomize renderers |
| D-20260809-07 | Deterministic failure signatures |
| D-20260809-08 | Isolation + policy + TTL |
| D-20260809-09 | Mock backend for no-Docker/CI |
| D-20260809-11 | `finalize_result` sixth verb (Option B) |
| D-20260809-10 | This decision log |
