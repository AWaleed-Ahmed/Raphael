# Raphael Supabase setup

**2026-10-20 database validation:** all seven migrations are applied to the
authorized Raphael project, including the new API privilege restriction migration.
31 live SQL checks passed using public Flask source identities and temporary
synthetic tenants; rollback and matching row hashes verified cleanup. Real JWT
HTTP authentication, healthy ingestion and sandbox repair remain deferred. See
[migration evidence](../docs/supabase-migration-validation-2026-10-20.md).
Re-run the rollback-only database checks with:
`supabase db query --linked --file supabase/tests/catalog_migrations.sql`.

The migration creates three application tables:

- `public.raphael_clients`: one row per client after the scope migration; a company may own multiple clients.
- `public.raphael_healthy_traces`: verified healthy stack traces, source mappings, release identity, span baselines, and invariants.
- `public.raphael_telemetry_events`: redacted model-call and run-outcome events scoped by company, client, and project.

## Optional project prerequisites

Supabase is not required for the [basic pilot installation](../docs/pilot-install.md).
Live catalog ingestion/repair remains unqualified; fixture-backed REST evidence
is not a successful live Supabase run. Obtain backend credentials and migration
approval from the project owner. Python does not automatically load `.env`;
source an operator-owned profile explicitly in each service terminal.

## Create and link a project (separate authorization required)

Install the Supabase CLI, authenticate, and create a project from the Supabase dashboard or CLI:

Initialize the local Supabase project directory once (the repository already contains the migrations):

```bash
supabase init
```

```bash
supabase login
supabase projects create raphael-pilot --org-id "example-organization-id" --region "example-region"
supabase link --project-ref "example-project-ref"
```

If the project already exists, only run `supabase link`.

## Apply migrations

```bash
supabase db push
```

For a local disposable database:

```bash
supabase start
supabase db reset
```

Never put the service-role key in a browser, repository, migration, or frontend environment. Raphael's backend should use it through `SUPABASE_SERVICE_ROLE_KEY`.

For telemetry scope, set `RAPHAEL_CLIENT_ID`. Raphael first uses `RAPHAEL_COMPANY_ID` when provided; if it is absent, the backend resolves `company_id` from `public.raphael_clients` by querying the configured client ID. If neither scope value can be resolved, telemetry skips the upload rather than interrupting the run. `RAPHAEL_COMPANY_ID` is safe to include in local `.env` files, but never commit service-role credentials.

## Run the fake healthy-trace smoke test

```bash
export SUPABASE_URL="https://<project-ref>.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<backend-only-service-role-key>"
export RAPHAEL_CLIENT_ID="demo-client"
export RAPHAEL_CLIENT_NAME="Demo Client"
python3 agent/scripts/test_supabase_healthy_trace.py
```

Run only against an explicitly authorized disposable/test project. These examples
were inspected, not executed in this refresh. The script upserts a fake client, inserts one verified healthy stack trace, queries it back by company/client, and verifies the stored stack fingerprint. It is intentionally credential-gated and does not delete rows.

This generic trace smoke is not the #34 image provenance acceptance pipeline.
Image replacement also requires matching workload/runtime identity, source
revision and approved baseline provenance; missing proof must refuse.

## Generate types

```bash
supabase gen types typescript --linked > supabase/database.types.ts
```

The backend must still enforce the same company/client scope when querying the catalog. Service-role access bypasses Supabase RLS, so application-level scoping remains mandatory.

## Compare a failing trace with the healthy catalog

After the migration and an operator-owned environment profile are configured, run the provider-neutral comparison smoke test:

```bash
set -a
source "$RAPHAEL_PILOT_ROOT/supabase.env"
set +a
python agent/scripts/test_supabase_catalog_compare.py
```

The comparison scopes by `company_id`, `client_id`, service, environment, and operation. It canonicalizes string and structured span representations, detects fingerprint/stack/span divergence, and reports whether the source anchor is shared with the healthy baseline.

`repository`, `git_sha`, and source mapping commit are optional for image-only/serverless deployments. Provider-specific identity belongs in `runtime_identity` and `metadata`; unavailable source commits are stored as `unknown` so upserts remain deterministic.

## Qualification status — 2026-10-20

Live ingestion, actual JWT authentication over HTTP, approved-image sandbox repair,
and production localization benefit are **deferred from pilot claims**. Database
RLS checks passed under SQL roles with simulated issuer claims. See the
[qualification record and runnable test-project procedure](../docs/supabase-localization-qualification-2026-10-20.md).
The `.env` configuration is not evidence that its project is disposable or that
migrations are authorized. The later user-authorized database migration and fixture
run is recorded above; earlier no-live statements in the qualification record are historical.

Catalog assistance now defaults off (`RAPHAEL_HEALTHY_CATALOG_ENABLED=0`). An opt-in
backend must set both `RAPHAEL_COMPANY_ID` and `RAPHAEL_CLIENT_ID`; request fields
cannot choose another tenant. This is one fixed catalog scope per worker, not
request-authenticated multi-tenant access. The telemetry sink's separate legacy
company-resolution behavior does not authorize catalog access.

The applied `20261020000000_scope_catalog_clients.sql` migration makes one row
per **client**, allowing multiple clients per company, while preserving the
company/client FK. It also requires both issuer-controlled company and client
claims for authenticated reads. This migration and the subsequent API privilege
restriction migration passed the recorded live database checks.
Review linked-project identity and approval before running any migration; do not
reset a shared project.

Opaque `SUPABASE_SECRET_KEY` values go in `apikey` only; legacy service-role JWTs
also use Bearer auth. Backend access bypasses RLS. The catalog and fake trace writer
now reuse this distinction; the separate telemetry sink is not qualified by it.
The fake writer now requires the installed agent or `PYTHONPATH=agent` when run
from the repository. It remains a direct fixture writer, not a health verifier.

For a safe preflight and identity plan (no network):

```bash
PYTHONPATH=agent ./.venv/bin/python agent/scripts/qualify_supabase_localization.py \
  --run-id "$QUAL_RUN_ID" --plan
```

The linked qualification record supplies the exact credential-gated live command,
observed-workload file requirements, scoped-JWT setup, expected partial outcomes,
executor setup and exact-row cleanup. There is no automatic healthy-deployment
ingestion path to invoke today; direct REST fixture seeding does not close that gap.
