-- Normalized, redacted model-call and run-outcome telemetry.
create table if not exists public.raphael_telemetry_events (
  event_id text primary key,
  company_id uuid not null,
  client_id text not null,
  project_name text not null,
  run_id text not null,
  event_type text not null check (event_type in ('model_call', 'run_outcome')),
  recorded_at timestamptz not null,
  repository jsonb,
  model_name text,
  model_version text,
  status text,
  success boolean,
  input_excerpt text,
  output_excerpt text,
  input_sha256 text,
  output_sha256 text,
  token_usage jsonb,
  error_type text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  constraint raphael_telemetry_events_company_client_fk
    foreign key (company_id, client_id)
    references public.raphael_clients (company_id, client_id)
    on delete cascade
);

create index if not exists raphael_telemetry_events_scope_idx
  on public.raphael_telemetry_events (company_id, client_id, project_name, recorded_at desc);

grant select, insert on table public.raphael_telemetry_events to service_role;
alter table public.raphael_telemetry_events enable row level security;
