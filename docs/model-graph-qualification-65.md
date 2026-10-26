# Issue #65: production-graph local model qualification

This report measures the five approved local model capabilities through the
existing `ModelGateway`, production graph nodes, a compiled LangGraph run and
an explicit opt-in disposable-kind integration. Inference stays **default-off**.
No model is retrained, no external LLM/BYOK is used, and publication is dry-run.

## Evidence boundaries

| Layer | What it proves | What it does not prove |
| --- | --- | --- |
| Public fixture replay | Actual estimator/vectorizer execution, node projection, decisions and measured call latency | Customer production calibration or causal correctness |
| Compiled production graph | All five result slots populated, policy/validation/publish routing and schema-valid final state | A live repair: this control uses clearly labelled recorded sandbox responses |
| Disposable hosted kind | Real dispatch hooks, actual Ignis controller, real Pod/probe failure, patch, sandbox validation and cleanup with models enabled only in this proof | Production tenant deployment, real APM trace accuracy or learned-only patch selection |
| Tenant isolation controls | Only the configured fictional company/client/tenant partition influences retrieval/ranking | Real customer membership provisioning or live Supabase ingestion/RLS |

The public replay uses real loopback HTTP requests through the production
`SupabaseHealthyCatalogStore` to a fixture REST server. That server is labelled
a catalog fixture; it is not a live Supabase project. The real models, gateway,
node functions and compiled graph are never replaced with prediction stubs.
Fault-injection tests intentionally substitute malformed outputs or runtime
errors to prove fallback; they are not counted as successful inference.

## Revisions and environment

