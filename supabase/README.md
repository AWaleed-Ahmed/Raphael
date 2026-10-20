# Raphael Supabase setup

The migration creates three application tables:

- `public.raphael_clients`: one row per customer/company.
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
