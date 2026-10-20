-- One company can own multiple clients. Existing healthy/telemetry foreign
-- keys retain the separate UNIQUE(company_id, client_id) ownership constraint.
begin;
alter table public.raphael_clients drop constraint raphael_clients_pkey;
alter table public.raphael_clients add primary key (client_id);

-- Only issuer-controlled top-level JWT claims establish tenant ownership.
-- Never use user_metadata for authorization. No anonymous or authenticated
-- write grant/policy is introduced; backend keys still bypass RLS.
drop policy if exists raphael_clients_company_select on public.raphael_clients;
create policy raphael_clients_company_select on public.raphael_clients
for select to authenticated using (
  company_id::text = (auth.jwt() ->> 'company_id')
  and client_id = (auth.jwt() ->> 'client_id')
);
drop policy if exists raphael_healthy_traces_company_select on public.raphael_healthy_traces;
create policy raphael_healthy_traces_company_select on public.raphael_healthy_traces
for select to authenticated using (
  company_id::text = (auth.jwt() ->> 'company_id')
  and client_id = (auth.jwt() ->> 'client_id')
);
commit;
