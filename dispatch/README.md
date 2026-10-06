# Dispatch operational notes

## Synthetic Secret fixture selection

Set `RAPHAEL_SECRET_FIXTURE_SET=payments-test` (or another Ignis-local fixture
name) explicitly to apply synthetic Secrets. Unset/empty means no fixture in
both connector-driven dispatch and direct `node_reproduce`. The latter no
longer silently hardcodes `payments-test`. Selection is trusted operator
configuration, not inferred from evidence or added to the public job envelope.
Dispatch snapshots the selection at intake, preserving it on replay/restart.
This deployment-level option is not per-tenant fixture authorization.

The separate `secret-fixture-kind` CI job checks the actual connector path
against disposable Kubernetes, with identical workload manifests for covered
and uncovered cases. It does not implement structural-secret diagnosis or
claim general real-backend validation. See `e2e/run_secret_fixture_kind.py`.

Diagnosis receives scoped, bounded, redacted manifest excerpts derived from
the ephemeral patch store, never its raw content. These safe excerpts are
persisted after initial deploy, before observation, so they survive restart.
The internal `intake(initial_evidence=...)` parameter accepts available evidence
from the same-process bridge without changing the public job envelope. It does
not collect missing evidence. Redaction precedes truncation and includes YAML
secret fields and structured observations; it is not a universal secret detector
or a policy for raw webhook and trace storage. See D-20260927-01.

The agent's connector-schema snapshot test reads Git blobs as well as files.
When running tests in WSL against a Windows-managed linked worktree, provide
Linux `GIT_DIR` and `GIT_WORK_TREE` paths for that worktree: its `.git` pointer
otherwise contains a Windows path Linux Git cannot resolve. Native checkouts
(including GitHub Actions) need no override.

Connector deployments use `RAPHAEL_DISPATCH_TOKENS`, a JSON object mapping each
Bearer token to `{ "tenant_id": "...", "role": "producer"|"connector" }`.
Producer tokens submit unchanged connector-v1 job envelopes to
`POST /v1/tenants/{tenant_id}/jobs`; connector tokens poll
`GET /v1/tenants/{tenant_id}/jobs/next`. The path tenant must match the token.
The legacy `POST /v1/jobs` endpoint remains for compatibility but is deprecated
for new producer integrations because it returns the first action directly.

The dispatch service reaps expired connector leases automatically every 10 seconds by default. Configure the cadence with `RAPHAEL_LEASE_REAP_INTERVAL_SECONDS`; `POST /v1/leases/reap` remains available as an explicit operations override.

Each state transition is persisted through the existing agent `RunStore`, including dispatch routing metadata and processed-action fingerprints. Raw manifests and executable patch bodies/diffs are excluded from connector-run records in both JSON and SQLite; live execution retains the original bytes in memory. Rejected proposals retain only metadata, stripped before append.

On startup, dispatch restores nonterminal jobs with a still-valid lease. A restart after initial deploy preserves the pending observation action unchanged, then issues a fresh unpatched `deploy_revision` on the same sandbox to reacquire `rendered_files` before patch generation. This refresh does not consume a patch attempt. Missing refreshed files escalate with `patch_input_unavailable` rather than generating a patch from empty input.

**Recovery limit:** once a generated patch's executable bytes have been omitted from persistence, startup (or producer retry against that persisted run) fails closed with `patch_context_lost_on_restart`. Dispatch never replays a stripped action or silently substitutes new bytes under an old action ID. This also applies to later validation/finalization stages that still need the in-memory patch. Persisted jobs whose lease already expired are failed closed with `job_lease_expired` first. This policy does not promise automatic connector cleanup delivery from a startup terminal; that remains governed by the existing terminal-delivery mechanism.
