-- Normalize release identity fields so non-Git, image-only, and provider-neutral
-- deployments can still register healthy baselines. Provider-specific values
-- remain in runtime_identity/metadata JSONB.
alter table public.raphael_healthy_traces
  alter column service_name set default 'unknown',
  alter column environment set default 'unknown',
  alter column operation set default 'unknown',
  alter column trace_provider set default 'unknown',
  alter column code_id set default 'unknown',
  alter column repository drop not null,
  alter column git_sha drop not null,
  alter column source_commit_sha drop not null;

-- Every row remains versioned for future catalog migrations.
alter table public.raphael_healthy_traces
  add column if not exists catalog_schema_version integer not null default 1;

comment on column public.raphael_healthy_traces.runtime_identity is
  'Provider-neutral deployment identity; may contain OCI, Kubernetes, serverless, or host metadata.';
comment on column public.raphael_healthy_traces.metadata is
  'Provider-specific extensions and normalized ingestion metadata; never store secrets.';
