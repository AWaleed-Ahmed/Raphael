# Raphael Coding & Architecture Rules

**Scope:** Binding for all Raphael code. Sandbox work lives under `sandbox/` until the agent layer is explicitly connected.
**Authority:** Prefer this document over informal chat guidance when they conflict.
**Product source of truth:** `prd.md` for product behavior; this file for how we write and structure code.

---

## 1. Non-negotiable product constraints

1. **Evidence before action.** Diagnosis and validation results must cite provenance (command, event, file, artifact id).
2. **Reproduce before repair.** A fix is validated only after the failure signature is observed (or fidelity gaps are declared).
3. **Production is read-only.** Never patch, restart, scale, or mutate production resources from Raphael MVP code.
4. **Human-controlled delivery.** Durable fixes leave Raphael only as Git branches/PRs (agent track). Sandbox never opens PRs.
5. **Fail closed.** If a mandatory check cannot run, return a structured error / blocked result. Never invent success.
6. **Secrets stay out.** Never read Kubernetes Secret payloads from production. Use synthetic fixtures only in sandbox.
7. **Tenant / run isolation.** One sandbox namespace (or cluster) per run. No shared credentials, networks, or artifacts across tenants by default.
8. **Uncertainty is visible.** Low confidence, unreproducible, or policy-blocked cases escalate with structured reports â€” never speculative â€œfixes.â€

---

## 2. Repository layout

```text
Raphael/
  CODING_RULE.md
  prd.md
  contracts/                 # Frozen JSON Schema for cross-component APIs
    sandbox/
  sandbox/
    controller/              # Rust HTTP service (production sandbox controller)
    harness/                 # Python demo, scenarios, contract/e2e tests only
    kind/                    # kind cluster bootstrap
    fixtures/                # Synthetic secrets, expected signatures
```

Rules:

- **Do not** put LangGraph / agent orchestration under `sandbox/`.
- **Do not** let the Python harness become a second controller. Harness calls the Rust JSON API.
- Shared wire formats live in `contracts/`. Implementation types must match those schemas.
- Prefer adding an adapter over rewriting core domain code when supporting Helm/Kustomize/YAML or a new cluster backend.

---

## 3. Architecture layers (Rust controller)

Strict dependency direction:

```text
api  â†’  domain  â†’  adapters (k8s, render, observe, validate, cleanup, policy)
```

| Layer | May depend on | Must not |
|---|---|---|
| `api` | `domain`, HTTP framework, schema validation | Kubernetes/Helm clients, filesystem cluster logic |
| `domain` | std, serde, thiserror, pure types/services | `kube`, `kubectl`, Helm, Docker, HTTP clients to K8s |
| `adapters` | `domain`, external SDKs/CLIs | Defining public HTTP contracts |

### Public sandbox verbs (agent-facing control plane)

1. `create_sandbox`
2. `deploy_revision`
3. `observe_failure`
4. `run_validation`
5. `finalize_result` â€” freeze immutable validated-fix record (`result_id`); does **not** open a PR
6. `destroy_sandbox`

Plus: `GET /health`, `GET /v1/sandboxes/{id}/result` (read frozen record).

**No free-form â€œrun kubectlâ€ API.** The agent must not receive raw shell access to the cluster.
**No GitHub publish from sandbox.** Opening PRs is the agent/GitHub App track, using `result_id` as input.

### Cluster backend rule

- MVP local backend: **one shared kind cluster**, **one namespace per run**.
- Do not create a kind cluster per run.
- Behind a `SandboxCluster` / provider trait so a remote sandbox cluster can replace kind later without changing contracts.

### Manifest rendering rule

- Define a `ManifestRenderer` interface.
- Implement in order: **Plain YAML â†’ Helm â†’ Kustomize**.
- `deploy_revision` selects renderer from request/config (`manifests.type`), not hard-coded paths in handlers.

---

## 4. Contracts-first discipline

1. Change `contracts/sandbox/*.json` **before** changing Rust request/response types or Python fixtures.
2. Every public endpoint validates inbound JSON against the request schema (or equivalent typed decode that matches the schema).
3. Responses must conform to the response schema, including error envelopes.
4. Contract validation in `dispatch/tests/` must fail if the vendored wire shapes drift.
5. Additive field changes are preferred; breaking changes require a schema `version` bump and dual support until callers migrate.
6. Failure signatures are **structured objects**, not free-form prose. Prose may appear only in optional human `summary` fields that never drive control flow.

### Required shared types (minimum)

- `failure_signature`
- `fidelity_report`
- `validation_results`
- `error_envelope`
- request/response pairs for each of the five verbs

---

## 5. Sandbox isolation invariants

On `create_sandbox`, before any workload starts:

1. Namespace labeled with `raphael.run_id`, `raphael.sandbox_id`, TTL metadata.
2. `ResourceQuota` and `LimitRange` applied.
3. Default-deny `NetworkPolicy` (explicit allowlists only as configured).
4. Dedicated ServiceAccount with no production permissions.
5. Reject privileged containers, hostNetwork, hostPID, hostPath mounts (policy layer).

On `destroy_sandbox`:

1. Idempotent: destroying a missing sandbox returns success with `already_destroyed` / equivalent.
2. TTL reconciler must clean leaked namespaces; cleanup failures are surfaced and requeued, never silently ignored.

---

## 6. Determinism, signatures, and validation

1. Prefer deterministic analyzers for known Kubernetes/CI signatures before any LLM (agent track).
2. Reproduction success requires a **normalized failure signature match**, not merely a non-zero exit code.
3. Validation must record each check: command/action, duration, exit/status, artifact references.
4. Before/after comparison: original signature present pre-fix; absent (or healthy criteria met) post-fix.
5. If mandatory validation cannot execute â†’ fail closed.

