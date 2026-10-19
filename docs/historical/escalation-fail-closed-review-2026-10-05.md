# Escalation validation: fail closed at transitions

Baseline: main `9e652d9`, PR #43. This change needs review; it is not merged.

## Previous behavior and proof limits

PR #43 changed eight files: the reason vocabulary, graph type annotation,
schema/source drift tests, two failure-characterization tests, and three docs.
It did **not** change the schema or production persistence enforcement, and
did **not** rerun the validating wrapper across seven evals on its final head.
Its post-merge [core](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37261846416)
and [E2E/kind](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37261846426)
runs passed; those runs alone do not establish the missing audit claim.

Before this change `durable_run_record()` validated escalation reports inside
both JSON/SQLite saves. Dispatch `_save()` did not catch ValidationError, and
`receive_result()`'s handler caught only protocol/orchestration/auth errors.
An invalid report could therefore cause HTTP 500 after an in-memory transition;
the old durable pending record stayed unchanged. There was no immediate recovery
guarantee: the periodic reaper only expires states still considered active,
so an already-terminal in-memory state would not be rescued by that loop.
The graph publication save instead swallowed all exceptions and could report
success without storing progress. #43 characterized both failure boundaries.

## Shared replacement policy

`escalation_failure_updates()` validates reports before another node, action,
or publication can use them. Graph node boundaries and dispatch `_run_node()`
use it; publication validates before calling publish; dispatch also checks
existing reports on result receipt, action issuance and terminal/persistence
transitions. Invalid reports return updates rather than raising:

- `failed_closed`, terminal reason `escalation_report_invalid`;
- minimal valid replacement, with no original summaries, hypothesis text,
  evidence IDs, attempt details, sandbox IDs or raw rejected values copied;
- one audit event and error log containing only the controlled schema path;
- no publish or executable patch survives the invalid-report transition.

Dispatch returns HTTP 200 with a normal `terminal` envelope, final status
`failed`, instructions `discard_local_copy`. No public connector schema changed.
JSON/SQLite persistence no longer enforces report validation. It still strips
raw connector patch bytes. Direct storage callers remain permissive, tested
explicitly with invalid reports. Filesystem/database failures remain separate:
dispatch can propagate them; the graph's best-effort storage now logs a safe
generic error rather than silently swallowing it. This is not an I/O recovery fix.

## Newly found shape defect

The full agent run exposed a real non-enum producer defect: patch-budget
escalation included `patch_id: null` although the schema permits a string only
when this optional field exists. Omit the optional field when no ID exists;
retain known IDs unchanged. The original budget test still asserts
`budget_exhausted` and now asserts no null patch ID. Eleven safety-test cases
used partial reports; they now use complete reports, retaining the original
refusal reason, unchanged diagnosis/input and no-model/no-patch assertions.
Neither change widens the schema.

## Test-only persistence audit

`tools/report_audit/` validates saved reports and normalized whole-run records,
recording schema paths/validators only. It is opt-in, diagnostic, and never
raises a validation error from storage. CI captures both full Python suites and
real dispatch subprocesses across the existing seven evals, and uploads the
audit with other artifacts. Save-revision counts include SQLite's JSON mirror,
not unique runs. Intentionally invalid direct-store tests remain visible.

Whole-run schemas still diverge from durable connector records: dispatch and
narrowed-location metadata; connector trigger/mode; evidence source/provenance
and missing timestamps; patch metadata whose executable content is intentionally
stripped. Partial unit fixtures also omit required fields. Do not restore raw
patch bytes or enforce the full-run schema at save time to conceal these gaps.
The previous audit additionally found report attempt status `completed`, which
PR #42 already added to the private schema.

Fresh seven-eval audit results must be reported from this PR's hosted run,
not borrowed from #43, PR #42, or the older local audit baseline.
