# Escalation vocabulary and persistence review

Baseline: Raphael main `122d2d0`, including PR #42. This review does not
remove, enable, or otherwise change production persistence validation.

## What is enforced today

`store/patch_content.py:durable_run_record()` validates a non-null
`escalation_report` before preparing a durable record. Both JSON `RunStore`
and `SqliteRunStore` call this helper before writing. This is **report-only**
validation, not validation of the complete persisted run schema. Whole-run
metadata/content projection mismatches from the earlier audit remain a
separate contract-design question; raw patch bodies must not be restored to
make those schemas pass.

The report enum now accepts 18 reasons, including the four additions in
PR #42. The attempt-status enum also now accepts `completed`.

## Observed failure boundaries

| Path | Current behavior if a report fails validation | Risk |
|---|---|---|
| JSON/SQLite stores | Raise before writes; existing record remains intact | New progress is not durable. Existing tests cover both stores. |
| Dispatch `Orchestrator._save()` | Propagates `jsonschema.ValidationError` | HTTP handlers catch protocol/orchestration/auth errors, not this exception; an affected request can return a server error after in-memory transitions. No rollback is provided by `_save()`. |
| Graph publication node's best-effort save | Catches all exceptions and continues | A success response can accompany an unchanged prior durable record. The new controlled regression proves this discrepancy; it does not claim ordinary valid reports fail today. |

Schema-reference loading errors can also propagate from validation. The
code-level reason drift guard reduces one cause, but does not make all
report fields valid or decide the right production error policy.

The prior instruction was to keep production persistence permissive until
the wider audit was reviewed. PR #42 enabled report enforcement anyway.
Whether to retain that gate, remove it, or change failure handling needs an
explicit decision. This branch does **none** of those three.

## Changes in this review branch

- One `EscalationReason` literal vocabulary and derived immutable reason set.
  The graph's report constructor uses the type; no runtime guard was added.
- Schema enum equality check, including duplicate detection.
- A real `_escalation()` report validated for each of the 18 registered
  reasons, including legacy compatibility values not currently emitted.
- AST checks on agent source producers: report/blocked reason fields,
  budget descriptors, template refusals, and literal-valued variable flows.
  Deliberately new unknown reasons fail the guard. Free-form terminal errors,
  prose, and lookup keys are not treated as escalation enums.
- Controlled regressions proving the two failure boundaries above.

The source guard is not a general Python data-flow/type checker. Arbitrary
runtime-generated reason strings still need review and behavioral tests.
Dispatch lease/stage terminal reasons are not automatically escalation-report
reasons: those paths do not construct a report. No public contract changed.

## Follow-up requiring review

1. Decide the production report-enforcement policy and what should happen to
   in-memory state and the caller when persistence fails.
2. Separately define the full durable-run schema/projection. Do not weaken
   the raw patch-content boundary to resolve bookkeeping mismatches.
3. Review this test-only safety net before merge; hosted CI must pass on its
   exact head. Current main's older hosted proof is not this branch's proof.

## Local verification

Fresh full WSL runs: agent **318 passed, 4 existing skipped**; dispatch
**76 passed**. This adds 27 agent tests and one dispatch test to main's
291/75 baseline. The controlled graph risk test stubs publication: it proves
error handling, not a live GitHub publication or an ordinary valid-run failure.
Production store code and schemas are byte-for-byte unchanged on this branch.
