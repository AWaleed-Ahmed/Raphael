# Pilot milestone runbook

Updated 2026-10-20. Gates replace the expired five-day schedule. Start with the
[canonical installation](pilot-install.md), [permission matrix](permission-matrix.md)
and [acceptance checklist](pilot-acceptance.md). No partner timeline is committed.

## Gate 1 — Access and selected pilot cut

Record the authorized staging repository, immutable revision, webhook ownership,
permission profile, sandbox context and optional provider/catalog choices. Obtain
webhook HMAC and any backend credentials through the partner's secrets manager.
Review customer App/PAT permissions; do not assume App auth or event intake is
missing merely because customer provisioning has not been qualified.

Exit: partner approves read-only production evidence access, sandbox isolation,
retention and no Secret payload reads. No infrastructure is provisioned by this runbook.

## Gate 2 — Install and local proof

Follow the canonical guide's exact pair and explicit environment profile. Confirm
combined core plus embedded connector health/auth, durable stores and dry-run
recorded smoke. Compare results with [local preflight](pilot-local-preflight.md).
A local `go=True` checks configuration only.

Exit: installed revisions and executed commands are recorded; blocked steps name
the missing prerequisite. Keep all publication, comments, labels and Checks off.

## Gate 3 — Optional integration qualification

Only enable the integrations chosen and authorized in Gate 1:

- Signed GitHub traffic: configure `/v1/webhooks/github`, HMAC and event subscriptions;
  record delivery IDs and confirm deduplication. GitHub commands/comments/Checks
  can mutate GitHub even when patch publication is dry-run; review permissions first.
- Supabase: use an approved disposable test project, migrations and backend keys.
  From the Raphael root with the venv active and environment explicitly loaded:

```bash
export RAPHAEL_CLIENT_ID="fake-telemetry-client"
export RAPHAEL_FAKE_RUN_ID="fake-telemetry-run-001"
python agent/scripts/test_supabase_telemetry.py
```

This writes persistent fake rows. Check company/client/project/repository/run
scope and plan approved cleanup. The generic trace smoke does not qualify the
image baseline pipeline; qualify ingestion, provenance, wrong-scope rejection
and repair/refusal separately before claiming live catalog acceptance.

- BYOK: provider adapter presence is not live qualification. Obtain explicit call
  budget approval and pin the model; preserve schema/policy checks and failure controls.
- Kubernetes: qualify only an owned sandbox context and selected workload; existing
  Linux kind proof is not certification of the partner's infrastructure.

Exit: each selected integration has actual evidence or is explicitly excluded
from the pilot cut. Do not silently enable unqualified localization or learning.

## Gate 4 — At least five real dry-run failures

Keep `RAPHAEL_PARTNER_MODE=dry_run`, `RAPHAEL_PUBLISH_MODE=dry_run` and an empty
live allowlist. Record ≥5 real eligible failures: delivery ID, run ID, repository,
SHA, class, bounded evidence, candidate patch, sandbox/cleanup results, terminal
reason, reviewer judgment and false positives. An escalation is labelled as such.

Manual feedback example (replace the quoted example IDs with actual IDs):

```bash
python -m raphael_agent.scripts.record_feedback \
  --outcome rejected \
  --run-id "example-run-id" \
  --result-id "example-result-id" \
  --notes "false positive: probe flapping"
```

This writes local feedback; it is not a model-training or improvement proof.
The HTTP alternative is `POST /v1/feedback`; webhook feedback uses authorized
`pull_request` events. Review metrics with:

```bash
python -m raphael_agent.scripts.metrics
python -m raphael_agent.scripts.pilot_go_nogo
```

Exit: partner reviews all runs and false positives; unmet PRD benchmark/accuracy/
timing targets remain visible rather than inferred from fixture counts.

## Gate 5 — Separate approval for live drafts

Only after explicit partner/security approval, change the operator-owned service
profile to partner `allowlist`, publish `live`, one proven failure class and scoped
GitHub write credentials. Reload/restart the services that read those settings.
An environment command in another terminal does not reconfigure a running server.
Run go/no-go, verify draft-only behavior and retain human merge control. Empty
allowlist, missing credentials, auto-merge or unreviewed model use is a no-go.
Advisory Checks must never become required merge checks.

Exit: accepted/rejected/merged outcomes recorded, owned resources cleaned up and
remaining acceptance gaps assigned. Use the canonical shutdown procedure; keep
recovery journals until owned work and cleanup are confirmed terminal.
