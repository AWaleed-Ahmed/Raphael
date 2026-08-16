-- Supabase/PostgREST table grants for the Raphael catalog.
-- This is separate so existing projects can repair privileges without
-- editing an already-applied migration.
grant select, insert, update, delete on table public.raphael_clients to service_role;
grant select on table public.raphael_clients to authenticated;
grant select, insert, update, delete on table public.raphael_healthy_traces to service_role;
grant select on table public.raphael_healthy_traces to authenticated;
