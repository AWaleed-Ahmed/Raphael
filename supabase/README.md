# Raphael Supabase setup

The migration creates exactly two application tables:

- `public.raphael_clients`: one row per customer/company.
- `public.raphael_healthy_traces`: verified healthy stack traces, source mappings, release identity, span baselines, and invariants.
- `public.raphael_telemetry_events`: redacted model-call and run-outcome events scoped by company, client, and project.

## Create and link a project

Install the Supabase CLI, authenticate, and create a project from the Supabase dashboard or CLI:

Initialize the local Supabase project directory once (the repository already contains the migrations):

```bash
supabase init
```

```bash
supabase login
supabase projects create raphael-prod --org-id <organization-id> --region <region>
supabase link --project-ref <project-ref>
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

The script upserts a fake client, inserts one verified healthy stack trace, queries it back by company/client, and verifies the stored stack fingerprint. It is intentionally credential-gated and does not delete rows.

## Generate types

```bash
supabase gen types typescript --linked > supabase/database.types.ts
```

The backend must still enforce the same company/client scope when querying the catalog. Service-role access bypasses Supabase RLS, so application-level scoping remains mandatory.

## Compare a failing trace with the healthy catalog

After the migration and `.env` are configured, run the provider-neutral comparison smoke test:

```bash
set -a
source .env
set +a
agent/.venv/bin/python agent/scripts/test_supabase_catalog_compare.py
```

The comparison scopes by `company_id`, `client_id`, service, environment, and operation. It canonicalizes string and structured span representations, detects fingerprint/stack/span divergence, and reports whether the source anchor is shared with the healthy baseline.

`repository`, `git_sha`, and source mapping commit are optional for image-only/serverless deployments. Provider-specific identity belongs in `runtime_identity` and `metadata`; unavailable source commits are stored as `unknown` so upserts remain deterministic.
