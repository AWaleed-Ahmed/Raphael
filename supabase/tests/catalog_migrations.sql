-- Run with: supabase db query --linked --file supabase/tests/catalog_migrations.sql
-- All fixture writes and temporary helpers roll back, including on SQL failure.
-- Public source provenance (not an observed deployment or real customer trace):
-- https://github.com/pallets/flask/blob/2c1b30d0503cfb064f1cb252e6614a06915a362a/examples/tutorial/flaskr/__init__.py#L29
-- Source SHA256: ecfe54451a0cb1cfb8aac26d0f65bdfc4b1fc5ccd7148f4ad38829a8ba26f03a
-- Real repository/commit/path/route; synthetic tenant IDs, spans and health assertion.
begin;
set local statement_timeout = '15s';
set local lock_timeout = '3s';
create temporary table qualification_results (name text primary key, passed boolean);
grant insert, select on qualification_results to authenticated, anon, service_role;
create function pg_temp.check_result(label text, ok boolean) returns void
language plpgsql as $$
begin
  if ok is distinct from true then raise exception 'Qualification failed: %', label; end if;
  insert into qualification_results values (label, true);
end;
$$;

select pg_temp.check_result('all three tables have RLS',
  (select count(*) = 3 and bool_and(relrowsecurity) from pg_class
   where oid in ('public.raphael_clients'::regclass,
     'public.raphael_healthy_traces'::regclass,'public.raphael_telemetry_events'::regclass)));
select pg_temp.check_result('client primary key supports sibling clients',
  (select pg_get_constraintdef(oid) = 'PRIMARY KEY (client_id)' from pg_constraint
   where conrelid='public.raphael_clients'::regclass and contype='p'));
select pg_temp.check_result('both ownership FKs remain',
  (select count(*)=2 from pg_constraint where confrelid='public.raphael_clients'::regclass
   and contype='f' and confdeltype='c'));
select pg_temp.check_result('API grants are least privilege', not exists (
  select 1 from (values ('anon'),('authenticated')) r(role)
  cross join (values ('raphael_clients'),('raphael_healthy_traces'),('raphael_telemetry_events')) t(tab)
  cross join (values ('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER')) p(priv)
  where has_table_privilege(r.role, 'public.'||t.tab, p.priv)));
select pg_temp.check_result('anonymous cannot read any application table',
  not has_table_privilege('anon','public.raphael_clients','SELECT')
  and not has_table_privilege('anon','public.raphael_healthy_traces','SELECT')
  and not has_table_privilege('anon','public.raphael_telemetry_events','SELECT'));
select pg_temp.check_result('authenticated cannot read telemetry',
  not has_table_privilege('authenticated','public.raphael_telemetry_events','SELECT'));
select pg_temp.check_result('catalog and telemetry lookup indexes exist',
  (select count(*)=6 from pg_indexes where schemaname='public' and indexname in
    ('raphael_healthy_traces_lookup_idx','raphael_healthy_traces_stack_idx',
     'raphael_healthy_traces_code_idx','raphael_healthy_traces_identity_uidx',
     'raphael_one_last_known_good_idx','raphael_telemetry_events_scope_idx')));

-- Unique run marker is transaction-local; no real registry identity is reused.
select set_config('qualification.run',gen_random_uuid()::text,true);
select set_config('qualification.company_a',gen_random_uuid()::text,true);
select set_config('qualification.company_b',gen_random_uuid()::text,true);
set local role service_role;
insert into public.raphael_clients (company_id,client_id,client_name,metadata,updated_at)
select (case when n='b1' then current_setting('qualification.company_b')
  else current_setting('qualification.company_a') end)::uuid,
  current_setting('qualification.run')||'-'||n,'Public Flask fixture '||n,
  jsonb_build_object('qualification_run',current_setting('qualification.run')),'2000-01-01'
from unnest(array['a1','a2','b1']) n;
select pg_temp.check_result('backend inserts A1 A2 B1',
  (select count(*)=3 from public.raphael_clients
   where metadata->>'qualification_run'=current_setting('qualification.run')));
insert into public.raphael_healthy_traces
  (company_id,client_id,service_name,environment,repository,git_sha,operation,
   trace_provider,normalized_stack_trace,stack_fingerprint,code_id,
   source_file,source_line,source_symbol,source_commit_sha,span_sequence,
   route_handler_map,verified_healthy,is_last_known_good,metadata)
