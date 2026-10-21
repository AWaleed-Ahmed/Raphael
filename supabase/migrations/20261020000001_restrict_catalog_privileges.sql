-- Older project defaults granted TRUNCATE/REFERENCES/TRIGGER to API roles.
-- RLS does not protect TRUNCATE. Restore the intended read-only client surface.
begin;
revoke all privileges on table public.raphael_clients,
  public.raphael_healthy_traces, public.raphael_telemetry_events
  from public, anon, authenticated;
grant select on table public.raphael_clients,
  public.raphael_healthy_traces to authenticated;
commit;
