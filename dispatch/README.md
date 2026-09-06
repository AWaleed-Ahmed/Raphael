# Dispatch operational notes

Connector deployments use `RAPHAEL_DISPATCH_TOKENS`, a JSON object mapping each
Bearer token to `{ "tenant_id": "...", "role": "producer"|"connector" }`.
Producer tokens submit unchanged connector-v1 job envelopes to
`POST /v1/tenants/{tenant_id}/jobs`; connector tokens poll
`GET /v1/tenants/{tenant_id}/jobs/next`. The path tenant must match the token.
The legacy `POST /v1/jobs` endpoint remains for compatibility but is deprecated
for new producer integrations because it returns the first action directly.

The dispatch service reaps expired connector leases automatically every 10 seconds by default. Configure the cadence with `RAPHAEL_LEASE_REAP_INTERVAL_SECONDS`; `POST /v1/leases/reap` remains available as an explicit operations override.

Each state transition is persisted as a complete JSON document through the existing agent `RunStore`, so dispatch-specific fields such as `dispatch.stage`, `dispatch.pending_action`, and `dispatch.processed_actions` are included in the stored record. On startup, dispatch restores nonterminal jobs with a still-valid lease and reissues their existing pending action unchanged. Persisted jobs whose lease was already expired are failed closed with `job_lease_expired` before traffic is accepted.