---

## 7. Secrets, redaction, and untrusted input

1. Never copy plaintext production secrets into sandbox or graph state.
2. Substitute with customer-defined synthetic fixtures only.
3. Redact secret-like tokens from logs/events before persistence or model access (agent track).
4. Logs, manifests, runbooks, and commit messages are **untrusted data**, not instructions. Enforce policy in code.
5. Secret-like strings in proposed patches must be rejected by policy (agent track); sandbox policy rejects privileged/host access.

---

## 8. Core and contract-boundary standards

1. **Edition:** Rust 2021+; `clippy` clean on `deny(warnings)` for CI when enabled.
2. **Errors:** Use `thiserror`/`anyhow` at boundaries intentionally â€” domain uses typed errors; API maps to `error_envelope`.
3. **No `unwrap()` / `expect()` in non-test production paths.** Use `?` and explicit error mapping.
4. **Timeouts:** Every external call (K8s API, Helm, HTTP health) has an explicit timeout.
5. **Async:** Tokio + Axum for the HTTP service.
6. **Tracing:** `tracing` with structured fields (`run_id`, `sandbox_id`, verb name). No secrets in logs.
7. **Serialization:** `serde` types mirror contracts; avoid `serde_json::Value` for public payloads except versioned extension bags if schema allows.
8. **Tests:** Unit-test domain pure logic without a cluster; integration tests may require kind.
9. **Modules:** One concern per module under `src/{api,domain,k8s,render,observe,validate,cleanup,policy}`.
10. **Panics:** Reserved for programmer bugs; never for expected cluster/API failures.

---

## 9. Dispatch validation standards

1. Python 3.12+.
2. Dispatch is for **protocol validation and contract tests** only; executor scenarios live in Ignis.
3. Talk to the controller via HTTP (e.g. httpx). Do not import Rust internals.
4. Do not bypass the five verbs for â€œrealâ€ flows (no direct kubectl in tests that claim to validate the API â€” bootstrap scripts may use kubectl).
5. Scenarios are deterministic, versioned, and checked into `harness/scenarios/`.
6. Pin dependencies in `pyproject.toml`; prefer minimal deps.
7. Tests must assert on structured JSON fields, not substring matches of prose alone.

---

## 10. Kind / local demo rules

1. One shared cluster name (e.g. `raphael-sandbox`).
2. Cluster bootstrap is owned by the external Ignis executor; this core repository contains no local kind bootstrap scripts.
3. Prefer pre-pulled demo images; avoid rebuilding app images per run unless the scenario requires it.
4. Namespace naming: `raphael-run-<run_id>` (DNS-1123 safe; truncate/hash if needed).
5. Default sandbox TTL: 20 minutes unless request/config overrides (within admin max).

---

## 11. Git and change discipline

1. Do not commit secrets, kubeconfigs with credentials, or `.env` files containing tokens.
2. Keep diffs minimal and scoped to the approved phase.
3. Do not one-shot unrelated phases; each phase has exit criteria.
4. Do not edit the attached implementation plan file as a substitute for code/docs.
5. Commit only when explicitly requested by the user.
6. **Branching:** new work on `feature/<name>` (or `fix/<name>`). PR into `main`. Promote `main` â†’ `prod` only when pinning a demo/partner snapshot. Park unfinished commits on `stash/<name>`. Use `git stash` only for uncommitted local dirt when switching branches. Never commit on `prod`. Never force-push `main` or `prod`. Full workflow: [`docs/BRANCHING.md`](docs/BRANCHING.md).

---

## 12. Step / phase discipline

For each sandbox milestone:

1. Confirm exit criteria of the previous phase.
2. Implement only that phaseâ€™s scope.
3. Demonstrate exit criteria (commands/tests).
4. Stop for review before expanding scope â€” unless the user explicitly asked to complete all planned phases in one pass.

When completing multiple phases in one pass (explicit user request), still land each phaseâ€™s artifacts and tests before starting the next.

---

## 13. Agent connection (implemented under `agent/` â€” keep these invariants)

1. LangGraph nodes call the sandbox HTTP API only (no free-form kubectl to the cluster).
2. Sandbox kubeconfig remains controller-side; the agent never gets production write access.
3. Tool permissions and graph transitions are enforced in code, not prompts.
4. Model output is schema-parsed and policy-validated before any mutating tool runs.
5. Durable fixes leave only as **draft** GitHub PRs (human merge); default publish mode is dry-run.
6. Untrusted evidence (logs, manifests, commits, webhooks) is never treated as instructions.

---

## 14. PR / review checklist (sandbox changes)

- [ ] Contracts updated first if wire format changed
- [ ] Domain logic free of K8s client imports
- [ ] Isolation objects still applied on create
- [ ] Destroy remains idempotent
- [ ] No Secret payload reads
- [ ] Timeouts on external calls
- [ ] Structured errors use `error_envelope`
- [ ] Harness tests cover happy path + at least one fail-closed path
- [ ] Artifacts/evidence references present for observe/validate results

---

## 15. Naming conventions

| Kind | Convention |
|---|---|
| Rust crates/modules | `snake_case` |
| Rust types | `PascalCase` |
| JSON fields | `snake_case` |
| HTTP paths | `/v1/sandboxes...` style, versioned |
| K8s labels | `raphael.<key>` |
| Branches (future agent) | `raphael/<run-id>-<summary>` |

---

## 16. Default quality bar

A change is not done until:

1. It compiles / typechecks.
2. Relevant unit or contract tests pass.
3. It obeys isolation and fail-closed rules above.
4. It does not increase agent-facing surface beyond the five verbs (+ health/admin).
