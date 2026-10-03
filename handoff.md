# Raphael handoff

**Audience:** teammate picking up the repo  
**Repo:** https://github.com/AWaleed-Ahmed/Raphael (private)  
**Branches:** `feature/*` → `main` (PRs) → `prod` (promote). Park WIP on `stash/*`. See [`docs/BRANCHING.md`](docs/BRANCHING.md).  
**Historical checkpoint (2026-09-27):** `feature/diagnosis-evidence-boundary` reconciled onto main `bd95ca2`, preserving merged PR #27's patch-store protection. WSL results at that time: dispatch 51 passed; agent 209 passed/4 skipped; evaluator 9 passed; exact whole-state secret regression 12 passed. The three formerly blocked negative cases were activated after proof. This work later merged; see D-20260927-01. Fourth forbidden-patch scenario remains deferred under §17.8.

**Strict-targeting closure (2026-10-01):** [PR #35](https://github.com/AWaleed-Ahmed/Raphael/pull/35) merged at `d88a6be` after Python, contracts, cross-repo E2E/evals, and disposable-kind jobs passed on its final head. It refuses patches without a unique structural target. Exactly two remediation classes, probe and bad-image, are proven to reach `fix_finalized`; missing-config is proven as a correct refusal (`patch_value_unavailable`), not a third safe fix. WSL suites: agent 236 passed/4 skipped, dispatch 72 passed, evaluator 9 passed. See D-20260930-01. Image-replacement provenance and hardcoded expected signature keys remain tracked separately in Raphael #34 and #33.

**Multi-resource eval closure:** [PR #36](https://github.com/AWaleed-Ahmed/Raphael/pull/36) merged at `8766570`. Its immutable fixture `26192b8` has a healthy first Deployment and a broken second probe port. Pre-PR #35 escalated after three empty-marker patches; the strict template finalizes with only the second Deployment's two-line port change. The fresh pinned [hosted run](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37035326891) passed all seven evals and nine evaluator tests. This is one multi-resource proof, not coverage of all manifests. See D-20261001-01.

This file is the shortest path to context. Deeper sources: [`prd.md`](prd.md), [`CODING_RULE.md`](CODING_RULE.md), [`decision.md`](decision.md).

---

## What Raphael is

### Current review checkpoint

- **Image-digest release (2026-10-02):** Ignis PR #16 merged at `ece2029`, tagged as annotated `contracts-v1.2.1`. Digest polling is bounded by existing `wait_seconds`, checks completeness per image, and keeps unresolved-image gaps; mock behavior and public schemas are unchanged (`CONTRACTS_VERSION` remains `contracts-v1.2.0`). Pinned [hosted run 37035326891](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37035326891) passed all four kind cases, mock Scenarios 1–3, real-hooks smoke, and all seven evals. The partially covered two-image case resolved the Ready sidecar and named only the blocked app in the gap. This is narrow fixture/digest verification, not general real-backend qualification; the paired Raphael PR still needs human review. Cosmetic gap-prefix cleanup is tracked in Raphael #37.
- **Secret-template safety finding (closed by PR #35):** The mixed-manifest reproduction exposed fabricated ConfigMap values. Strict evidence-backed targeting now refuses missing-config patches without an evidenced value (`patch_value_unavailable`); no invented value is a safe-fix milestone. Structural Secret-dependency detection remains separately scoped in Raphael #30.

- **Fixture prerequisite (PR #31, merged):** [hosted run 36334290256](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/36334290256) passed both real-kind cases: Ready with the consumed synthetic value, and never-started `CreateContainerConfigError` naming missing `payments-db` without the fixture. Same fixture SHA for both; Pod evidence and real traces uploaded. `contracts-v1.2.0` (`2655790`) fixes the enum; snapshot/runtime pins match. Dispatch distinguishes 422 validation/replay failures from 401/403 auth errors. This proves the narrow prerequisite, not structural detection or full backend qualification. See D-20260927-03.
- PR #29 is merged on current main `0dbbbe0`; older pending-review and unmerged references below are historical, superseded by this checkpoint.

- PR #29 approved with bounded claims (D-20260927-02): explicit textual secret-dependency refusal, not structural inference from `secretKeyRef` ([#30](https://github.com/AWaleed-Ahmed/Raphael/issues/30)); exact injection delta/outcome equality for one manifest-comment fixture with LLM disabled, not whole-file byte identity or universal injection resistance. Named-secret checks cover verified surfaces, not arbitrary logs/storage. Final application/test head CI [36275365505](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/36275365505) is green; merge remains gated on the current PR checks. This supersedes earlier pending-review wording below.

- Release alignment complete: PR #28 merged at `bd95ca2`; `IGNIS_REF` and `CONTRACTS_VERSION` both pin annotated `contracts-v1.1.2` at Ignis `ded0dbd206f13ff59cb114e66dee56d3dbcd31c8`. Main [default CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/36255524251) and [forced-CRLF CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/36255526533) passed. This supersedes earlier pending-release notes.

- Ignis #4 is closed after [PR #12](https://github.com/AWaleed-Ahmed/Ignis/pull/12) merged as `ded0dbd`: YAML render normalizes CRLF; Rust suite 32 passed. Paired Raphael verification landed in PR #28. Forced-CRLF fixture diff counts: probe 30→2, image 26→2. The ConfigMap template historically changed from budget exhaustion to a one-line patch, but that patch fabricated an unevidenced value; it is **not** a safe-fix milestone and is superseded by D-20260930-01. Clone-level fidelity is deferred in Ignis #13; #11 remains deferred. See D-20260926-02 and D-20260927-01.
- PR #26's observation-summary redaction is merged. This evidence-boundary branch adds bounded/redacted source excerpts and bridge `initial_evidence`, without public contract changes. It remains **unmerged**, now tested rather than an unreconciled draft.
- PR #27 strips executable file bodies/diffs from durable connector-run records, including nested proposals, pending actions, and finalized records. Rejected proposals are stripped before append. Whole-record secret-value checks cover JSON and SQLite after real patch generation, not merely absence of `rendered_files`.
- Restart before patch generation re-fetches manifests in the same sandbox. Restart after generated bytes are lost fails closed with `patch_context_lost_on_restart`; missing re-fetch input escalates with `patch_input_unavailable`. Do not describe all dispatch restart points as resumable. See `dispatch/README.md` and D-20260926-01.
- PR #25's three scenarios are activated on this branch only after real passing runs: secret-required → `production_secret_required`, unreproducible → `reproduction_failed`, injection → equivalent probe fix. Ordinary default six-scenario execution also passed. Reports and ordered traces: `evals/out/evidence-boundary-active/`. No enabled-LLM or live Kubernetes proof is implied.
- Existing ingestion/evidence/diagnosis was extended, not rebuilt. Internal bridge tests prove propagation of available evidence; empty ingest runs still require collection. Raw manifest bodies remain ephemeral and patch-only; redacted diagnosis excerpts survive restart.
- Teammate entry-point map and exact gaps: [ingestion/evidence code audit](docs/ingestion-evidence-current-state.md). In particular, Actions log download is not implemented by the current webhook evidence adapter, and raw webhook persistence is outside PR #27's run-record protection.
- CI restart evidence: Scenario 3 killed Ignis at t+0.9s, restarted at t+1.2s, and reached terminal at t+60.8s with the same `sb-b71f383595d8`. This proves the existing whole-Ignis restart scenario with these code changes, not every possible dispatch restart point.

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
| GitHub-native GH-M5 (permission matrix + pilot docs) | **Done** (permission checks, audit events, cancellation safeguards, diagnosis-only mode, and label-gated fixes) |
| **Dispatch orchestration (typed connector loop)** | **Done** â€” job intake, action/result sequencing, budgets, replay idempotency, lease terminalization, and draft-only terminal delivery | `dispatch/` + pinned `contracts/sandbox/connector/v1/` |
| **Dispatch reliability** | **Merged PR #19** — automatic lease reaping and startup rehydration; PR #27 patch-content restart limits are noted above |

| Telemetry fingerprints + APM evidence adapters | **Done** (Prometheus/Alertmanager and provider-neutral evidence paths) |
| Supabase healthy-trace catalog + normalized multi-company identity | **Done** (migrations applied to linked project) |
| Supabase redacted telemetry sink + terminal run outcomes | **In progress** — migration and live fake upload validated; lifecycle integration and PR pending |

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
# Terminal 1: Sandbox (Ignis executor, mock backend)
RAPHAEL_CLUSTER_BACKEND=mock cargo run --manifest-path <ignis-checkout>/controller/Cargo.toml

# Terminal 2: Raphael-core (agent webhooks + dispatch orchestrator, single process)
python run.py
# health: http://127.0.0.1:8091/health
# webhooks: http://127.0.0.1:8091/v1/webhooks/github
```

`run.py` starts both the agent webhook server and dispatch orchestrator in one
process with a shared Orchestrator instance. The ingest→dispatch bridge
(`RAPHAEL_DISPATCH_BRIDGE_ENABLED=1`) submits jobs via direct Python call.

> Single-process startup rehydration and automatic lease reaping are implemented
> (merged PR #19). Multi-instance durable lease ownership is not established by
> that work. PR #27 adds the explicit patch-content recovery limits above.

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

## Whatâ€™s next

1. **Ignis connector implementation** â€” outbound-only connector against the pinned v1 schemas; no customer source code or GitHub credentials in dispatch.
2. **Lease-reaping automation** â€” replace the current manual `POST /v1/leases/reap` invocation with a deployment-owned scheduler or worker before any real pilot.
3. **Startup rehydration** â€” restore in-flight dispatch jobs from `RunStore` into `Orchestrator.jobs` and define durable multi-process lease ownership before any real pilot.
4. **Real partner week** â€” secrets, â‰¥5 dry-run failures, permission approval.
5. **Accumulate feedback â†’ rebuild learning snapshots** in partner envs (`RAPHAEL_LEARNING=1`).
6. **Interface layer** â€” CLI + I0 HTTP ([`interface/Usage.md`](interface/Usage.md), [`interface/prd-i0-api.md`](interface/prd-i0-api.md)); **IDE P0**: [`interface/IDE/README.md`](interface/IDE/README.md); **GitHub-native GH-M1â€“M5** in the agent ([`interface/github-native/prd.md`](interface/github-native/prd.md), default off).
7. **Broader Post-MVP adapters** (GitLab, ChatOps, â€¦) from prd Â§25.
Do **not** invent auto-merge or production remediation.