select company_id,client_id,'flaskr','qualification','pallets/flask',
  '2c1b30d0503cfb064f1cb252e6614a06915a362a','GET /hello',
  'synthetic-source-fixture','flaskr.hello','shared-flask-fixture','flaskr.hello',
  'examples/tutorial/flaskr/__init__.py',29,'hello',
  '2c1b30d0503cfb064f1cb252e6614a06915a362a','["flaskr.hello"]',
  '{"GET /hello":"examples/tutorial/flaskr/__init__.py:29"}',true,true,
  metadata||'{"evidence_kind":"public_source_fixture_not_observed_health"}'::jsonb
from public.raphael_clients where metadata->>'qualification_run'=current_setting('qualification.run');
select pg_temp.check_result('backend inserts scoped catalog',
  (select count(*)=3 from public.raphael_healthy_traces
   where metadata->>'qualification_run'=current_setting('qualification.run')));
-- Exercise the production upsert conflict target without creating a second row.
insert into public.raphael_healthy_traces
  select * from public.raphael_healthy_traces
  where client_id=current_setting('qualification.run')||'-a1'
on conflict (company_id,client_id,service_name,environment,operation,
  stack_fingerprint,code_id,source_commit_sha) do update set verified_healthy=excluded.verified_healthy;
select pg_temp.check_result('catalog upsert is idempotent',
  (select count(*)=3 from public.raphael_healthy_traces
   where metadata->>'qualification_run'=current_setting('qualification.run')));
insert into public.raphael_healthy_traces
  (company_id,client_id,normalized_stack_trace,stack_fingerprint,metadata)
select company_id,client_id,'flaskr.hello','default-identity',metadata
from public.raphael_clients where client_id=current_setting('qualification.run')||'-a1';
select pg_temp.check_result('normalized identity defaults and nullable revisions work',
  (select service_name='unknown' and environment='unknown' and operation='unknown'
    and trace_provider='unknown' and code_id='unknown' and source_commit_sha='unknown'
    and repository is null and git_sha is null and catalog_schema_version=1
    from public.raphael_healthy_traces
    where client_id=current_setting('qualification.run')||'-a1' and stack_fingerprint='default-identity'));
delete from public.raphael_healthy_traces
where client_id=current_setting('qualification.run')||'-a1'
  and metadata->>'qualification_run'=current_setting('qualification.run')
  and stack_fingerprint='default-identity';
insert into public.raphael_telemetry_events
  (event_id,company_id,client_id,project_name,run_id,event_type,recorded_at,repository,metadata)
select current_setting('qualification.run')||'-'||client_id,company_id,client_id,
  'Flask source fixture',current_setting('qualification.run'),'run_outcome',now(),
  '{"owner":"pallets","name":"flask"}',metadata
from public.raphael_clients where metadata->>'qualification_run'=current_setting('qualification.run');
select pg_temp.check_result('backend inserts scoped telemetry',
  (select count(*)=3 from public.raphael_telemetry_events
   where run_id=current_setting('qualification.run')));
update public.raphael_clients set client_name=client_name
where client_id=current_setting('qualification.run')||'-a1';
select pg_temp.check_result('updated_at trigger runs',
  (select updated_at>'2000-01-01' from public.raphael_clients
   where client_id=current_setting('qualification.run')||'-a1'));

-- Each expected constraint failure uses a PL/pgSQL subtransaction.
do $$ begin
  begin
    insert into public.raphael_clients select * from public.raphael_clients
    where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'duplicate client accepted';
  exception when unique_violation then perform pg_temp.check_result('duplicate client refused',true); end;
  begin
    update public.raphael_healthy_traces set company_id=current_setting('qualification.company_b')::uuid
    where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'wrong company/client pairing accepted';
  exception when foreign_key_violation then perform pg_temp.check_result('catalog ownership FK enforced',true); end;
  begin
    insert into public.raphael_telemetry_events
    select (jsonb_populate_record(null::public.raphael_telemetry_events,
      to_jsonb(t)||jsonb_build_object('event_id',gen_random_uuid()::text,
        'company_id',current_setting('qualification.company_b')))).*
    from public.raphael_telemetry_events t where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'wrong telemetry pairing accepted';
  exception when foreign_key_violation then perform pg_temp.check_result('telemetry ownership FK enforced',true); end;
  begin
    update public.raphael_healthy_traces set verified_healthy=false
    where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'unverified catalog row accepted';
  exception when check_violation then perform pg_temp.check_result('verified-only constraint enforced',true); end;
  begin
    update public.raphael_healthy_traces set source_line=0
    where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'invalid source line accepted';
  exception when check_violation then perform pg_temp.check_result('source line constraint enforced',true); end;
  begin
    insert into public.raphael_telemetry_events
    select (jsonb_populate_record(null::public.raphael_telemetry_events,
      to_jsonb(t)||jsonb_build_object('event_id',gen_random_uuid()::text,'event_type','invalid'))).*
    from public.raphael_telemetry_events t where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'invalid event type accepted';
  exception when check_violation then perform pg_temp.check_result('telemetry event constraint enforced',true); end;
  begin
    insert into public.raphael_healthy_traces
    select (jsonb_populate_record(null::public.raphael_healthy_traces,
      to_jsonb(t)||jsonb_build_object('healthy_trace_id',gen_random_uuid(),
        'stack_fingerprint','conflicting-lkg'))).*
    from public.raphael_healthy_traces t
    where client_id=current_setting('qualification.run')||'-a1';
    raise exception 'conflicting LKG accepted';
  exception when unique_violation then perform pg_temp.check_result('conflicting LKG refused',true); end;
