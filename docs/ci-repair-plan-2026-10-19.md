# CI repair plan — 2026-10-19

Scope: Raphael PR #50, its current main, and paired Ignis main. Keep the current
review branches; no main merge or contract-check bypass.

1. Verify failures against exact runs. PR core-ci39159064461 fails contract drift;
   current-main repository_dispatch39159346175 fails only bad_image_reference.
   Older repeated schedule failures used5a1771e and are superseded by current-main
   green scheduled39226819536; do not alter tests to erase historical failures.
2. Pin contracts/runtime to reviewed merged Ignisf1f3b2c858c6ce246308eae395e280856459d9a5
   using new annotated contracts-v1.4.0. Prepare changes and qualification first;
   publishing the new tag needs the release approval required by REL-06 in the
   shared checklist. Existing tags must not move. Sync with the canonical script.
3. Resolve one Ignis reference for all three cross-repository jobs. Defaults read
   CONTRACTS_VERSION; manual/repository-dispatch overrides are shared consistently.
   Remove obsolete candidate branch special cases. Validate immutable input forms.
4. Migrate the mock bad-image eval to the new explicitly labelled mock evidence:
   diagnosis recognizes the mock absence but refuses patch_value_unavailable
   without a verified scoped healthy baseline. Preserve no patch/no publication,
   unverified-evidence refusals, real-backend rejection of mock evidence and the
   pending real-kind positive proof. Assert source/cause/backend on the eval wire.
5. Add workflow/ref/eval regression assertions and run them in core CI. Exercise
   the implemented TTL30/diagnosis35 wire control automatically. Verify local
   suites, real-hook/evals and canonical contract sync, then push PR #50 and inspect
   all current-head hosted jobs/artifacts. Record failures and corrected reruns.

Success: current-head contracts/core/E2E jobs pass against the same reviewed
implementation, and prior failures are explained without weakening release,
provenance, ownership, redaction or publication gates.

## Execution checkpoint

The user approved publishing the prepared new contract tag. Ref/eval fixes and
regressions are committed in small steps; exact outcomes, initial failures and
hosted/current-main limits are recorded in
[the verification record](ci-repair-review-2026-10-19.md).
