# Supabase migration validation — 2026-10-20

## Result

**PASS: 31/31 live database checks.** The user authorized migration and temporary
public-repository fixture testing on Raphael, followed by cleanup.
Target: `mqcdjdzvgsgaqkrpmtpb.supabase.co`, PostgreSQL 17, Linux x86_64,
Supabase CLI 2.121.0. Local base `f66a514d92115417a41fdbd1637ed01a9470a0ba`,
branch `fix/byok-live-qualification`, with uncommitted qualification changes.
Unrelated work was preserved. No Git commit, push or PR was made.

This proves database upgrade/constraint behavior. Automatic healthy ingestion,
HTTP JWT authentication, real-incident localization benefit and Ignis sandbox
repair remain deferred. No database reset or existing-row deletion occurred.

## Migration outcome

| Version | Action / check |
|---|---|
| 20260815000000 | Already applied; catalog schema, indexes, FKs, trigger checked |
| 20260816000000 | Already applied; effective API/backend privileges checked |
| 20260816000001 | Already applied; nullable revisions/version/defaults checked |
| 20260816000002 | Already applied; unknown source-revision default checked |
| 20260819000000 | Applied; compatible pre-existing telemetry table retained |
| 20261020000000 | Applied; sibling clients and paired company/client RLS |
| 20261020000001 | Added/applied; remove unintended API-role privileges |

Telemetry existed without its migration-history entry. Its columns/constraints
matched; IF NOT EXISTS preserved it. No history repair was needed. All seven
versions now match remotely; final dry run shows no pending migrations.
The first four were not replayed. Fresh-database replay of all seven: NOT RUN.

Preflight demonstrated anon/authenticated TRUNCATE privileges and unwanted
REFERENCES/TRIGGER grants on application tables. RLS does not protect TRUNCATE.
The new migration revokes PUBLIC/anon/authenticated table privileges and restores
authenticated SELECT on the two RLS-protected catalog tables. Backend catalog
CRUD and telemetry INSERT/SELECT remain unchanged. Tests inspect destructive
privileges without executing TRUNCATE.

## Fixture provenance

