# Supabase localization qualification — 2026-10-20

> Subsequent authorized run: [database migration validation](supabase-migration-validation-2026-10-20.md).
> All seven migrations are now recorded remotely; 31 database checks passed and
> fixture cleanup was verified. The original investigation below is historical.
> RLS SQL roles were live, issuer claims simulated; actual JWT HTTP access,
> healthy ingestion and sandbox repair remain deferred.

## Decision

**Defer Supabase-backed localization from pilot acceptance claims.** It is now explicitly off unless `RAPHAEL_HEALTHY_CATALOG_ENABLED=1` and the backend has a fixed `RAPHAEL_COMPANY_ID`/`RAPHAEL_CLIENT_ID` pair. Missing/invalid catalog data cannot authorize image repair. Deterministic diagnosis and other supported templates remain available.

| Verdict | Result | Evidence and remaining requirement |
|---|---|---|
| A. Live ingestion/retrieval | **DEFERRED** | No authorized disposable project was established. More fundamentally, automatic healthy-deployment ingestion is absent: only backend store methods and direct-writing smoke scripts exist. A REST seed/read cannot close this gap. |
| B. Tenant isolation | **DEFERRED (LIVE); PASS (targeted offline controls)** | Fixed backend scope, response rechecking, and provenance checks are tested offline. The new SQL migration, service-role application checks, and RLS with actual scoped JWTs still require an authorized disposable project. |
| C. Approved-image selection and sandbox validation | **DEFERRED (LIVE); PASS (targeted offline refusal/selection controls)** | No authorized Ignis executor, disposable workload, healthy observation, failing deployment, or intervention replay was supplied. No sandbox was created or deployment repaired. |
| D. Measured localization benefit | **DEFERRED** | The 20-case synthetic replay improves ranking in four cases and regresses in one. It does not establish benefit on independently observed incidents or workload executions. |

No live Supabase requests, migrations, registry requests, or sandbox mutations were made. Local `.env` contains Supabase URL/backend-key/client configuration, but its project was not established as disposable and migration permission was not supplied. Those credentials were not used, printed, or copied. The process environment had no supplied Supabase or executor configuration. A text request for project authorization/executor identifiers remained unanswered during this qualification; secrets were not requested in chat.

## Revision, environment, and migration scope

- Checkout: `fix/byok-live-qualification`, HEAD `f66a514d92115417a41fdbd1637ed01a9470a0ba`.
- Linux / Python 3.12.3 / repository `.venv`. Default sandbox prohibits sockets; local HTTP fixture tests required network-enabled execution. This is unrelated to live Supabase acceptance.
- Existing dirty files at task start included `.gitignore`, root/contributor/agent/dispatch/frontend documentation, graph/local-model code and tests, `decision.md`, pilot guides, `handoff.md`, `prd.md`, and `supabase/README.md`; untracked planning, issue-reconciliation/local-inference documents and frontend assets were preserved. Shared files were edited only at localization/setup sections for this task. No issue was closed, and no commit, push, or PR was made for this task.
- Existing migrations inspected: `20260815000000`, `20260816000000`, `20260816000001`, `20260816000002`, `20260819000000`.
- New migration prepared: `20261020000000_scope_catalog_clients.sql`. **Not applied or PostgreSQL-executed.** Supabase CLI and psql were unavailable. It preserves composite ownership FKs, changes the client PK from company to client, and requires both company/client claims for authenticated catalog reads.
- Frozen synthetic cases, fixture SHA-256, base revision, and relevant worktree source hashes are in [paired-replay.json](evidence/supabase-localization-2026-10-20/paired-replay.json). These hashes, rather than an uncommitted branch name alone, identify evaluated code.

## Actual pipeline and trust boundaries

