# Phase 1 source preparation

This directory contains source identities and a proposed preregistered protocol for #78 checkpoints 1–4 / #66. It contains **no final accuracy score, trained model change, invented incident, or approved production dataset**. The initial twelve cases are regression/development sources. Human reviews and a statistically adequate independent final set remain required.

See the [execution report](../../../docs/model-readiness-phase-1.md), [Phase 1 plan](../../../docs/plans/issue-78/phase-1-data-and-acceptance.md), and [source manifest](source-manifest.json). `protocol.json` freezes the proposed quality/resource gates before new scoring; its owner approval is explicitly pending.

## Exact files and oracle separation

`source-manifest.schema.json` rejects malformed metadata. Every source file has an original URL, byte count, SHA-256, role and cache-relative path. Original ZIP members additionally record compressed byte ranges, archive size and CRC32. An archive-member hash is not a hash of the complete remote ZIP.

Roles are enforced: `input` alone enters prepared predictor bundles; `oracle` (answers, fixed sources/diffs), `environment` and raw snapshots stay outside. Only the recorded GitHub report-body and OpenRCA instruction projections are allowed; titles/comments/scoring answers are not automatically injected as class labels. A separate human answer-leakage review is still required because original reports and buggy repositories can themselves contain hints.

## Acquire and verify originals

Run from the repository root in its qualified Python environment:

```bash
python agent/scripts/fetch_readiness_evidence.py --cache-root /tmp/raphael-readiness-cache
python agent/scripts/prepare_model_readiness.py \
  --cache-root /tmp/raphael-readiness-cache \
  --training-root /path/to/original/raphael/data \
  --output /tmp/raphael-readiness-preparation
```

The original trace members total several GiB uncompressed. Downloads are explicit, stream-verified, limited to locked public HTTPS sources/ranges and never executed by the fetcher. Existing cache bytes must match; changed upstream issues or archive bytes refuse rather than silently updating the dataset. Keep raw data local/restricted pending terms/redaction review. No raw issue bodies, large telemetry, or third-party source archives are redistributed in this Git change. Immutable source-archive URLs, fixed metadata hashes, and the approved retained snapshot are necessary for reproduction; mutable issue snapshots may become unavailable for exact re-fetch.

The training-root argument identifies the original local corpus. No training files are copied into this branch, and no estimator is loaded to audit it. The shipped index is audited separately using its verified public source list, not the retired unowned training index. Exact identifier absence does not prove semantic or generation independence.

Without private/local data, this command still validates the public metadata and prepares jobs:

```bash
python agent/scripts/prepare_model_readiness.py --output /tmp/readiness-metadata-only
```

It reports raw-data/training checks as unverified and retains blockers. CI uses this offline form and uploads preparation evidence; green CI does not mean Phase 1 is fully accepted.

```bash
python agent/scripts/prepare_model_readiness.py \
  --output /tmp/readiness-check --require-final-ready
```

This must currently exit **2** because the final freeze is not approved. Malformed or mismatched evidence exits **1**. An ordinary preparation snapshot exits **0** with explicit blockers, zero executed predictions, and `prepared_not_executed` jobs. Detailed final class/history/healthy-exposure labels are deliberately not yet frozen; the tool fails closed for those gates rather than inventing counts.

## Reproduction and reviews

The only small upstream snapshots committed for automated integrity tests are three original BugsInPy test-command files in `agent/tests/fixtures/readiness_commands/`. Their hashes match the original metadata references. Mock HTTP/compression and altered metadata appear only in adversarial/tool unit controls; they are not positive model or historical incident proofs.

Use the [review worksheet](../../../docs/evidence/issue-78/phase-1/label-review.csv) for two independent human reviews. Future label changes require a new reviewed source/protocol snapshot; do not tune on the locked final answers. Current proposed retention, pilot access, evaluation thresholds, and unresolved approvals are documented in the five plans.