- Base revision: `dbae7a2609f90aede92fba7ccd9217ac2df19f31` (merged #63/#64 prerequisites).
- Exact candidate source is the implementation commit on the associated PR;
  CI artifacts identify the tested PR merge revision. The committed local
  replay was collected from the candidate working tree on that base.
- Local platform: `Linux-7.0.0-38-generic-x86_64-with-glibc2.39`; Python `3.12.3`.
- Qualified libraries: joblib 1.6.0, NumPy 2.5.2, SciPy 1.18.1, scikit-learn 1.9.0.
- Local Docker daemon was unavailable. Live Kubernetes evidence must come from
  the disposable hosted run; local replay is not presented as live cluster proof.
- Peak RSS of the complete standalone qualification process: **189.4 MiB**.
  This includes imports, all fixture replays, cached bundles and the compiled
  graph; it is not isolated estimator memory or evidence of a 512 MiB deployment fit.

## Accuracy, coverage and decision source

| Capability | Fixture result and limits | Learned / rule overrides | Warm median / p95 |
| --- | --- | --- | --- |
| Failure classification | 40/40 emitted classifications match (100%); 40/50 overall (80%); 10 image-policy stops | 40 / 40 | 1.92 / 2.93 ms |
| Candidate ranking | 37/50 top-1 fix-file matches (74%); gateway projection of benchmark candidates | 50 / 0 | 1.84 / 2.56 ms |
| Incident similarity | 44/50 top-1 class matches (88%); queries overlap the owned fixture index | 50 / 0 | 5.14 / 6.14 ms |
| Trace anomaly | 38/50 fault-window matches (76%); weak per-trace labels | 50 / 15 | 3.55 / 4.18 ms |
| Patch selection | 12/50 safe-template hypothesis matches (24%); 41/51 outputs, 22 refusals; not repair accuracy | 1 / 40 | 1.12 / 1.37 ms |

These are different measures with deliberately different denominators:

- **Classifier:** all 40 emitted answers agree with marker-derived labels, but
  every one is a deterministic override of a computed learned probability.
  Ten image cases stop at the existing `image_pull_evidence_unverified` gate.
  Calling this 100% learned-model accuracy would be incorrect. The all-input
  match fraction is 80%; the additional OOD control executes the real estimator
  and abstains at the graph's low-confidence gate.
- **Ranker:** 74% is top-1 agreement with actual BugsInPy fix-file labels after
  production gateway feature projection. Historical benchmark candidate features
  are derived from test/path tokens, not captured production stacks. This is
  measured at the gateway, not labelled as 50 end-to-end source-localization
  successes. Separate real graph tests preserve every generated path, line,
  symbol, evidence reference and mapping method across model ordering. Strong
  evidence no longer acquires a fabricated `historical_similarity` tag.
- **Similarity:** the approved format-2 artifact uses 49 available public reports
  repeated in four fictional ownership partitions (#64). These 50 query fixtures
  overlap that corpus; 88% measures retrieval consistency after graph evidence
  projection, not held-out incident generalization. The unavailable historical
  URL is retained as a query, not inserted into the index. Foreign scope can
  neither select a partition nor affect ranker history features.
- **Trace:** RCAEval spans and healthy-window latency are measured microservice
  data around controlled injected faults. The 76% compares trace decisions to
  broad fault-window labels; an individual trace can be normal within a fault
  window. Fifteen decisions use explicit-error/baseline rule overrides after
  learned scoring. This does not establish customer anomaly precision/recall.
- **Patch selector:** only 12/50 weak acceptable-template hypotheses survive the
  graph's concrete generator boundary. Forty rule paths and one learned path
  execute; 21 unsupported template families are refused, and the extra real
  Fission report refuses a low-confidence learned template (22 refusals total).
  Ten image cases remain on the dedicated provenance-backed image path. None
  of these report-level hypothesis matches is counted as a validated repair.

The classifier and similarity evidence pass through the normal bounded/redacted
issue collector. Classifier fixtures project structured failure markers plus
source title/body excerpts. Patch fixtures retain their evidence text. Ranking
uses existing benchmark candidate records. Trace fixtures add measured healthy
latency to an explicitly owned/scoped test baseline. These adaptations are
retained in the fixture files and replay code, rather than silently changing
labels to make scores improve.

## Performance methodology

Each of the 251 cases is run once in source order in a single Python process.
The table measures the warm target node/adapter invocation using `perf_counter`:
classifier = `node_diagnose`, similarity/trace = `node_localize` (including real
loopback catalog HTTP and localization overhead), patch = `node_patch` (including
proposal/refusal checks), ranker = production gateway projection. Initial evidence
collection and its preliminary trace call are outside that target-call timer.
These heterogeneous timings are not an estimator speed comparison.

The p95 is the nearest-rank observation at `ceil(0.95 * n)`. There are no latency
acceptance thresholds, repeated-run confidence intervals, network-to-customer
latency estimates or concurrent throughput claims. Timing varies by machine/load.
Compiled graph elapsed time is **235.079 ms**, with recorded
sandbox responses and a fixture catalog; it is not live repair duration.

The loader cache is cleared before each capability's first explicit load. Those
sequential first-load measurements include validation/deserialization; the first
also pays dependency import cost. They are not five independent process cold starts.

| Bundle | Sequential first-load ms | Approved model SHA-256 |
| --- | ---: | --- |
| failure_classifier | 943.478 | `c029aca6c4c0ac197b1e26c444fe2883001a46289101b972b3e181502f5b0d80` |
| candidate_ranker | 22.828 | `036eca89dc9bb450d665dab516096f8012fb31775f6e187af6a05db2e1cd6b47` |
| incident_similarity | 103.275 | `5fc33e1a21d0e6a600e674ee0a64722e989c491b6e92c602d633f84ef8811644` |
| trace_anomaly | 5.965 | `b946fabc97bb703b4449595126f2c29872e1a6319559fd2de4410f75c8415020` |
| patch_selector | 56.726 | `ed7a9ed3f9713b64bf102e54e734b445b3b6be3e12df8fede4101f6f15741c49` |

Manifest hashes and sizes remain pinned by the trusted loader. No artifact bytes
were changed in this issue. [Local summary](evidence/model-graph-65/summary.json)
records fixture hashes, versions, timing, decisions and compiled output.
[Per-case evidence](evidence/model-graph-65/cases.jsonl) records the exact fixture
file/line index, source URL, actual output, refusal reason and measured call time.
The original full inputs are tracked under `agent/tests/fixtures/local_inference`.
[Compiled run](evidence/model-graph-65/compiled-run.json) retains actual graph
state, policy/validation outcomes and execution-source audit events. CI uploads
full input/output/audit replay records separately.

## Safety and integration results

- `ModelGateway` validates result shapes, taxonomy, probability ranges, finite
  scores, exact candidate identities and incident ownership before graph use.
- NaN/Inf, boolean probabilities, malformed records, invented candidate paths,
  unknown labels and runtime errors refuse suggestions or preserve deterministic
  behavior. Raw exception text is not exposed through model diagnostics.
- Classifier merge cannot replace deterministic blocks, introduce unknown/healthy
  fix classifications or use invalid confidence values.
- Trace baseline selection now happens after scoped catalog retrieval. Only a
  verified healthy row with matching company/client/service/environment/operation/
  repository and valid latency/status can supply a baseline. Missing and unsuitable
  baselines are explicit output states; caller-supplied comparison records cannot
  grant baseline authority. Missing-baseline execution can abstain.
- Patch suggestions reach the existing private handoff only for concrete approved
  generator families and with `requires_sandbox_validation=true`. Provenance,
  allowlists, reproduction, Secret-coverage, policy and sandbox validation remain
  authoritative. An unsupported suggestion is an auditable refusal, not a new
  template or a successful repair.
- Audit records distinguish trained inference, deterministic override, abstention,
  disabled runtime and unavailable fallback. A separate `learned_execution` flag
  records whether estimator work occurred even when a rule/refusal determined
  the effective answer.
- Existing adversarial non-abstaining stub tests remain in place for blocked
  classifier and patch paths; those tests assert zero prohibited model/proposal
  calls. New real-artifact tests establish actual execution separately.

Local verification: **600 agent tests passed, 4 optional integrations skipped**.
The changed gateway/output boundary has **97% statement coverage** (gateway 98%,
output validation 95%). Workflow/security/evaluation/wire checks: **58 passed**.
Strict mypy passes for the new output validator and measurement harness; new
files pass Black and Ruff. Hosted and live-kind outcomes are recorded below
once the candidate run completes.

## Hosted environment proof

The opt-in `e2e/run_model_graph_kind.py` reuses the existing owned-cluster runner.
It commits the controlled probe fixture, starts real dispatch and pinned Ignis,
authenticates a fictional fixture tenant, calls the real catalog adapter over
HTTP, checks all five model result slots, verifies a real unhealthy-to-Ready
repair and sandbox validation, and deletes only its owned namespace. Models
remain disabled in the other normal E2E cases. No AgentHooks/prediction override
is installed, and no GitHub publication credentials are supplied.

**Hosted result: pending the PR run.** This line must be replaced with the actual
run/revision and observed result before treating this document as completed live
proof. A valid live-kind pass does not turn fixture trace input into real APM data,
and its rule-selected probe patch does not establish learned patch accuracy.

## Reproduce

```bash
python -m pip install --require-hashes -r requirements-bootstrap.txt
python -m pip install 'setuptools>=68' wheel
python -m pip install -e './agent[local-inference]' -e ./dispatch
python -m pytest -q agent/tests/test_model_graph_qualification.py \
  agent/tests/test_model_gateway.py agent/tests/test_blocked_model_boundary.py \
  agent/tests/test_graph_localization.py agent/tests/test_image_provenance.py
python agent/scripts/qualify_model_graph.py --output /tmp/model-graph-proof
```

Full verification uses `python -m pytest -q agent/tests` and the dispatch suite,
plus the repository's workflow/evaluation/wire unittests. Run the live-kind script
only through the configured disposable hosted job with its pinned Ignis build,
fixture set, owned context and cleanup. These results do not enable a pilot,
change production resources, alter public sandbox contracts or qualify BYOK.