1. `ingest/apm_webhook.py`, failed-run normalization, issue/connector ingress and `initial_run_state` produce failure-oriented RunState. The HTTP interface uses a shared operator bearer (or local loopback access), **not** a company/client identity from an authenticated Supabase principal. Seed scope fields therefore cannot authorize catalog access. Connector jobs also do not establish a tenant-to-company/client mapping.
2. `telemetry_supabase.py` writes redacted model/run events to `raphael_telemetry_events`. It does **not** promote healthy deployment telemetry into `raphael_healthy_traces`. Do not describe that telemetry sink as healthy-baseline ingestion.
3. `SupabaseHealthyCatalogStore.record_healthy_trace` is a backend REST upsert. The fake healthy-trace script writes a client and an exception-shaped synthetic record directly, using fake release fields. No production API/worker independently observes Ready state, checks source/image identity, or calls this method to certify health. The local `HealthyCatalogStore` is a separate filesystem store; the scorer holds a reference but does not ingest it into Supabase.
4. Current schema permits only backend/service-role healthy writes; authenticated users have read grants/policies, anonymous users have neither catalog grant nor policy. `verified_healthy` defaults true and has a true-only CHECK; the backend writer decides verification and last-known-good status. These fields are assertions by a privileged writer, not proof of independent health observation. The partial unique index admits one verified LKG per company/client/service/environment/operation; the upsert key includes fingerprint/code/source commit.
5. The previous company primary key prevented two clients under one company. Existing RLS checked company only, exposing same-company sibling clients to a JWT with that company claim. The new migration addresses both defects without granting authenticated writes. Issuer-controlled top-level company/client claims must be configured; user-editable `user_metadata` must never supply authorization.
6. Before the fix, graph scope preferred RunState over backend environment, resolved a company from any requested client, and consumed returned baseline route/span fields even when comparison marked them wrong-scope. The service-role key bypasses RLS, so database filters alone were insufficient. The graph now accepts only the backend-fixed company/client, validates active registry ownership, and rechecks every baseline's company, client, service, environment, operation, repository, and health before comparison, ranking, or image selection. This supports one configured scope per backend worker; dynamic tenant-authenticated catalog access is not implemented.
7. Image resolution requires a verified LKG, trace ID, full hexadecimal source commit, matching repository/service/environment/company/client/Deployment/container, and matching namespace/cluster when either side supplies them. Multiple distinct image/commit candidates refuse. The patch template rechecks trusted scope and opt-in, environment and reported namespace/cluster, along with existing exact rendered workload/container and structural failure gates. No provenance means no image patch, even with catalog assistance disabled. A well-formed SHA is not itself proof that a privileged writer observed a real deployment.
8. Source release/OCI identity and trace provenance are supplied by backend writes. No automatic verifier binds them to a real build or pod. Missing namespace/cluster on both sides remains an identity limitation; the live harness requires these observed fields and will not strip them to make executor validation pass. Explicit operations are matched; a structural `bad_image_reference` defaults to deployment operation `deploy` when no operation is supplied.

## Official authentication check

