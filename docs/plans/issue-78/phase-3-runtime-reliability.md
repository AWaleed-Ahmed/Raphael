# Phase 3 — Runtime performance, resilience, and safety testing

Date: 2026-10-27. Status: implementation and local measurement completed; acceptance remains deferred.
Results: [Phase 3 report](../../model-readiness-phase-3.md). Memory growth fails the frozen gate; provider, complete graph and downstream crash/recovery requirements remain open.
Tracking: #78 checkpoints **10–13**; CPU/dependency measurements also satisfy the corresponding #66 criteria.
Prerequisites: [Phase 1](phase-1-data-and-acceptance.md), [Phase 2](phase-2-model-evaluation.md). Next: [Phase 4](phase-4-operations-and-rollback.md).

## Goal and boundaries

Establish the deployment envelope in which the existing packaged runtime remains useful and safe. Measure the model runtime separately from original workload/sandbox reproduction. A lightweight inference process does not imply an entire telemetry archive, legacy test environment or Kubernetes cluster fits the same memory budget.

Reuse the original source IDs and frozen evidence from Phase 1. No new fake incident is authored. Concurrency replay, corrupting a disposable artifact copy, killing an owned process, and constraining its memory are explicit operational controls applied while real inputs run; they are not counted as new historical incidents or accuracy cases. If operational perturbations are excluded by the eventual execution scope, the corresponding reliability gates remain untested.

## Proposed deployment profile and budgets

Freeze the actual provider/CPU architecture, OS/container digest, runtime/ML versions and package hashes before measurement. Proposed pilot target: single Linux instance, **2 vCPU / 2 GiB RAM**, one qualified agent deployment and its explicit process model; no horizontal-scaling or GPU claim. Sandbox and dataset preparation are separate resources. Do not provision paid hosting from this plan.

These are proposed budgets to ratify in Phase 1, not current measured results or external SLAs:

| Measurement | Proposed gate / boundary |
| --- | --- |
| Cold startup | 30 independent fresh-process starts; model availability p95 ≤5 seconds; imports and verified artifact loading included |
| Warm inference | 1,000 calls/capability where applicable; p95 ≤50 ms and p99 ≤100 ms for the complete local gateway operation, validation included; cache hits labelled |
| Evidence-size envelope | Freeze actual bounded input sizes from the source manifest; publish bytes/tokens/spans/candidates. Oversized inputs refuse or truncate only via existing documented policy. |
| Process memory | Measure agent and worker process tree/cgroup, not parent-only RSS; steady peak ≤1.5 GiB inside a 2 GiB limit |
| Soak stability | After a 10-minute warm-up, run ≥2 hours at admitted traffic; late steady-window memory growth ≤10% versus first steady window and no continuing upward trend |
| Mixed concurrency | At concurrency 4, ≥1 completed mixed model-evaluation job/second, local runtime errors <1%, and p95 gateway latency within the 50 ms budget; report concurrency 1/4/8/16 saturation separately |
| End-to-end overhead | Paired model-on graph overhead p95 ≤250 ms excluding network/sandbox/workload execution; report complete incident latency separately |
| Recovery | Restart returns runtime health ≤60 seconds; job outcome/recovery follows existing journals/leases without duplicated side effects |

Declare exact duration, mix and measurement boundaries. Realistic partner arrival rates must be checked in Phase 5; this provisional profile qualifies only its measured envelope. If it fails, keep deferred or review a new profile before a new run; never reinterpret model-only results as whole-incident SLOs.

## Checkpoint 10 — Named deployment and CPU costs

**Source cases:** K01 original Kubernetes report, B01 original reproduced code failure, and an O01 recorded telemetry incident. Include all five capability workloads as the larger matrix, with O02/O03 and B02/B03 expanding diversity.

Implementation:

1. Reuse #66's evaluator and benchmark the final installed package from outside the source checkout. Capture wheel/lock/bootstrap hashes, download/install footprint, on-disk dependency size, artifact sizes, fresh process cold loads, warm measurements and process-tree RSS.
2. Alternate paired model-off/on runs to reduce ordering effects; pin CPU allocation and record noisy-neighbor conditions. Healthy caches and prior imports are explicitly warm, not independent cold starts.
3. Attribute graph/evidence/HTTP overhead separately from model compute. Whole-process telemetry archive loading must not be hidden outside memory accounting for the chosen deployment path.

Acceptance: all chosen budgets and complete metadata published; ≥3 original cases, ≥30 cold starts and warm repeats as above. A result on a developer laptop alone does not certify the target container/provider.

## Checkpoint 11 — Concurrency and load

**Source cases:** B01, B02 and B03 real failure evidence; add O01–O03 for trace-heavy mix and K01/K03/K06 for original Kubernetes reports. Repetition creates operational load only, not additional independent accuracy samples.

Implementation:

