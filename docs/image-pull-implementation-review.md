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