Supabase documents opaque `sb_secret_...` keys as API keys, not JWTs: send them in `apikey`, not `Authorization: Bearer`. Legacy `service_role` credentials are JWTs. Both backend forms bypass RLS. Authenticated RLS tests must use a publishable/anon key plus a real project-issued user access JWT, never the backend key. Sources checked on this date: [API keys and header limitations](https://supabase.com/docs/guides/getting-started/api-keys), [RLS and trusted claims](https://supabase.com/docs/guides/database/postgres/row-level-security), [JWT reference](https://supabase.com/docs/guides/auth/jwts).

The catalog and its fake baseline smoke now reuse format-aware headers. Catalog REST errors expose sanitized codes only; redirects are rejected, HTTPS is required except loopback, timeouts are finite, and request/response bodies are bounded at 1 MiB. This task does not qualify the separate telemetry sink's legacy transport.

## Isolation and image matrices

All results below are **OFFLINE / SIMULATED**. No database RLS or Ignis result is presented as live evidence.

| Tenant/catalog case | Expected / actual offline result | Live status |
|---|---|---|
| Matching active company/client and repository/service/environment/operation | Scoped baseline accepted | NOT RUN |
| Wrong company; wrong sibling client; spoofed request company/client | No catalog access for request spoof; wrong returned rows discarded before use | NOT RUN |
| Client paired with another company / inactive registry | Registry ownership must match backend scope or error/refuse | NOT RUN |
| Missing company/client; default opt-in off | Zero catalog calls; diagnosis fallback retained | NOT RUN |
| Wrong service/environment/operation/repository | No baseline fields or trace IDs enter ranking/approval/output | NOT RUN |
| Service-role returned mixed-scope rows | Adapter and graph independently recheck scope | NOT RUN |
| Opaque secret vs legacy JWT; provider body contains sensitive marker | Correct headers; no raw error body/credential in exposed errors | NOT RUN |
| Anonymous and unauthorized access; A1/A2/B1 JWTs; missing/mismatched claims | SQL policies prepared; credential-gated harness provided, not executed | NOT RUN |

| Image case | Expected / actual offline result | Live sandbox |
|---|---|---|
| Matching verified LKG with full commit, exact target/container/image repository | Approved; deterministic template still changes only its exact rendered target | NOT RUN |
| Wrong/missing company/client, repository, service, environment | Refused | NOT RUN |
| Wrong workload/container; reported namespace/cluster disagreement | Refused | NOT RUN |
| Unverified/non-LKG; missing/malformed source commit or trace provenance | Refused | NOT RUN |
| Conflicting approved image or commit candidates | Refused | NOT RUN |
| Malformed rows or unavailable catalog | Malformed candidates cannot approve; unavailable catalog cannot authorize a patch | NOT RUN |
| Stale scope or opt-in after localization | Patch boundary rechecks scope/opt-in and refuses | NOT RUN |
| Registry auth failure/outage or unrelated crash | Existing structural bad-image gate remains authoritative; not classified as an approved bad-tag intervention by these tests | NOT RUN |

## Paired experiment: exploratory synthetic replay only

Twenty authored fault/provenance definitions are frozen in [supabase_qualification_cases.json](../agent/fixtures/localization/supabase_qualification_cases.json). Ground-truth paths and positive/refusal labels were written in that fixture file, not copied from localization output. There are 12 synthetic source scenarios and 8 image authorization scenarios, including already-solvable cases, missing/wrong-scope/misleading baselines and one outage. These are **not** 20 independently reproduced customer incidents; no claim of real incident accuracy is made.

Each pair uses the same RunState, runtime evidence, changed-path pool, deterministic weights, and graph/scorer. “Off” means the same deterministic localizer with an empty catalog; “on” supplies the corresponding synthetic rows. It does not compare the entire disabled graph node (which deliberately skips catalog localization) with a running one. All expected paths are in the fixed candidate pool. Rankings are deduplicated by path before scoring. Optional ML, LLM diagnosis/patch, and learning are disabled. No model, database, registry, or executor calls occur.

No ranking weights or final labels were tuned from this replay. An initial harness run lost image signatures because `initial_run_state` does not copy them; the harness injection was corrected before the recorded run. The declaration file remained unchanged. The replay is small, designed, non-independent, and has no production holdout, so it cannot establish reliable deployment benefit.

| Metric | Catalog absent | Catalog supplied |
|---|---:|---:|
| Top-1 localization, all cases | 16/20 (80%) | 19/20 (95%) |
| Top-3 localization, all cases | 16/20 (80%) | 19/20 (95%) |
| Mean reciprocal rank | 0.85 | 0.95 |
| Correct approved image on positive cases | 0/2 (0%) | 2/2 (100%) |
| Correct refusal on negative image cases | 6/6 (100%) | 6/6 (100%) |
| Unsafe approval on negative image cases | 0/6 (0%) | 0/6 (0%) |
| Catalog-covered cases | 0/20 (0%) | 14/20 (70%) |
| Catalog errors | 0/20 (0%) | 1/20 (5%) |
| Sandbox-validated repair | NOT RUN (0 attempts; success rate undefined) | NOT RUN (0 attempts; success rate undefined) |
| Real database latency | NOT RUN | NOT RUN |

Paired localization: **4/20 wins (20%), 15/20 ties (75%), 1/20 regression (5%)**. Wins are payment/inventory/shipping trace and tax route cases. `catalog-outage` regresses because the current unavailable-catalog path stops localization rather than emitting runtime candidates; caller deterministic diagnosis is still available. It was not “fixed” by tuning the held replay. Misleading baseline scenarios do not establish protection against arbitrary misleading hints. Per-mode local execution latency is recorded in the JSON; it is fixture/scorer time, not Supabase latency. Image authorization and localization accuracy are separate; no catalog-less variant bypasses mandatory provenance.

### Per-case recorded results

| Synthetic case | Ground truth path | Off rank | On rank | Off / on image approval |
|---|---|---:|---:|---|
| payment-timeout | `src/payments.py` | 4 | 1 | no / no |
| inventory-shortfall | `src/inventory.py` | 4 | 1 | no / no |
| shipping-rate | `src/shipping.py` | 4 | 1 | no / no |
| tax-rounding | `src/tax.py` | 4 | 1 | no / no |
| order-validation | `src/orders.py` | 1 | 1 | no / no |
| refund-timeout | `src/refunds.py` | 1 | 1 | no / no |
| stock-update | `src/stock.py` | 1 | 1 | no / no |
| invoice-parse | `src/invoice.py` | 1 | 1 | no / no |
| misleading-wrapper-span | `src/checkout.py` | 1 | 1 | no / no |
| misleading-route-map | `src/discount.py` | 1 | 1 | no / no |
| wrong-company-baseline | `src/customer.py` | 1 | 1 | no / no |
| catalog-outage | `src/session.py` | 1 | none | no / no |
| image-approved-api | `deploy/app.yaml` | 1 | 1 | no / yes |
| image-approved-worker | `deploy/app.yaml` | 1 | 1 | no / yes |
| image-unverified | `deploy/app.yaml` | 1 | 1 | no / no |
| image-no-commit | `deploy/app.yaml` | 1 | 1 | no / no |
| image-wrong-client | `deploy/app.yaml` | 1 | 1 | no / no |
| image-wrong-container | `deploy/app.yaml` | 1 | 1 | no / no |
| image-conflicting-approvals | `deploy/app.yaml` | 1 | 1 | no / no |
| image-missing-baseline | `deploy/app.yaml` | 1 | 1 | no / no |

## Fixes and tests

- Correct opaque-secret vs legacy-JWT headers in the catalog and reuse them in the fake baseline writer. Sanitize provider/transport failures, reject redirects, bound bodies, and validate endpoint/timeouts.
- Default the unqualified catalog path off; bind access to operator-configured company/client, reject spoofed scope before lookup, verify active client ownership, and discard wrong-scope/repository/unverified rows before any baseline field is consumed.
- Require tenant provenance at image selection and again at patch generation; reject conflicting commits and reported namespace/cluster mismatches. Existing bad-tag classification, exact rendered-target policy, Secret gates and sandbox validation remain authoritative.
- Fix false trace divergence from stringifying structured golden spans, the unconditional first-span fallback on identical traces, and the graph awarding a trace-divergence bonus to the first stack anchor even without a divergent trace.
- Prepare the narrow client-key/RLS migration. It is not applied here. The live command will detect an old one-client-per-company schema when inserting A2, then clean up only its own run.

Recorded commands:

- Affected catalog, localization, graph, provenance, patch and harness tests: **74 passed**, followed by **114 passed** including diagnosis and blocked-boundary tests (the latter includes an added cleanup-manifest regression).
- Graph-phase-2 and BYOK tests: **81 passed**.
- Full local `agent/tests` plus `e2e/test_kind_verification.py`, with loopback permission: **437 passed, 4 skipped, 1 failed**. The failure is the pre-existing dirty local-inference change in `node_evidence`: `reason = model_error(gateway) or "unknown"` is interpreted by the escalation reason AST scanner as an unregistered reason. That unrelated change was present at task start and was preserved. The four skips are optional integrations, not Supabase proof.
- Earlier default-sandbox broader attempt timed out after 45 seconds; a local HTTP fixture also failed with socket `PermissionError`. The network-enabled run above completed in 6.05 seconds. Neither run used live Supabase credentials.
- The live command's no-authorization mode returned exit 2 and `BLOCKED ... no requests made`; `--plan` generated two companies/three clients without constructing a database client.
- Replay: `PYTHONPATH=agent ./.venv/bin/python agent/scripts/evaluate_supabase_localization.py --output docs/evidence/supabase-localization-2026-10-20/paired-replay.json`.
- `git diff --check`: clean. No live project rows, sandbox resources, or cluster resources were created; none need cleanup. Retained artifacts are only the fixture definitions, scripts, tests, migration source, report, and offline JSON evidence.

## Runnable live command and exact prerequisites

### 1. Authorization and migration setup (not performed here)

Identify an owner-authorized **disposable** project hostname/ref, an approved migration window, an operator-owned credential profile, and a disposable workload/executor/context. Do not reuse a production project or authorize by the mere existence of `.env`.

Install the Supabase CLI in the operator environment if needed. From the repository, after approval for that specific project:

```bash
supabase link --project-ref "$QUAL_PROJECT_REF"
supabase migration list
supabase db push --dry-run
# Review the exact pending repository migrations and confirm the linked test project.
supabase db push
```

Do not reset a shared database. The new migration changes authenticated read semantics: both issuer-controlled company and client claims are now necessary. Check existing readers before applying it outside a disposable project.

Load the backend profile explicitly in the qualification shell, clearing stale credentials first:

```bash
unset SUPABASE_URL SUPABASE_SECRET_KEY SUPABASE_SERVICE_ROLE_KEY
unset SUPABASE_PUBLISHABLE_KEY SUPABASE_ANON_KEY
set -a
source "$QUALIFICATION_PROFILE"
set +a
```

The profile must provide `SUPABASE_URL` and either `SUPABASE_SECRET_KEY` or legacy `SUPABASE_SERVICE_ROLE_KEY` for this authorized project. To exercise RLS also provide `SUPABASE_PUBLISHABLE_KEY` (or legacy `SUPABASE_ANON_KEY`) and `SUPABASE_TEST_JWT_A1`, `SUPABASE_TEST_JWT_A2`, `SUPABASE_TEST_JWT_B1`, `SUPABASE_TEST_JWT_UNSCOPED`, `SUPABASE_TEST_JWT_MISMATCHED`. Keep profile files and JWTs outside the repository; do not print or paste them into chat.

Choose a fresh run UUID and print only its planned test identities:

```bash
QUAL_RUN_ID=$(./.venv/bin/python -c 'import uuid; print(uuid.uuid4())')
PYTHONPATH=agent ./.venv/bin/python agent/scripts/qualify_supabase_localization.py \
  --run-id "$QUAL_RUN_ID" --plan
```

Use the project owner's trusted Auth/custom-access-token hook to issue actual `authenticated` test JWTs carrying these **top-level** `company_id` and `client_id` claims. A1/A2 share the planned company; B1 has the other company. The unscoped identity omits those claims. The mismatched identity carries B's company with A1's client. Do not generate unsigned tokens or derive authorization from `user_metadata`. The harness also tries an intentionally invalid synthetic token and anonymous reads/writes. Missing keys/JWTs produce BLOCKED entries, not RLS passes. No signing key is requested by the script.

### 2. Independently observe the healthy workload

Use a specifically authorized disposable cluster/context and namespace. Record full healthy source SHA (`git rev-parse HEAD` in the workload repo), repository, observed image reference/digest, Deployment and container, cluster/context and namespace, service/environment/operation, actual trace ID, and health observation. Example observation commands, after the operator has created the disposable workload:

```bash
kubectl --context "$QUAL_CONTEXT" -n "$QUAL_NS" wait \
  --for=condition=Available "deployment/$QUAL_DEPLOYMENT" --timeout=90s
kubectl --context "$QUAL_CONTEXT" -n "$QUAL_NS" get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.conditions[?(@.type=="Ready")].status}{" "}{.status.containerStatuses[*].name}{" "}{.status.containerStatuses[*].imageID}{"\n"}{end}'
curl --fail --max-time 5 "$QUAL_HEALTH_URL"
git -C "$QUAL_WORKLOAD_REPO" rev-parse HEAD
```

Prepare an operator-owned JSON file referenced by `QUAL_HEALTHY_RECORD`, with real observed values for:

- `service_name`, `environment`, `operation`, `repository` (`owner/name`), actual `trace_id`, full `source_commit_sha`.
- `runtime_identity`: `resource_kind="Deployment"`, `resource_name`, `namespace`, `cluster`, and `container_images` mapping exact container names to observed `repository@sha256:<64 hex>` references.
- `health_observation`: `ready=true`, actual `observed_at`, and `evidence_path` pointing to retained independent readiness/application-health evidence.

Placeholders, fake SHAs/digests, an exception stack alone, or a hand-written `ready=true` without observation are not health proof. The script validates input structure; it does not independently authenticate a hand-edited observation. It deliberately labels its inserted copies `qualification-direct-seed` and **never** reports production ingestion as passed.

### 3. Run adapter/graph/RLS fixture qualification

```bash
PYTHONPATH=agent ./.venv/bin/python agent/scripts/qualify_supabase_localization.py \
  --live --project-host "$QUAL_PROJECT_REF.supabase.co" \
  --run-id "$QUAL_RUN_ID" --observed-baseline "$QUAL_HEALTHY_RECORD" \
  --output "/tmp/raphael-supabase-$QUAL_RUN_ID.json"
```

This is a runnable live **fixture qualification** command, not end-to-end ingestion acceptance. It creates planned A1/A2/B1 registry rows, inserts overlapping direct REST fixture copies, verifies idempotent upserts, queries through the production adapter, checks wrong scope, verifies conflicting-LKG database refusal, and exercises the actual graph node's scoped image selection/refusal. Optional real-user JWTs independently test RLS using the public API key. No service-role result is counted as RLS evidence. It disables ML/LLMs/learning and does not execute or publish a patch.

Expected output: sanitized host/run IDs/owned row IDs, per-check status, request counts/timing, explicit production-ingestion and sandbox deferrals, and cleanup status. Exit 0 means requested fixture checks completed, **not** overall qualification. Exit 2 means preflight or RLS inputs are incomplete; exit 1 means an assertion, transport, schema, or cleanup failure. `overall` remains DEFERRED because ingestion and live repair are not established. A2 conflict on the old schema means the new migration has not been applied. HTTP 401/403 requires checking key format/project/claims/grants; never retry with a browser-exposed backend key. Never strip scope or provenance fields to force a pass.

Default cleanup runs in `finally`, even after failure. `--retain` is an explicit option only when an operator needs these exact test rows for the next disposable executor step. Retained IDs/markers are recorded; it must be followed by the exact cleanup command below.

### 4. Remaining real ingestion and Ignis validation work

There is no supported automatic healthy-deployment writer to invoke today. A must remain deferred until an authorized ingestion design establishes authenticated tenant mapping, observed health certification and immutable release/container provenance, and its real writer is exercised. Do not substitute the fake smoke or the fixture harness for it.

For C, use a frozen disposable repo containing an actually healthy revision and a bad-image-only revision, with the same logical Deployment/container. Record the healthy baseline and approved image, then reproduce the bad reference with real Ignis. Baselines copied by the harness can only prove fixture-backed retrieval/selection. The existing real-process runner is `e2e/run_real_job.py`; required operator inputs include:

```bash
export E2E_IGNIS_BIN="$QUAL_VERIFIED_IGNIS_BINARY"
export E2E_CLUSTER_BACKEND=kind
export E2E_KUBE_CONTEXT="$QUAL_CONTEXT"
export E2E_REAL_CLONE_URL="$QUAL_DISPOSABLE_REPOSITORY_URL"
export E2E_REAL_COMMIT_SHA="$QUAL_BAD_IMAGE_COMMIT"
export E2E_REAL_NARROWED_LOCATION=deploy/manifests/app.yaml
export E2E_REAL_RESULT_FILE="/tmp/raphael-supabase-$QUAL_RUN_ID-executor.json"
export RAPHAEL_HEALTHY_CATALOG_ENABLED=1
# Backend company/client must match the planned A1 row; never take them from a job payload.
export RAPHAEL_COMPANY_ID="$QUAL_COMPANY_A"
export RAPHAEL_CLIENT_ID="$QUAL_CLIENT_A1"
export RAPHAEL_DEFAULT_ENVIRONMENT="$QUAL_ENVIRONMENT"
export RAPHAEL_MODEL_ENABLED=0 RAPHAEL_LEARNING=0 RAPHAEL_LLM_DIAGNOSIS=0 RAPHAEL_LLM_PATCH=0
export RAPHAEL_PARTNER_MODE=dry_run RAPHAEL_PUBLISH_MODE=dry_run
unset GITHUB_TOKEN RAPHAEL_GITHUB_TOKEN RAPHAEL_GITHUB_APP_PRIVATE_KEY RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH
PYTHONPATH=agent:dispatch ./.venv/bin/python e2e/run_real_job.py
```

Use an Ignis binary matching this checkout's reviewed contract pin. Supply a dedicated `kind-...` context; never production Kubernetes. Verify the runner's derived repository/service/environment/operation and observed workload identities match the retained rows; its fixture repository name is `raphael-e2e-fixture`. If these identities do not match, refusal is the expected result. If the executor lacks namespace/cluster identity or maps the source namespace to a different sandbox namespace, define and review that trusted identity mapping before claiming success; do not delete baseline fields to evade the refusal.

Independently retain original image-pull-not-found evidence and after-intervention Ready/application-health evidence; registry auth/outage/crash cases must refuse. Inspect the exact changed container/image, policy, validation output, and repeatability. Include no-provenance, conflicting and wrong-scope controls. A terminal envelope or a successful database query alone is insufficient. This command and those workload conditions were **not run here** and are not promised to pass. Existing hosted kind proof used a fixture HTTP catalog; it is not live Supabase proof.

### 5. Exact cleanup and retained resources

Retry only the exact qualification run's database cleanup:

```bash
PYTHONPATH=agent ./.venv/bin/python agent/scripts/qualify_supabase_localization.py \
  --live --project-host "$QUAL_PROJECT_REF.supabase.co" --run-id "$QUAL_RUN_ID" \
  --cleanup "/tmp/raphael-supabase-$QUAL_RUN_ID.json" \
  --output "/tmp/raphael-supabase-$QUAL_RUN_ID-cleanup.json"
```

The script derives only its planned unique client IDs and company IDs and additionally requires the matching `metadata.qualification_run` marker on DELETE; trace FKs cascade only for those clients. The manifest records intended trace IDs before writing, plus returned IDs. No prefix-wide delete, reset, or shared tenant deletion is used. A mismatched cleanup manifest causes zero database access.

If an operator runs the separate executor experiment, record every created sandbox ID/namespace at creation. Destroy only those exact IDs with `SandboxClient.destroy_sandbox(id, {"reason":"qualification-cleanup"})` or the corresponding `/v1/sandboxes/<owned-id>/destroy` endpoint. Delete the independently created healthy namespace only when it is in that run's ownership ledger:

```bash
kubectl --context "$QUAL_CONTEXT" delete namespace "$QUAL_NS" --ignore-not-found=true
```

Do not delete another run's namespace/cluster. No live resources exist from the qualification recorded here, so these commands were not executed.