- Add a small load entry point around the evaluator, proposed `agent/scripts/qualify_model_runtime.py`; avoid a new queue/service unless the current deployment demonstrably needs one.
- Test concurrency 1/4/8/16, a 5-minute warm-up followed by ≥30 measured minutes per admitted plateau, a burst at twice the admitted rate, and the two-hour soak. Pin the traffic mix before final runs and record successful, rejected, timed-out, cancelled and dropped requests.
- Check request-local diagnostics and predictions under concurrent gateway calls. Existing mutable gateway error state and global cache are inspection targets; neither thread safety nor the need for a lock is assumed without a reproducer.
- Repeat a deterministic subset at serial and concurrent settings; outputs/ownership must agree except documented ties/numeric tolerance. If concurrency is unsupported, bound admission explicitly and report a reduced envelope; no silent unbounded threads.

Acceptance: selected capacity gate met, bounded queue/admission behavior, overload visible, zero ownership mixing, zero silently lost accepted work, no duplicate publication/proposal side effects. Saturation beyond the admitted envelope may reject requests safely; it must not bypass policy.

## Checkpoint 12 — Failure and recovery

**Three input sources:** K01, B02 and O03. Run the full fault matrix below against each where applicable; preserve original incident bytes and record a separate control ID for each operational perturbation.

| Control | Required observation |
| --- | --- |
| Missing/corrupted artifact or manifest; mismatched registry hash | Rejection before deserialization; bounded unavailable diagnostic; deterministic fallback/refusal |
| Incompatible ML dependency / estimator warning | Rejection under the existing compatibility policy, without exposing raw exception contents |
| Runtime exception / malformed / nonfinite output | Existing validators refuse safely; no unknown classification, invented candidate or automatic patch |
| Memory limit / owned worker termination / CPU pressure | Job becomes recoverable or safely terminal; no false success; core supervisor/health state accurately reflects availability |
| Restart during inference and during downstream sandbox work | Persisted state, leases and cleanup obey current contracts; executable patch bytes are not reconstructed from unsafe storage |
| Catalog/network interruption | No fabricated healthy baseline or fallback to another tenant; bounded timeout and explicit gap |

Run disposable-copy controls only. Do not corrupt tracked model artifacts or alter the trusted registry to admit a damaged file. Test both a fresh process and a warmed cache: document whether an already verified cached object remains usable and when changes require restart. Hash-validation failure must never be “fixed” by bypassing integrity checks.

Acceptance: every applicable matrix cell has logs and terminal state for the three sources; no crash escapes into a success result, secrets remain absent, health/recovery meets the frozen budget. Do not promise exactly-once remote publication: uncertain outcomes require the existing fail-closed reconciliation path.

## Checkpoint 13 — Safety under concurrency and failure

**Three original input sources:** K01, K04 and K03. Retain authentic inputs; attach explicitly labelled runtime/ownership test controls rather than fabricating incident evidence.

Verify at serial and admitted concurrent load:

- Trust-loader checks remain before deserialization; the same verified bytes are loaded; invalid outputs cannot alter policy state.
- Wrong tenant/company/client context cannot select histories or authorize trace/image baselines. Public test partitions prove implementation controls, not real customer authorization.
- K01 cannot obtain an image replacement without correct independently verified provenance; K04 cannot relax non-root/Secret/security controls; K03 cannot receive an unsupported controller-code “repair.”
- Candidate path/line/symbol/evidence remain canonical; missing baselines abstain; all blocked graph paths retain zero prohibited model/proposal/publication calls.
- Lease expiry, cancellation and runtime failure do not revive work or leave untracked owned sandboxes. Cleanup checks are scoped to resources created by this run; no cluster sweeps.

Acceptance: **zero observed policy bypasses, ownership leaks, unverified replacements, prohibited actions or orphaned owned resources** across the recorded matrix. Counts and limits accompany the zero; this is not a universal guarantee.

## Delivery, tests and exit

Expected seams: existing packaged runtime/cache, gateway diagnostics, existing output validators, graph cancellation/recovery, and `e2e/run_model_graph_kind.py` / `run_kind_verification.py`. Modify a seam only after a failing reproducer identifies a problem; no broad runtime refactor or speculative new configuration.

- [ ] `runtime-profile.json`, cold/warm/load samples, process-tree resource series, failure matrix and CPU-cost report link exact source IDs and revisions.
- [ ] New meaningful tests cover discovered races/recovery defects; existing agent, dispatch, schema, tenant, provenance, blocked-path and paired E2E suites pass for changed behavior.
- [ ] Every checkpoint has ≥3 real source inputs; operational perturbations are separately labelled.
- [ ] Selected deployment budget passes or a smaller qualified scope is explicitly reviewed; unmet resource/compatibility claims stay deferred.
- [ ] No persistent environment, public issue state, production deployment or default flag is changed by measurement alone.

Hand off the admitted envelope and exact recovery behavior to Phase 4. Capabilities failing Phase 2 cannot gain quality acceptance merely by passing this phase.
