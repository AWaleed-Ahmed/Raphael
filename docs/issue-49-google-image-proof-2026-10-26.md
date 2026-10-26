# Issue #49: Google workload image-pull proof

Status: PASS — both Google kind cases and all seven PR checks passed on code head
`73c1fd1f57ac0f796108e49423b6134617e0bf97`. Evidence inspected after download.

## Scope

Reproduce an absent image tag on Google's public Online Boutique
`productcatalogservice`, pinned to upstream commit
`474d0f2eb73d97525234995a40d7781b7923a07d` (v0.10.4). This is an injected fault
on company-maintained sample software, not a claim about a Google outage.
The fixture source, copyright, license, adaptations and hashes are retained in
`e2e/fixtures/google-productcatalog/`.

## Acceptance and issue wording reconciliation

- Positive: independently Ready upstream baseline with resolved imageID; genuine
  ErrImagePull/ImagePullBackOff for an absent tag; real dispatch → connector →
  Ignis kubectl-controller; runtime `not_found`, verified regular container and
  exact Pod → ReplicaSet → Deployment identity; image-only patch back to the
  observed healthy release; validation clears the signature; `fix_finalized`;
  independently observed Ready Pod using the expected Google image.
- Missing approved replacement: runtime pull evidence is still verified, but
  without a trusted healthy baseline the result is
  `bad_image_reference / patch_value_unavailable`, without patch or publication.
- Unverified pull evidence: the existing production gate and
  `agent/tests/test_image_pull_gate.py` continue to require
  `image_pull_evidence_unverified`. Mock-only evidence is accepted only on the
  mock backend, per PR #50 / D-20261019-02, and never establishes a kind proof.

The original #49 no-provenance wording conflated the last two controls.
D-20261026-01 reconciles that wording without changing the production gate.
The workflow still requires the original probe, synthetic image, missing-baseline
and healthy-sentinel controls in addition to the Google cases.

Publication inside the repair harness remains dry-run. The scoped loopback REST
catalog holds an independently observed baseline; this does not qualify live
Supabase ingestion. Only owned namespaces and the disposable cluster are deleted.

## Validation

Local proof/workflow assertions: 38 passed. Image-pull gate and diagnosis
regressions: 18 passed. Local Docker is unavailable; no local kind success is
claimed.
[Cross-repository run 40306497161](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40306497161)
passed all four jobs, including both Google cases and the four original kind
controls. [Core run 40306497168](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40306497168)
passed Python, frontend and contract checks: agent **502 passed / 4 skipped**,
dispatch **88 passed**, workflow/evaluation/wire assertions **58 passed**.
The Google-specific and original kind assertions also passed in the hosted job.

[Inspected evidence and raw-file hashes](evidence/issue-49-google-image-proof-2026-10-26.json)
retain the exact signature, Kubernetes registry `not found` messages, verified
owner UIDs, image-only diff, validation result and healthy/repaired image IDs.
The initial independently Ready baseline and repaired Ready Pod both resolved to
`sha256:5604602ebb6f910c9e1bc906718d631e6415207f6da1e646a045eaebde86fad8`.
The real-kind backend used Kubernetes `v1.35.0` and Ignis `contracts-v1.4.2`.
GitHub tested the PR merge revision `15426c238f5d703076e3b792b3784a01e2e7de1f`;
the evidence distinguishes it from the branch head and upstream fixture commit.

The full [kind artifact](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40306497161/artifacts/12642298376)
is `kind-remediation-40306497161`, archive digest
`sha256:8b258ff2119d8f9af5b22288d993a9edb0949c9e2a6924e701df8367cceaa116`.
It contains the baseline, traces, initial Pod/events/ReplicaSet/Deployment,
verified identity, runner results, snapshots and successful proof summaries.
Namespace cleanup and cluster destruction passed. This commit adds the retained
evidence and final wording only; final-head checks are followed on
[PR #74](https://github.com/AWaleed-Ahmed/Raphael/pull/74).