Actual public source: [Flask 3.1.2 /hello route](https://github.com/pallets/flask/blob/2c1b30d0503cfb064f1cb252e6614a06915a362a/examples/tutorial/flaskr/__init__.py#L29).
Repository `pallets/flask`; commit `2c1b30d0503cfb064f1cb252e6614a06915a362a`;
file `examples/tutorial/flaskr/__init__.py`, symbol `hello`, line 29, `GET /hello`.
Downloaded file SHA256:
`ecfe54451a0cb1cfb8aac26d0f65bdfc4b1fc5ccd7148f4ad38829a8ba26f03a`.

Tenant IDs, spans, telemetry outcomes and health assertions are synthetic.
No third-party customer/user records were imported. The schema requires
verified_healthy=true; metadata labels this fixture
`public_source_fixture_not_observed_health`. It does not prove an observed
healthy deployment, real trace, image provenance or repair.

## Execution and coverage

1. Inspected schema/history/counts/grants and recorded full ordered row hashes,
   without exposing existing row contents or credentials.
2. Rehearsed three pending migrations plus fixtures in one rollback transaction.
   Initial fixture incorrectly attempted telemetry UPDATE and was refused.
   Corrected it to INSERT, preserving backend privilege limits. Final rehearsal
   passed 31 checks and rolled back both schema and fixture changes.
3. Reviewed final dry run and applied with `supabase db push --yes`.
4. Ran the SQL regression file against the committed schema: **31 passed**.
5. Verified identical before/after hashes/counts, migration history, and final
   dry run. `git diff --check` passed.

Coverage: three-table RLS, client PK, both cascading ownership FKs, API privilege
limits, six indexes, A1/A2 siblings and B1 in another company, catalog/telemetry
writes, idempotent upsert, normalized defaults, timestamp trigger, duplicate
client refusal, wrong-company FKs, verified/source-line/event-type constraints,
conflicting LKG refusal, per-client reads, missing/mismatched/user_metadata claims,
unauthorized reads/writes, and exact deletion with both cascades.

RLS uses actual PostgreSQL authenticated/anon roles with transaction-local
request.jwt.claims: **LIVE database policy tests; SIMULATED issuer claims**.
Real user JWT issuance/signatures/PostgREST authentication: NOT RUN. No Auth hooks,
users, credentials or auth settings changed. No LLM, registry, sandbox or GitHub
publication calls occurred. SQL has 15-second statement and 3-second lock limits.

## Cleanup and reproduction

Every fixture uses transaction-local UUIDs. Exact-owned deletion/cascades are
tested, then ROLLBACK removes all inserts/helpers; exceptions abort the same
transaction. Final fixture run: `7c574e2a-0753-4e58-8419-52516511830f`.

| Table | Before | After | Full row hashes match |
|---|---:|---:|---|
| raphael_clients | 2 | 2 | PASS |
| raphael_healthy_traces | 1 | 1 | PASS |
| raphael_telemetry_events | 1 | 1 | PASS |

**Zero fixture rows remain; existing rows are unchanged.** No persistent test
users/functions/resources were created. Nine SQL-query CLI invocations covered
preflight/rehearsals/verification; internal HTTP request counts are unknown.

Evidence directory: `docs/evidence/supabase-localization-2026-10-20/`.
Files: controls-before.json, database-before.json, migration-rehearsal.json,
migrations-applied.json, database-fixture-validation.json, database-after.json,
cleanup-verification.json, migrations-after.json, migrations-final-dry-run.json,
migration-fixture-provenance.json (includes source/SQL/migration hashes).

```bash
supabase migration list --linked
supabase db push --dry-run
# Review target/pending files before an owner-authorized apply:
supabase db push
supabase db query --linked --file supabase/tests/catalog_migrations.sql
supabase db push --dry-run
```

The SQL test needs administrative SET ROLE permission and retains no fixtures.
Keep authentication in the local CLI store. API keys alone do not establish SQL
role-switching privileges.

## PR integration snapshot

The delivery branch `fix/supabase-localization-qualification` is isolated from
main `52e53055eb0867ed17ea7187fa3651d5d7cbd47a`. It preserves the merged BYOK,
local-inference deferral, pilot documentation and branding changes. The original
mixed checkout remains unchanged. No further live database request was necessary
for branch integration; the migration and SQL test hashes match the executed files.

```bash
PYTHONPATH=agent:dispatch timeout 60s /path/to/venv/bin/python -m pytest agent/tests e2e/test_kind_verification.py -q
PYTHONPATH=agent:dispatch /path/to/venv/bin/python agent/scripts/evaluate_supabase_localization.py --output docs/evidence/supabase-localization-2026-10-20/paired-replay-main.json
```

The isolated agent/kind-harness run passed **524 tests, 4 skipped, 13 subtests**.
See `pr-integration-tests.txt`. This is a local regression suite, not a new real
kind/sandbox run. `paired-replay-main.json` records the current source hashes;
`paired-replay.json` retains the original investigation snapshot and its hashes.
The original mixed-checkout escalation-reason scanner failure is absent here.

Integration initially refused both positive image cases because the older fixture
generators omitted main's image-pull evidence contract. The generators now mark
synthetic signatures as mock_fixture and use the existing mock-backend gate,
including not_found, regular-container and owner_verified fixture attributes.
No production gate was relaxed. Added offline regressions cover the paired replay
and the qualification harness with a fake catalog and no executor. Frozen case
labels, candidate pools and scorer weights were unchanged. Final replay: 4 ranking
wins / 15 ties / 1 catalog-outage regression; expected images 2/2, negative refusals
6/6, unsafe approvals 0. These are simulated results, not new live evidence.

## CI fixture correction — 2026-10-20

[Cross-repository run 39405584054](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39405584054)
passed contracts, mock integration and Secret-kind controls but failed positive
real-kind image repair at the fix_finalized assertion. Its artifact showed
patch_value_unavailable, localization operation deploy, and baseline_count zero.
The catalog fixture omitted operation, so the new exact-scope checks correctly
rejected it. Contract renewal was unnecessary; the contracts check passed.

The fixture builder now includes operation deploy. A loopback-REST/real-graph
regression failed before this correction (baseline_count 0) and passed afterward,
including exact approved-image selection. Production gates and contract pins are
unchanged. Focused kind-harness, graph-localization and image-provenance tests:
**52 passed, 13 subtests passed**. git diff --check passed. No new real cluster or
Supabase requests were made for this correction. Per user instruction, delivery
stops after commit/push without waiting for the new hosted CI run.