end $$;
reset role;

-- LIVE PostgreSQL RLS, with SIMULATED issuer claims. This does not test JWT verification.
set local role authenticated;
do $$ declare n text; company text; begin
  foreach n in array array['a1','a2','b1'] loop
    company:=current_setting(case when n='b1' then 'qualification.company_b' else 'qualification.company_a' end);
    perform set_config('request.jwt.claims',jsonb_build_object('role','authenticated',
      'company_id',company,'client_id',current_setting('qualification.run')||'-'||n)::text,true);
    perform pg_temp.check_result(n||' sees only own client',
      (select count(*)=1 and bool_and(client_id=current_setting('qualification.run')||'-'||n)
       from public.raphael_clients));
    perform pg_temp.check_result(n||' sees only own trace',
      (select count(*)=1 and bool_and(client_id=current_setting('qualification.run')||'-'||n)
       from public.raphael_healthy_traces));
  end loop;
  foreach n in array array['{}',
    jsonb_build_object('company_id',current_setting('qualification.company_a'))::text,
    jsonb_build_object('company_id',current_setting('qualification.company_b'),
      'client_id',current_setting('qualification.run')||'-a1')::text,
    jsonb_build_object('user_metadata',jsonb_build_object('company_id',current_setting('qualification.company_a'),
      'client_id',current_setting('qualification.run')||'-a1'))::text] loop
    perform set_config('request.jwt.claims',n,true);
    if exists(select 1 from public.raphael_clients) or exists(select 1 from public.raphael_healthy_traces)
      then raise exception 'missing/mismatched/untrusted claim exposed data'; end if;
  end loop;
  perform pg_temp.check_result('missing mismatched and user_metadata claims refused',true);
  begin
    insert into public.raphael_clients(company_id,client_id,client_name)
    values (gen_random_uuid(),'forbidden','forbidden');
    raise exception 'authenticated write allowed';
  exception when insufficient_privilege then perform pg_temp.check_result('authenticated write refused',true); end;
  begin
    perform count(*) from public.raphael_telemetry_events;
    raise exception 'authenticated telemetry read allowed';
  exception when insufficient_privilege then perform pg_temp.check_result('authenticated telemetry read refused',true); end;
end $$;
reset role;
set local role anon;
do $$ begin
  begin
    perform count(*) from public.raphael_clients;
    raise exception 'anonymous read allowed';
  exception when insufficient_privilege then perform pg_temp.check_result('anonymous read refused',true); end;
end $$;
reset role;

-- Exercise exact-owned deletion and both FK cascades before rolling everything back.
delete from public.raphael_clients
where client_id=current_setting('qualification.run')||'-a1'
  and company_id=current_setting('qualification.company_a')::uuid
  and metadata->>'qualification_run'=current_setting('qualification.run');
select pg_temp.check_result('exact client deletion cascades trace and telemetry',
  not exists(select 1 from public.raphael_healthy_traces where client_id=current_setting('qualification.run')||'-a1')
  and not exists(select 1 from public.raphael_telemetry_events where client_id=current_setting('qualification.run')||'-a1')
  and (select count(*)=2 from public.raphael_clients where metadata->>'qualification_run'=current_setting('qualification.run')));
select jsonb_build_object('checks',count(*),'passed',bool_and(passed),
  'results',jsonb_agg(name order by name),'fixture_run',current_setting('qualification.run'),
  'rls','LIVE SQL roles; SIMULATED claims; HTTP JWT NOT RUN',
  'cleanup','transaction rolled back after assertions') as qualification
from qualification_results;
rollback;
