# Raphael issue closure reconciliation — 2026-10-20

Status: issues #30, #33, #34 and #37 closed as completed on 2026-10-20,
following verification of their original acceptance criteria. Issue #49 remains open
while its original negative-control wording is reconciled with the later
recorded mock policy. This does not authorize implementation or alter that policy.

## GitHub closure record

The four issues were closed as `completed` on 2026-10-20. Each closure
includes the existing shipped-code evidence and scope limits.

| Issue | Closure comment |
| --- | --- |
| [#30](https://github.com/AWaleed-Ahmed/Raphael/issues/30) | [Evidence and scope](https://github.com/AWaleed-Ahmed/Raphael/issues/30#issuecomment-6283278893) |
| [#33](https://github.com/AWaleed-Ahmed/Raphael/issues/33) | [Evidence and scope](https://github.com/AWaleed-Ahmed/Raphael/issues/33#issuecomment-6283279596) |
| [#34](https://github.com/AWaleed-Ahmed/Raphael/issues/34) | [Evidence and scope](https://github.com/AWaleed-Ahmed/Raphael/issues/34#issuecomment-6283280241) |
| [#37](https://github.com/AWaleed-Ahmed/Raphael/issues/37) | [Evidence and scope](https://github.com/AWaleed-Ahmed/Raphael/issues/37#issuecomment-6283280854) |

[#49](https://github.com/AWaleed-Ahmed/Raphael/issues/49) was verified open
after the four closures; no comment, body or state change was made to it.

## Verified baseline

- Raphael default branch: `main` at `0dc46c47b976a42dd958ad4d8e56dcfaf8b154ab`.
- Delivered consumer: `08accd56189171fcc779a858ba7e6f7558924b89` from PR #56;
  the subsequent main changes in PR #57 are documentation only.
- Ignis release: annotated `contracts-v1.4.2`, resolving to
  `2bfcc644f278da3e16845d6e4408ee9b6048922d` from Ignis PR #20.
- All 29 vendored `contracts/sandbox` Git blobs match that release exactly.
- [Current-main core CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39366474221)
  and [paired integration CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39366474138)
  passed at `0dc46c4`. Paired proof files, runner results, Kubernetes observations,
  workload identity and catalog requests were downloaded and inspected.
- Existing offline tests against an isolated snapshot of this exact main:
  71 agent regressions passed, one optional live-publication test deselected;
  two dispatch validation-target regressions passed, 22 unrelated tests deselected.
  These are focused results, not a new full-suite execution.

The dirty local checkout and its draft model/BYOK changes were excluded from
shipped-code conclusions. Historical implementation reviews remain historical
records; this reconciliation supersedes their pending-status statements for the
four scoped issues below.

## Closure decisions

| Issue | Delivered acceptance and evidence | Disposition |
| --- | --- | --- |
| [#30 structural Secret dependencies](https://github.com/AWaleed-Ahmed/Raphael/issues/30) | Initial coverage in Raphael #42 / Ignis #18; follow-up safety corrections in Raphael #55 and Ignis #20; runtime delivery in #56. Current-main mock controls prove missing-required refusal without patch/publication and covered probe-only repair. Six kind Secret controls plus covered-Secret probe repair verify actual Kubernetes behavior. Metadata persistence, textual precedence, unknown/incomplete coverage and zero model calls on structural refusal have tracked regressions. | Close as completed within the approved structural-coverage scope. |
| [#33 observed signature identity](https://github.com/AWaleed-Ahmed/Raphael/issues/33) | #42 preserves observed probe/image/ConfigMap keys. Direct repeated rollout validation and dispatch validation use observed resource identity; missing identity refuses. Renamed-resource, conflicting-manifest and repeat-validation regressions pass on current main. | Close as completed. |
| [#34 replacement-image provenance](https://github.com/AWaleed-Ahmed/Raphael/issues/34) | #42 removes the generic automatic image replacement. Approval requires a verified, scoped last-known-good baseline with trace and full commit identity; absent, malformed, mismatched or conflicting provenance refuses. Current-main kind proof verifies a target-only image repair using an independently Ready baseline and refusal without a baseline. | Close the original provenance-policy issue. Live Supabase baseline ingestion remains a separate unqualified milestone. |
| [#37 image-gap presentation](https://github.com/AWaleed-Ahmed/Raphael/issues/37) | #42 groups recognized image-gap prefixes while preserving full references, unrelated gaps, original material_gaps and validation flags. Single/multiple/mixed-gap and duplicate-reference rendering regressions pass on current main. | Close as completed; no live publication is required to prove rendering. |
| [#49 genuine kind image repair proof](https://github.com/AWaleed-Ahmed/Raphael/issues/49) | The positive proof now passes on the released pair: genuine ErrImagePull, not_found/runtime/verified-owner evidence, exact image-only repair, fix_finalized and independently Ready post-fix Pod. #51 restored required automatic execution. However, #50 and D-20261019-02 changed the structured mock and missing-baseline refusal expectations after the original issue text was written. | Keep open for explicit acceptance-wording reconciliation. No runtime gate weakening is needed. |

## Scope and limitations

### Secret coverage (#30)

[PR #55](https://github.com/AWaleed-Ahmed/Raphael/pull/55),
[Ignis #20](https://github.com/AWaleed-Ahmed/Ignis/pull/20), and
[consumer #56](https://github.com/AWaleed-Ahmed/Raphael/pull/56) address the
[gaps documented after #42](https://github.com/AWaleed-Ahmed/Raphael/pull/42#issuecomment-5992136207).
A Secret reference alone does not establish a production-only credential
requirement. Unsupported, incomplete or malformed coverage remains unknown.

The approved raw-channel exceptions remain deploy `rendered_files`, full
rendered-manifest artifacts and controller `rendered_yaml`, as recorded in
D-20261014-01. Value-absence claims apply outside those channels; neither this
closure nor synthetic sentinels establish universal credential detection.

### Image provenance (#34)

The current kind proof uses fixture commit
`bce03d155a80b13d40bcd82d892bc3c5594ca018` for the genuine absent image and a
baseline independently observed Ready. The production REST catalog adapter
queries a loopback fixture scoped to company, client, service and environment.
The fixture is not a live Supabase service.

No issue-history agreement was found making live Supabase ingestion a condition
of the original #34 provenance-policy acceptance. The broader release milestone
still requires authorized baseline write/read, valid per-container image and full
commit identity, wrong-scope refusal and repair qualification before live
ingestion is advertised. The existing healthy-trace smoke alone is insufficient:
its sample lacks the required per-container image map and uses an abbreviated
commit. No live Supabase requests were made for this reconciliation.

### Remaining #49 decision

[AmazingDude's October comments](https://github.com/AWaleed-Ahmed/Raphael/issues/49#issuecomment-6238836855)
kept positive proof pending the reviewed Ignis runtime release and pin. That
historical dependency is now satisfied. The current positive case is required
on every cross-repository workflow event.

The original issue expects `unknown / image_pull_evidence_unverified` for its
unverified mock control. [PR #50](https://github.com/AWaleed-Ahmed/Raphael/pull/50)
and D-20261019-02 deliberately introduce `mock_fixture` evidence usable only on
the mock backend; without an approved replacement, the control now returns
`bad_image_reference / patch_value_unavailable` with no patch or publication.
The current kind negative control also has verified runtime pull evidence but
no trusted replacement baseline. These cases must be distinguished from missing
or unverified pull evidence, which the production gate continues to reject.

The smallest remaining action is to reconcile the issue's acceptance text with
that recorded policy, retaining explicit unverified-source regression coverage.
If the recorded policy is accepted, no implementation or infrastructure change
is required for closure. This document leaves #49 open and does not silently
change its acceptance criteria.

## Evidence classification and reproduction

- Unit/graph tests exercise production analyzers, resolvers, rendering and
  validation-target derivation with explicit fixtures/stubs where appropriate.
- Mock integration uses actual Raphael/dispatch and Rust connector/controller
  processes against mock Kubernetes. It does not establish real Kubernetes.
- Kind controls use owned disposable Kubernetes clusters and the actual
  dispatch → connector → kubectl-controller chain. Image baseline catalog
  responses remain a labelled loopback fixture.
- Publishing is dry-run; kind remediation explicitly disables local inference,
  external diagnosis/patch models and learning. No trained inference, paid
  provider behavior, live publication or production acceptance is claimed.

From the verified revision, using a Python environment with existing test dependencies:

```bash
(cd agent && PYTHONPATH=../dispatch python -m pytest -q tests/test_diagnosis.py tests/test_image_provenance.py tests/test_image_pull_gate.py tests/test_secret_coverage_boundary.py tests/test_graph_localization.py tests/test_graph_phase2.py tests/test_publish.py -k 'not optional_live_network_publish')
(cd dispatch && PYTHONPATH=../agent python -m pytest -q tests/test_orchestrator.py -k 'validation_plan_targets_observed_resource or validation_plan_refuses_missing_resource_identity')
gh run download 39366474138 --repo AWaleed-Ahmed/Raphael --dir /tmp/raphael-acceptance-evidence
```

The existing hosted proofs were inspected; no new cluster was provisioned and no
workflow was dispatched during this reconciliation.
