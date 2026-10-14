# Paired Ignis #11 implementation review

Date: 2026-10-06. Branch: `codex/raphael-image-pull-evidence`; base `8601763`.
Status: implementation present, behavioral qualification pending.

## Small commits

| Commit | Change |
| --- | --- |
| `7ec97c3` | Shared cause/identity gate; deterministic, BYOK and local-model diagnosis respect pull refusals; retain backend returned by sandbox creation. |
| `0163be3` | Gate provenance selection and deterministic image templates; exact canonical key; model patch paths cannot bypass image provenance. |
| `04f87c2` | Refuse generic image text and model bad-image predictions without structured repair evidence. |

Requires paired Ignis feature branch through `d7b0939`, based on unfinished #17 branch `2ffb319`.

## Repair policy

Automatic image replacement requires class bad_image_reference, cause not_found, verified Deployment ownership, regular container, exact workload/container/image fields and runtime evidence. Mock fixture evidence additionally requires sandbox_backend=mock retained from the sandbox creation response; incoming seed state is initialized without a trusted backend.

Existing healthy-baseline provenance checks remain mandatory: repository/service/environment, matching Deployment/container, same image repository, verified last-known-good trace and exact source SHA. The runtime template verifies the JSON-tuple signature key against those exact target fields. Unknown owners, unsupported init containers, non-not-found causes, legacy signatures without cause/source and missing provenance refuse repair.

Image incidents use the deterministic template only; BYOK patching and the local model patch selector cannot replace it. Diagnosis restrictions also cover issue hints and the final post-learning gate. Structural Secret-coverage blocking remains in place.

Live and dispatch reproduction record the controller-reported backend. Recorded responses lacking that field do not receive implicit mock permission. Legacy image fixtures require explicit refresh before the new positive controls can qualify.

## Checks actually executed

| Command | Actual result |
| --- | --- |
| python3 -m compileall -q agent/raphael_agent dispatch/raphael_dispatch | Passed after each implementation step through 04f87c2 |
| git diff --check | Passed |

These are Python syntax checks only, not dependency/import or behavioral checks. No tests were added/run; no provider, Supabase, registry, kind or hosted workflow proof was executed. No PR, push, merge or contract release.

## Pending cases

- Authentication/network/throttling/unknown with generic ImagePullBackOff text: blocked, zero image patches.
- BYOK/local-model/issue hints predicting bad-image against authoritative contrary evidence: remain blocked.
- Confirmed runtime absence with exact verified healthy baseline: one target-only deterministic image replacement.
- Missing/ambiguous/wrong repository, environment, Deployment, container or source provenance: zero patches.
- Direct provenance/template/model calls and replay: no bypass.
- Mock backend plus explicit fixture attributes: deterministic positive control; fixture attribute alone: refusal.
- Legacy signatures and unsupported init targets: explanatory refusal.
- Existing Secret, probe, mock/evaluation and provenance kind controls: rerun and record results.

All cases are planned, not executed. Do not call #11 complete until the paired runtime/consumer proofs pass and rollout is documented.


## Follow-up review fixes and CI qualification

- `0c99428`: verified structured image evidence selects the supported hypothesis even with no matching evidence text.
- `ed19ed7`: durable RunRecord now admits the controller-reported backend; schema/code escalation vocabularies include the four image-pull refusal reasons.
- `47bb7d7`: update positive provenance/template fixtures for verified runtime evidence; add six direct-gate regressions for non-absence causes, legacy signatures and mock backend impersonation.
- `6d5dfee`: this paired feature's three integration jobs use exact Ignis candidate `b71e781b7f93246f271bb15df8efa2c0fda8e662`; other runs retain the released runtime. Published Ignis contract snapshots/pins are unchanged.

Final local agent suite: **396 passed, 4 skipped**. Dispatch: **77 passed**. Rust candidate: **66 passed**. All suites used this feature's code; loopback fixtures required execution outside the restricted sandbox. An initial combined Python invocation had conflicting `tests.conftest` packages, so suites were run independently. Initial agent failures exposed the missing durable backend schema, refusal vocabulary and legacy image fixtures; these were fixed, then the complete agent suite passed. No failures were disabled.

These results do not establish live provider, registry, Supabase or kind behavior. Existing hosted mock/Secret-kind/image-provenance-kind jobs are the next proof. A registry-denial live control and production short-lease heartbeat controls are still pending. The Ignis candidate inherits incomplete #17; do not close #17 or claim that heartbeat coordination is implemented.

Merge-tree comparison against fetched Raphael main is conflict-free. The paired PR is for review only at this stage; no automatic merge, release or issue closure. The PR-scoped runtime override must be replaced with an authorized rollout/pin update before relying on post-merge runs, which otherwise retain the older release.
