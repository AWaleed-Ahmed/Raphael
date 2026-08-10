# Raphael Sandbox — Remaining Checklist

**Scope:** Engineer A / sandbox side only (not LangGraph, not GitHub PRs).  
**Status key:** `[ ]` todo · `[~]` partial · `[x]` done

Last updated: 2026-08-10

---

## Done already

- [x] `CODING_RULE.md` + `decision.md`
- [x] Frozen contracts under `contracts/sandbox/`
- [x] Rust controller (Axum) with mock + kubectl/kind backends
- [x] Verbs: create, deploy, observe, validate, finalize, destroy (+ GET result, health)
- [x] YAML → Helm → Kustomize render adapters
- [x] Deterministic failure signatures (probe, image, ConfigMap key, OOM, service port)
- [x] Policy blocks (privileged, hostPath, hostNetwork/hostPID patterns)
- [x] Fidelity report fields + secret-fixture *disclosure*
- [x] Manual feature/stress/break suite (`sandbox/tests`)
- [x] kind bootstrap scripts (`sandbox/kind/`)
- [x] kubectl + kind + helm installed to `~/.local/bin`
- [x] **Clone repo at failing SHA** (`repository.clone_url` + commit) — FR-030
- [x] **Synthetic secret fixtures applied** on create (`secret_fixture_set`) with policy label
- [x] **Bounded artifacts on observe** (events + pod logs + manifest artifacts)
- [x] kubectl isolation manifests: ResourceQuota, LimitRange, default-deny NetworkPolicy, SA + PSA labels
- [x] P0 automated tests in `sandbox/tests` feature `p0` (fixtures, artifacts, clone-at-SHA)

---

## P0 — Before trusting a real demo

- [x] Install Docker + usable daemon (`docker info`)
- [x] Run `./sandbox/kind/bootstrap.sh` → `kind-raphael-sandbox` + kubeconfig
- [x] Controller on **8090** with `RAPHAEL_CLUSTER_BACKEND=kind`
- [x] Full suite green on kind: `RAPHAEL_SANDBOX_URL=http://127.0.0.1:8090 sandbox/tests/.venv/bin/python sandbox/tests/test.py`
- [x] Kind-only gaps fixed (observe-before-deploy, real pullable images, PSA baseline, validate timeouts)

**P0–P2 complete** (full suite green on kind, including `p2`). Next is agent track when you want it.


**Known footgun:** with no kubeconfig, plain `kubectl` talks to `http://127.0.0.1:8080`. If the Raphael controller is bound there, create fails with `cluster_unavailable … (post namespaces)`. Default listen is now **8090**.

---

## P1 — PRD sandbox scenarios & fidelity

- [x] Benchmark: **liveness probe starts too early**
- [x] Benchmark: **Helm value-type / render/schema failure**
- [x] Benchmark: **Kustomize renamed resource / broken overlay reference**
- [x] Record tool versions (helm/kubectl/kustomize) on deploy/validate artifacts
- [x] Prefer/record **image digests** when available
- [x] Enforce: material fidelity gaps → `full_validation=false` (do not claim full validation)
- [x] Real **HTTP health** path via `svc/name:port/path` port-forward (mock + kind)

---

## P2 — Pilot hardening

- [x] Persist sandbox metadata + frozen `result_id` (durable JSON document store; SQLite-shaped API/`RAPHAEL_SQLITE_PATH` — swap to SQLite/Postgres when crates.io available)
- [x] TTL reconciler also hunts **leaked** `raphael.managed` namespaces via label/`expires_at`
- [x] Operator/admin: `POST /v1/admin/force-cleanup`
- [x] Pod Security **restricted** enforce (default) + auto-inject restricted `securityContext` on apply
- [x] Artifact retention on local disk (`RAPHAEL_ARTIFACT_DIR`, default 48h purge)
- [x] Stress tests: `p2` parallel create/destroy x8 (+ existing pipeline parallel)

---

## Explicitly out of sandbox (agent track — lives under `agent/`)

Sandbox never owns these. Status as of Agent Phase 6 (dual-path):

- [x] GitHub webhook ingestion (K8s watcher still deferred)
- [x] LangGraph diagnosis + optional LLM hypotheses (LLM default off)
- [x] Patch generation loop (allowlisted, budgeted)
- [x] Open draft GitHub PR from `result_id` (partner dry_run default; live behind failure-class allowlist; no auto-merge)
- [x] Prompt-injection agent policy tests (`agent/fixtures/injection/`)
- [x] Partner install + permission matrix + acceptance checklist (`docs/`)
- [x] Phase 6 dual-path: labeled Issues (`RAPHAEL_ISSUE_TRIGGER_LABEL`) + optional model patch + issue fix-snippet delivery

Still open: K8s watcher, App JWT as primary auth, full FR-065 learning loop, multi-tenant SaaS.

---

## Suggested next 3 checks

1. [x] Full suite green (58 tests) including P2
2. [ ] Optional: swap JSON durable store → real SQLite when crates.io is available
3. [x] Agent track Phase 0–6 dual-path (CI draft PR + Issues fix snippet)
