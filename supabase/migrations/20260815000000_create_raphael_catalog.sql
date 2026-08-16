-- Raphael multi-tenant client registry and healthy trace/source catalog.
-- The service role performs ingestion. End-user access is restricted by
-- company_id in the caller's Supabase JWT custom claims.

create extension if not exists pgcrypto;

create table if not exists public.raphael_clients (
  company_id uuid primary key default gen_random_uuid(),
  client_id text not null unique,
  client_name text not null,
  status text not null default 'active'
    check (status in ('active', 'suspended', 'deleted')),
  hosting_provider text,
  cluster_provider text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (company_id, client_id)
);

create table if not exists public.raphael_healthy_traces (
  healthy_trace_id uuid primary key default gen_random_uuid(),
  company_id uuid not null,
  client_id text not null,
  service_name text not null,
  environment text not null,
  repository text not null,
  git_sha text not null,
  image_digest text,
  operation text not null,
  trace_provider text not null,
  trace_id text,
  stack_trace text,
  normalized_stack_trace text not null,
  stack_fingerprint text not null,
  code_id text not null,
  source_file text,
  source_line integer,
  source_symbol text,
  source_commit_sha text not null,
  span_sequence jsonb not null default '[]'::jsonb,
  route_handler_map jsonb not null default '{}'::jsonb,
  runtime_identity jsonb not null default '{}'::jsonb,
  invariants jsonb not null default '[]'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  verified_healthy boolean not null default true,
  is_last_known_good boolean not null default false,
  verified_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint raphael_healthy_traces_company_client_fk
    foreign key (company_id, client_id)
    references public.raphael_clients (company_id, client_id)
    on delete cascade,
  constraint raphael_healthy_traces_source_line_check
    check (source_line is null or source_line > 0),
  constraint raphael_healthy_traces_verified_check
    check (verified_healthy = true)
);

create index if not exists raphael_healthy_traces_lookup_idx
  on public.raphael_healthy_traces
    (company_id, client_id, service_name, environment, operation);

create index if not exists raphael_healthy_traces_stack_idx
  on public.raphael_healthy_traces
    (company_id, normalized_stack_trace, stack_fingerprint);

create index if not exists raphael_healthy_traces_code_idx
  on public.raphael_healthy_traces
    (company_id, code_id, source_commit_sha);

create unique index if not exists raphael_healthy_traces_identity_uidx
  on public.raphael_healthy_traces
    (company_id, client_id, service_name, environment, operation,
     stack_fingerprint, code_id, source_commit_sha);

create unique index if not exists raphael_one_last_known_good_idx
  on public.raphael_healthy_traces
    (company_id, client_id, service_name, environment, operation)
  where is_last_known_good and verified_healthy;

-- PostgREST roles need table privileges in addition to RLS policies.
-- service_role bypasses RLS; authenticated access remains policy-scoped.
grant select, insert, update, delete on table public.raphael_clients to service_role;
grant select on table public.raphael_clients to authenticated;
grant select, insert, update, delete on table public.raphael_healthy_traces to service_role;
grant select on table public.raphael_healthy_traces to authenticated;

-- Keep updated_at server-side for both tables.
create or replace function public.raphael_set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists raphael_clients_updated_at on public.raphael_clients;
create trigger raphael_clients_updated_at
before update on public.raphael_clients
for each row execute function public.raphael_set_updated_at();

drop trigger if exists raphael_healthy_traces_updated_at on public.raphael_healthy_traces;
create trigger raphael_healthy_traces_updated_at
before update on public.raphael_healthy_traces
for each row execute function public.raphael_set_updated_at();

alter table public.raphael_clients enable row level security;
alter table public.raphael_healthy_traces enable row level security;

-- The backend service role bypasses RLS. Browser/client access requires a
-- company_id custom JWT claim, preventing cross-company catalog reads.
drop policy if exists raphael_clients_company_select on public.raphael_clients;
create policy raphael_clients_company_select
on public.raphael_clients
for select
to authenticated
using (company_id::text = (auth.jwt() ->> 'company_id'));

drop policy if exists raphael_healthy_traces_company_select on public.raphael_healthy_traces;
create policy raphael_healthy_traces_company_select
on public.raphael_healthy_traces
for select
to authenticated
using (company_id::text = (auth.jwt() ->> 'company_id'));

comment on table public.raphael_clients is
  'One row per Raphael customer/company; client_id is the customer-facing stable identifier.';

comment on table public.raphael_healthy_traces is
  'Verified healthy trace, stack mapping, source identity, and runtime baseline catalog shared across all clients with company isolation.';
