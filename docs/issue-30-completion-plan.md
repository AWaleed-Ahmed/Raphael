# Issue #30 completion plan

Date: 2026-10-20. Raphael base f056557; Ignis base bc42504.

The original structural coverage gate is merged. Finish the remaining safety and qualification work described in the handoff without inferring production-only credentials from a Secret reference or reading production Secret values.

1. Integrate the existing Ignis #20 changes with current runtime deadlines/leases. Unsupported/malformed reference forms remain unknown; report positively missing required dependencies accurately; recognize explicitly labelled bundled synthetic fixtures using names/keys only. Preserve selected fixture inventory across redeploys without treating previously bundled fixtures as a new name collision. Verify parser, service, redeploy, persistence and sentinel cases.
2. Preserve schema-validated, bounded Secret-reference metadata through Raphael evidence redaction and persistence. Keep arbitrary sensitive fields redacted. Report specific uncovered references in escalation checks; retain textual-block precedence and zero diagnosis/patch model calls on structural refusal. Verify direct/dispatch parity, JSON/SQLite restart and malformed/incomplete compatibility.
3. Add undecorated missing/covered mock evaluations and covered-plus-probe real-kind remediation to the existing harness. Run regressions and inspect artifacts. Record exact source identities, outcomes and raw-channel limits in the implementation review. Keep the existing released pin until the updated Ignis runtime is reviewed/released; no merge/tag or issue closure is implied by this plan.

The approved raw-channel exceptions remain deploy rendered_files, full manifest artifacts and controller rendered_yaml. The no-values guarantee applies outside those named channels; credentials are not needed for tests. Linux/kind proof does not qualify native Windows or production deployments.
