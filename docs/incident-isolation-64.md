# Issue #64: local incident index isolation

Implemented candidate on `codex/issue-64-tenant-similarity`. Inference remains
default-off. No customer data, live Supabase project, production workload or
external model provider is used. Full all-five graph qualification stays in #65.

## Scope contract and trusted source

One backend deployment is explicitly bound by operator configuration to one
`RAPHAEL_AGENT_TENANT_ID`, `RAPHAEL_COMPANY_ID`, `RAPHAEL_CLIENT_ID` triple. All
three must be nonempty and known. There is no `local-dev` fallback for search.
This retains the existing single-company/client backend posture; shared-worker
multi-client routing is not introduced by this issue.

For dispatch jobs, the tenant comes from the configured bearer-token principal:
`submit_tenant_job` checks the tenant URL against that principal and intake stores
that tenant in RunState. `scope_for_run` requires an exact match with the backend
binding. Manual/agent execution is operator-bound to that same deployment; the
shared interface bearer is not interpreted as a tenant JWT. An unauthenticated
compatibility intake's generic `connector` tenant does not grant incident access.
Do not bind an operator deployment to an untrusted generic compatibility tenant.

Run, observation and normalized-signature company/client/tenant fields are only
consistency hints. Missing backend scope, a missing/mismatched run tenant,
conflicting hints, malformed scope carriers, or fabricated `verified` flags cannot
grant search authorization. The immutable `IncidentScope` travels separately from
text features through `ModelGateway` and is checked again by direct runtime calls.
The approved index must contain exactly one partition for the complete triple.

Examples of safe refusal reasons are `incident_scope_unverified`,
`incident_scope_mismatch`, `incident_partition_unavailable` and
`incident_record_scope_unverified`. These contain no incident text, scope IDs,
file paths or deserialization diagnostics. Disabled/unavailable retrieval preserves
the deterministic path. Existing image/patch policy and blocked-path gates remain.

## Retrieval, ranking and artifact migration

The old format-1 index embeds records without ownership and fits one global
vectorizer/matrix. Filtering only its output would still allow foreign records to
influence TF-IDF statistics, scoring and top-k. It is not relabelled or used as a
public fallback.

Only `incident_similarity` moves to format 2. Each partition has an exact scope,
its own independently fitted vectorizer/matrix, and owner fields on every record.
The runtime selects the partition before text transformation, scoring or top-k;
then it validates record ownership and matrix row count. Missing/ambiguous
partitions or incomplete ownership refuse the whole search. Results copy record
fields, so caller mutation cannot poison the cached index. Ranker feature
projection ignores unowned/wrong-owner/non-finite cached similarity hints.

The loader still pins independent manifest and artifact SHA-256 hashes and byte
lengths in release-owned code, hashes the same bounded bytes it deserializes,
and rejects legacy or unsupported formats. No customer-provided pickle is
accepted. The other four model artifacts are unchanged. Deploy matching code,
manifest and model bytes from one reviewed Git revision and restart the worker;
old/mixed releases fail closed. A real customer corpus would require explicitly
verified ownership, independently built partitions and reviewed release trust
roots. This test corpus is not such a deployment or an authorization to enable it.

## Real-world inputs and explicit test ownership

The existing public query fixture contains 50 source-linked GitHub issue reports.
On 2026-10-26, 49 were verified using the public issue API, with URLs, titles,
timestamps, body hashes and fixture-input hashes retained in
[source verification](../agent/tests/fixtures/incident_isolation/public-sources.json).
`luxfi/node#143` returned HTTP 404 twice and is excluded from the index. The
historical query fixture remains unchanged; its excluded query may abstain.

The same 49 available reports are repeated in four explicitly owned fixture
partitions: two fictional companies, each with two clients. Identical text,
fingerprints and service names therefore cannot substitute for authorization.
This is 196 test records/searches, not 196 independent real incidents. Source
authorship is unrelated to test ownership; labels are marker-derived and fix
correctness is not established. `successful_fix_template` is unset. No implicit
public/shared-corpus exception exists.

The [replay report](evidence/incident-isolation-64.json) records 196 authorized
matches, 588 forged-identity refusals, direct-unscoped refusals and unchanged real
ranker output under foreign-owner hints. Four per-scope prediction hashes and
source/artifact identities make the results reproducible. Other tests perturb an
unauthorized partition's IDF, matrix, summary and patch hint and verify identical
authorized output with no canary in results/logs. These perturbations modify only
test process memory after the trusted loader; actual altered on-disk artifacts
are independently proved to fail before deserialization.

## Verification

Local Linux / CPython 3.12.3 with the qualified `local-inference` extra:

- Full agent: **570 passed, 4 skipped** (optional integrations).
- Scope + inference statement coverage: **93%**; scope module **98%**, artifact loader **100%**.
- Clean installation test: stages only the package, installs it, destroys the
  build source and replays outside the repository. Actual socket operations are
  denied. It exercises all four scopes, forged/missing scope and default-off.
- Real graph localization uses the packaged gateway/vectorizers. Only the
  unrelated healthy catalog is stubbed; no prediction function is replaced.
- Real bearer-token dispatch test rejects cross-tenant endpoints and proves the
  accepted principal's RunState controls access to actual artifact records.
- Strict typing, Black and Ruff validate the changed inference/scope tooling.
- Dispatch: **89 passed**. Workflow/security/evaluation/wire assertions: **58 passed**.
- Strict mypy: **10 source files passed**; changed inference/scope tooling passed
  Black and Ruff, and `git diff --check` passed. Hosted results are tracked on the PR.

To reproduce with the qualified installed environment from the repository root:

```bash
python -m pytest agent/tests/test_incident_isolation.py \
  agent/tests/test_local_inference.py agent/tests/test_local_inference_install.py \
  agent/tests/test_model_gateway.py dispatch/tests/test_tenant_queue.py -q
python agent/scripts/qualify_incident_isolation.py \
  --model-root models \
  --cases agent/tests/fixtures/local_inference/incident_similarity.jsonl \
  --source-verification agent/tests/fixtures/incident_isolation/public-sources.json \
  --output /tmp/incident-isolation-64.json
cmp /tmp/incident-isolation-64.json docs/evidence/incident-isolation-64.json
python agent/scripts/build_scoped_incident_fixture.py \
  --source agent/tests/fixtures/local_inference/incident_similarity.jsonl \
  --source-verification agent/tests/fixtures/incident_isolation/public-sources.json \
  --output /tmp/rebuilt-incident-index
python -m pytest agent/tests/test_local_inference.py::test_scoped_fixture_reproduces_index -q
```

The release artifact is hash-pinned byte for byte. Rebuilding on another Python
patch/CPU may change joblib bytes; the rebuild test instead requires identical
ownership, records, vectorizer parameters/vocabulary and numerically equivalent
IDF/matrix values. Such regenerated bytes are not automatically trusted and still
require release review and independent repinning before runtime loading.

CI runs both the existing public-input replay with an explicit test scope and
the four-scope isolation replay; their JSON reports are uploaded together. This
qualifies local incident-index isolation, not production accuracy, live customer
membership management, Supabase ingestion/RLS or pilot rollout.
