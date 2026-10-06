# Real-kind remediation implementation review — 2026-10-06

Branch: `test/real-kind-closed-loop-proof`, updating [PR #32](https://github.com/AWaleed-Ahmed/Raphael/pull/32). The PR was reconciled with current main; earlier claims are not reused as fresh proof.

## Retained and corrected

- Preserve main's `rollout_resource(signature)` helper and refusal without target identity. Discard the stale `deployment/target` fallback.
- Preserve existing mock/evaluator fixture SHAs and expectations, including bad-image refusal without provenance. Kind uses separate tracked synthetic YAML fixtures copied into temporary Git repositories; actual fixture commit SHAs are recorded.
- Preserve main's decision history; remove the PR's duplicate D-20260930-01 and obsolete kubectl-backend claim.
- Keep backend/context parameters in the real-hooks runner. Add test-only inspection barrier and longer test lease/observation bounds for the real cluster; defaults for current mock callers remain unchanged.
- Replace service-starting/shared-cluster helpers and prefix-based namespace sweeping with a hosted-only disposable cluster and exact owned namespace cleanup. Required preload failures fail the job; runner cleanup uses `finally`, and workflow cluster deletion uses `always()`.
- Keep dry-run publication and disable external/local model/learning paths. The catalog fixture is a loopback REST service; production AgentHooks and the real Supabase REST adapter execute normally. No real Supabase credentials or live ingestion proof is claimed.

## Three hosted controls

| Control | Independent Kubernetes observation | Required agent outcome |
|---|---|---|
| Probe mismatch | Initially not Ready with readiness-probe failure event; Ready Pod independently observed after repair | `fix_finalized`; only two target probe-port replacements; real rollout validation passed and signature cleared; dry-run publication |
| Bad image, no provenance | Initially ErrImagePull/ImagePullBackOff; no Ready assumption from static signature | `escalated / patch_value_unavailable`; no candidate/deployed patch, validation or publication |
| Bad image, verified fixture provenance | Separately deployed healthy source is actually Ready and has a runtime image ID before the baseline is marked verified; failed workload later observed Ready | `fix_finalized`; only one image-line replacement; actual scoped baseline trace and full source SHA recorded; real rollout/signature checks passed; dry-run publication |

The positive image control's catalog row matches company, client, repository, service, environment, Deployment and container. Its commit SHA is the independently deployed healthy fixture's Git SHA. This proves an explicitly seeded catalog boundary and the provenance-gated repair path, not ingestion from production traces or an actual Supabase deployment.

Ignis's known-bad-image YAML heuristic remains in use (#11); the independent Pod failure requirement prevents the runner from claiming Kubernetes failure solely from that heuristic. These controls do not qualify arbitrary registry failures, all manifests or all backend/crash windows.

## Local verification

- `python -m unittest e2e.test_kind_verification`: **9 passed**. Cases: all three expected outcomes; initial-Ready rejection; no-independent-post-Ready rejection; no-provenance patch rejection; extra changed-line rejection; live PR URL rejection; catalog scope filtering; exact owned cleanup; hosted guard before cluster access.
- `python -m pytest evals/test_run_evals.py -q`: **10 passed**. Existing mock fixtures/scored expectations are preserved.
- Initial full suites against reconciled main `78c5e0e`: **327 agent passed (4 existing skips), 77 dispatch passed**. The BYOK merge will be reconciled before final hosted verification.
- `py_compile` for the runner/helpers and `git diff --check`: passed before commit.

No local kind cluster was created or destroyed. Fresh hosted controls are required before merge. The pinned controller remains `contracts-v1.3.0`; this proof needs no public contract change.

## Retained artifacts / proof limits

The `kind-remediation-<run-id>` artifact contains initial Pod/events, subsequent Pod snapshots, real dispatch/connector HTTP traces, runner outcomes, process logs, source fixture SHAs, scoped baseline metadata, catalog queries and cluster version. The existing mock and six Secret-kind controls remain separate gates.

The shared wall deadline is 600 seconds in these test scenarios; lease TTL is also 600 seconds, and connector HTTP budget is extended. This is a deliberate test setting, not an implementation of Ignis #17's runtime timeout/lease coordination. Native BYOK providers, local model #40, real Supabase ingestion and broader partner-pilot gates remain separate work.
