# Dispatch operational notes

Connector deployments use `RAPHAEL_DISPATCH_TOKENS`, a JSON object mapping each
Bearer token to `{ "tenant_id": "...", "role": "producer"|"connector" }`.
Producer tokens submit unchanged connector-v1 job envelopes to
`POST /v1/tenants/{tenant_id}/jobs`; connector tokens poll
`GET /v1/tenants/{tenant_id}/jobs/next`. The path tenant must match the token.
The legacy `POST /v1/jobs` endpoint remains for compatibility but is deprecated
for new producer integrations because it returns the first action directly.

The dispatch service exposes `POST /v1/leases/reap` for explicit lease cleanup. The current implementation does not run a timer, scheduler, or background reaper; a deployment must invoke this endpoint from its own operational control plane before lease expiry can be enforced continuously. Adding a durable periodic worker is deferred until the connector runtime and deployment model are defined.

Each state transition is persisted as a complete JSON document through the existing agent `RunStore`, so dispatch-specific fields such as `dispatch.stage`, `dispatch.pending_action`, and `dispatch.processed_actions` are included in the stored record. The current `Orchestrator` does not rehydrate `self.jobs` from `RunStore` during process startup, however. A process restart therefore loses in-memory routing of mid-flight jobs even though the last state is persisted; startup rehydration and durable multi-process leasing remain follow-up work.
