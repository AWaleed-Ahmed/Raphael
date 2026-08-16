-- Use a deterministic sentinel for source revisions that are unavailable.
-- This keeps the healthy-trace upsert key stable for image-only/serverless runs.
update public.raphael_healthy_traces
set source_commit_sha = 'unknown'
where source_commit_sha is null;

alter table public.raphael_healthy_traces
  alter column source_commit_sha set default 'unknown',
  alter column source_commit_sha set not null;
