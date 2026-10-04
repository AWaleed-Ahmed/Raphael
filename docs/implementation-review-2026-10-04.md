# Implementation review notes: #33, #34, and #37

Branch: `docs/contributor-handoff`
Scope: observed signature identity (#33), replacement-image provenance (#34), and image-gap presentation (#37)

## Changes

### #33 — observed resource identity

The deterministic analyzers preserve the matching observed signature key for probe, image, and missing-ConfigMap diagnoses. When a probe signature is present, its normalized port attributes supply the hypothesis; unrelated manifest text cannot supply ports for that resource. Without an observed signature, manifest analysis can classify a mismatch but leaves the expected key unset.

Both direct-agent validation (including repeats) and dispatch validation use the pre-validation signature's normalized resource kind/name. Missing identity fails closed instead of checking an invented `payments-api` or `target` workload.

### #34 — replacement-image provenance

`fix_bad_image` no longer defaults to `hashicorp/http-echo:1.0`. Localization may approve a replacement only from a baseline that is verified healthy and marked last-known-good, scoped to the same repository, service, and environment, and tied to the same Deployment and container. The baseline must provide a container image reference from `runtime_identity.container_images`; its image repository must match the failing image repository. The recorded approval includes the healthy trace ID and source commit SHA.

If that evidence is absent or ambiguous, patch generation stops with `patch_value_unavailable`. This keeps the generated image change tied to the observed container and an auditable healthy release.

For automatic repair to work, healthy-trace rows need this shape in `runtime_identity`:

```json
{
  "resource_kind": "Deployment",
  "resource_name": "payments-api",
  "container_images": {
    "api": "ghcr.io/acme/payments-api@sha256:..."
  }
}
```

The test suite proves the resolver behavior against that row shape. Source commit provenance must be a full 40-character hexadecimal SHA; placeholders such as `unknown` are rejected. Malformed baseline metadata is ignored so later valid rows can still be considered. This checkout does not prove that live Supabase ingestion currently writes the per-container image map.

The committed bad-image evaluation has no trusted baseline. Its expected outcome is now `escalated / patch_value_unavailable`, with no patch, validation, or publication. The scorer and CRLF verifier enforce this refusal. Successful image replacement remains a controlled agent-test claim until a real verified baseline is supplied; no successful real-process or hosted image repair is claimed for this change.

## Test cases

| Case | Expected result | Result |
|---|---|---|
| Probe diagnosis has an observed resource name | Expected key uses that name and the observed ports | Passed |
| Probe diagnosis has no observed resource name | Expected key remains unset | Passed |
| An unrelated manifest resource has different probe ports | Hypothesis uses observed target ports, not unrelated ports | Passed |
| Image and ConfigMap signatures use class-specific key formats | Analyzer preserves the exact observed key | Passed |
| Direct-agent validation observes a different post-deploy signature, including three repeats | Every rollout still targets the original `worker-api` Deployment | Passed |
| Dispatch validation targets a renamed Deployment | Rollout uses `deployment/worker-api` | Passed |
| Dispatch validation has no observed identity | Validation plan refuses to invent a target | Passed |
| Matching verified, last-known-good baseline has the target container image | Resolver returns image and trace/commit provenance | Passed |
| Localization receives a matching last-known-good row | Run state records the approved image and source trace in localization results | Passed |
| Baseline is not verified healthy or not marked last-known-good | No image approved | Passed |
| Baseline repository, service, environment, Deployment, or container differs | No image approved | Passed |
| Replacement image comes from a different image repository | No image approved | Passed |
| Matching baselines disagree on replacement image | No image approved | Passed |
| Source commit is `unknown`, abbreviated, nonhexadecimal, null, or numeric | No image approved | Passed |
| Malformed rows precede a valid row | Invalid metadata is ignored; valid provenance is returned | Passed |
| Image patch has no approved baseline provenance | Refuses with `patch_value_unavailable` | Passed |
| Image patch targets an exact Deployment/container in a multi-resource manifest | Changes only the target image to the approved digest | Passed |
| Image patch target is missing, duplicated, or uses an aliased YAML node | Refuses instead of editing an ambiguous target | Passed |
| Bad-image evaluation has no approved baseline | Scorer accepts the explicit refusal and rejects an incorrect terminal reason | Passed |

## Test results

- Pytest was already available in the repository `.venv` (Python 3.12.3, pytest 9.1.1); no installation was needed.
- Initial focused diagnosis, image patch, provenance, and localization run: **47 passed**.
- Full agent suite after the earlier #33/#34 review fixes: **272 passed, 4 skipped**. After #37 and review corrections: **276 passed, 4 skipped**.
- Latest full dispatch suite: **74 passed**.
- Latest evaluator unit suite: **10 passed** (includes the changed refusal outcome and CRLF verifier checks).
- `py_compile` and `git diff --check`: passed.
- The first sandbox-only full-suite attempt stalled at the existing local HTTP endpoint test. Rerunning with localhost access completed successfully.

Warnings in the full run were existing deprecations from Starlette's test client and `jsonschema.RefResolver`.

Commands (run separately because agent/dispatch both use a `tests` package):

```bash
./.venv/bin/python -m pytest agent/tests -q
(cd dispatch && ../.venv/bin/python -m pytest tests -q)
./.venv/bin/python -m pytest evals/test_run_evals.py -q
git diff --check
```

## Limits for review

- No live Supabase or hosted end-to-end run was performed. The implementation fails closed until matching per-container image provenance is present in a healthy-trace row.
- #30 Secret coverage remains untouched because the handoff marks that workstream as claimed and calls for review of its report-schema prerequisite before implementation.

## #37 — readable image-gap presentation

The generated PR body now groups recognized `image digests not resolved; tags only:` messages under one prefix and lists each full image reference. The group is placed where the first image gap appeared, so unrelated gaps retain their relative order. Repeated references remain repeated, since this display transformation does not know whether they represent separate workload containers. The original fidelity list is not modified, and no validation or fidelity flags are changed.

| Case | Expected result | Result |
|---|---|---|
| One image gap containing a registry port, tag, and digest | Full reference appears under one image-gap prefix | Passed |
| Multiple image gaps mixed with a non-image gap | One prefix lists all references; non-image gap remains visible in order | Passed |
| Duplicate image references | Both occurrences remain visible | Passed |
| No material gaps | Existing frozen-record checklist fallback remains | Passed |
| Render image gaps | Source fidelity list remains unchanged | Passed |

- Focused command: `./.venv/bin/python -m pytest agent/tests/test_publish.py -q` — **12 passed, 1 skipped**.
- The skipped test is the optional live network publish test; the focused rendering tests are local unit tests.

## Follow-up implementation review — 2026-10-04

Reviewed and corrected the uncommitted changes on `docs/contributor-handoff` before pushing.

### Findings

1. **P1 — image provenance could come from a different target environment (fixed).** `node_localize` chooses `runtime_observation.environment` before `target_environment`. `fix_bad_image` then compares the approved source environment only with `localization_result.environment`. Before the fix, an in-process reproduction with `target_environment=staging`, observation/catalog `environment=production`, a matching verified last-known-good image row, and an exact Deployment/container signature emitted a staging patch from the production image. Localization now withholds image approval when an available target environment conflicts with the observed environment; the resolver also rejects an `unknown` repository, service, resource, container, image, or environment scope. Regression tests cover environment conflict and unknown scope.
2. **P2 — the #37 validation-flag assertion did not verify the stated requirement (fixed).** The original test only checked that the text `full_validation` was absent from the PR body. It now supplies `full_validation=False` and checks the validation record is unchanged after rendering.
3. **Documentation status mismatch (fixed).** The handoff now marks #37 implemented locally and lists Ignis #11/#13 as the next planned tasks.

The #37 material-gap display example changes from repeated prefixes:

```text
image digests not resolved; tags only: registry.example:5000/app:v1, image digests not resolved; tags only: busybox:1.37.0
```

to one prefix with both references:

```text
image digests not resolved; tags only: registry.example:5000/app:v1, busybox:1.37.0
```

### Rechecked evidence

| Check | Result | Scope |
|---|---|---|
| `./.venv/bin/python -m pytest agent/tests -q` | **276 passed, 4 skipped** | Full agent suite after review fixes, with localhost access |
| `../.venv/bin/python -m pytest tests -q` from `dispatch/` | **74 passed** | Full dispatch suite, with localhost access; no dispatch code changed during review fix |
| `./.venv/bin/python -m pytest evals/test_run_evals.py -q` | **10 passed** | Evaluator unit tests |
| `git diff --check` | Passed | Whitespace checks |
| Staging target with production observation/baseline; unknown provenance scope | **Regression asserts no image approval** | Fake catalog and resolver unit tests; no live services |

The sandboxed dispatch run was interrupted after stalling; its replacement run with localhost access passed. Live Supabase ingestion, a real Ignis process, and hosted proof remain unverified.

## Delivery review — 2026-10-04

The prior #33/#34/#37 code was reviewed together with #30 and passed the current full suites: **291 agent passed (4 existing skips), 75 dispatch passed, 10 evaluator unit tests passed**. Hosted [core CI 37217777993](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37217777993) and [cross-repo 37217777910](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37217777910) passed. The latter includes seven scored real-hook/mock scenarios and six narrow real-kind Secret controls. The bad-image scenario correctly refuses without verified provenance; a live image replacement is still not claimed. See [#30 delivery review](implementation-review-2026-10-04-issue-30.md) for fixes, release SHA and detailed controls. Live Supabase ingestion remains outstanding.
