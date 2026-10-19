# CI repair verification — 2026-10-19

## Failures confirmed

| Run | Code / event | Actual failure |
| --- | --- | --- |
| [core-ci39159064461](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39159064461) | Raphael PR #50, e180964 | Canonical drift check detected changed connector OpenAPI and two new lease schemas against contracts-v1.3.0 |
| [E2E39159346175](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39159346175) | Current main903370a, Ignis repository dispatch | Only mock eval bad_image_reference failed: new labelled mock evidence produced supported bad-image diagnosis followed by patch_value_unavailable; manifest still expected legacy unknown/image_pull_evidence_unverified |
| Older recurring schedules | Historical Raphael5a1771e | Superseded legacy expectations, already corrected on current main; [current scheduled39226819536](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39226819536) passed against the older release |

Current merged Ignis main is f1f3b2c858c6ce246308eae395e280856459d9a5
(PR #21). Its [CI39159339643](https://github.com/AWaleed-Ahmed/Ignis/actions/runs/39159339643)
passed. No current Ignis workflow failure was found in the audited recent runs.
The code/contracts/fixtures match the previously tested recovery877af6b tree.

## Repairs and safety boundaries

1. New annotated contracts-v1.4.0 targets exactly the reviewed merged Ignis
   commit above. The user explicitly approved tag publication. No existing tag
   moves. Canonical sync/check remains enabled; snapshot also gains the missing
   optional deploy_timeout_seconds field from upstream.
2. One resolve-ignis job selects root CONTRACTS_VERSION or the same explicit
   immutable override for all three jobs, including Secret-kind. Only contract
   tags/full40-character SHAs are accepted; mutable/short/injected references
   fail. Obsolete candidate-branch overrides are removed.
3. The bad-image mock eval now asserts mock_fixture/not_found on backendmock,
   then the exact missing-healthy-baseline refusal. It retains no candidate patch,
   no publication and no validation. Wrong source/cause/backend or malformed
   attributes fail. The production gate is unchanged; legacy/unverified signatures
   and mock evidence on real backends remain agent regression cases. This does
   not qualify a registry lookup or a positive real-kind image repair.
4. The real-kind negative control had the same legacy refusal expectation.
   It now requires non-mock backend, runtime source and the shared verified
   ownership/absence predicate, then the exact missing-healthy-baseline refusal
   and absence of an approved replacement/patch/publication/validation. Three
   new assertions reject mock source/backend, wrong owner/cause and wrong
   reason/approved-image combinations. The positive case remains manual-only.
5. Core CI now runs the workflow/ref/eval/wire/kind assertion modules. The hosted
   wire harness exercises TTL30s and diagnosis35s, including whole-process restart.

## Local expected/actual evidence

| Case | Expected | Actual |
| --- | --- | --- |
| Ref resolution | Committed contract default or validated full-SHA/tag override; all three jobs consume one output | 7 new workflow/ref assertions pass |
| Existing safety/eval assertions | No weakened refusal, patch, publication, backend or cleanup expectations | 41 combined assertions pass |
| Bad-image former hosted evidence | Exact new mock/baseline semantics explain the earlier red result | All scorer assertions pass, original runner exit0 preserved |
| Schema synchronization | Exact tagged upstream snapshot, complete tree comparison | Canonical sync and Check pass against the published GitHub v1.4.0 tag; staged checks also passed |
| Agent regressions | Preserve production gates | 441 passed / 4 skipped |
| Dispatch regressions | Preserve state/lease/replay behavior | 88 passed |
| Actionlint | Valid workflow syntax, contexts, expressions and needs | Pass; shellcheck disabled/unavailable |
| Wire / production hooks / seven evals | Current pair succeeds with strict expected refusals | All3 wire scenarios, production-hook smoke and all7 strict evals pass |

Initial failures are retained as diagnostic evidence: workflow assertions first
failed before adding the shared resolver/core step/short-lease inputs. The new
source/backend eval assertion failed before the scorer checked those fields.
One combined assertion run lacked loopback permission; its HTTP fixture failed
with PermissionError and all38 passed at that stage (41 after the kind-control additions) with the required permission. A manual
re-score initially omitted runner_exit_code from the separate runner artifact;
using the original eval-results exit0 makes all assertions pass without changing
runtime evidence. Official PowerShell hashes were UTF-16; after decoding correctly,
SHA256 validation passed. One wire invocation found the previous /tmp binary gone;
the rebuilt persistent Ignis binary is used for the final local pair.

Diagnostic logs are local under /tmp/ci-repair-*.log. No raw credentials or wire
bodies are committed. Portable PowerShell7.6.7/actionlint1.7.12 were downloaded
from their official repositories and SHA256 checked. Python3.12.3, Git2.43.0,
Rust/Cargo1.97.1, Linux. Staged tag checks use an explicitly scoped process-local
Git URL rewrite to the owned Ignis clone; they are not claimed as GitHub checks.

## Standards

Independent read-only focused review: zero actionable findings. Release approval,
canonical sync and D-20261019-02 preserve the repository standards.

## Spec

Independent read-only focused review: zero actionable findings. Shared runtime
selection, contract parity and strict mock refusal address the confirmed failures.

The first current-head core run [39271237220](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39271237220)
passed both contracts and Python at00183be. The related real-kind control was
then strengthened before accepting full hosted qualification; final-head runs
are tracked in the PR description.

## Public tag and hosted results

The approved annotated tag is published: object
c8fdbfda8883c3e7e422c5a3b8c2b0446f5a1f96, peeled commit
f1f3b2c858c6ce246308eae395e280856459d9a5. Canonical sync and Check ran against
GitHub with no URL override and passed. Public contract parity is restored.

Current-head hosted results and immutable run links are recorded in
[PR #50](https://github.com/AWaleed-Ahmed/Raphael/pull/50)'s description/checks
when verification completes. A separate manual run exercises the existing CRLF
flag against the same release; no pending positive image case is silently enabled.

PR #50 remains draft and unmerged. A repair on the PR cannot retroactively change
a historical run's conclusion or update main's workflow/code before the user
merges. No historical run is deleted or hidden. #11 positive image repair,
remaining authenticated/system-attribute/native-Windows qualification and the
separate Secret-safety follow-up retain their own acceptance conditions.
