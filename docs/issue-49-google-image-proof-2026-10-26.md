# Issue #49: Google workload image-pull proof

Status: implementation and local assertions pass; hosted Kubernetes results pending.

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
claimed. Hosted run links and inspected artifacts will be recorded after CI.
