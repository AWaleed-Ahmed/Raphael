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

- Base revision: `3cef7b3a7bdc340d47aef77b0fce2294cfdbdad4` (merged #63/#64 prerequisites).
- Exact candidate source is the implementation commit on the associated PR;
  CI artifacts identify the tested PR merge revision. The committed local
  replay was collected from the candidate working tree on that base.
- Local platform: `Linux-7.0.0-38-generic-x86_64-with-glibc2.39`; Python `3.12.3`.
- Qualified libraries: joblib 1.6.0, NumPy 2.5.2, SciPy 1.18.1, scikit-learn 1.9.0.
- Local Docker daemon was unavailable. Live Kubernetes evidence must come from
  the disposable hosted run; local replay is not presented as live cluster proof.
- Peak RSS of the complete standalone qualification process: **189.5 MiB**.
  This includes imports, all fixture replays, cached bundles and the compiled
  graph; it is not isolated estimator memory or evidence of a 512 MiB deployment fit.

## Accuracy, coverage and decision source

| Capability | Fixture result and limits | Learned / rule paths | Warm median / p95 |
| --- | --- | --- | --- |
| Failure classification | 40/40 emitted classifications match (100%); 40/50 overall (80%); 10 image-policy stops | 40 / 40 | 1.90 / 2.75 ms |
| Candidate ranking | 37/50 top-1 fix-file matches (74%); gateway projection of benchmark candidates | 50 / 0 | 1.77 / 2.06 ms |
| Incident similarity | 44/50 top-1 class matches (88%); queries overlap the owned fixture index | 50 / 0 | 5.16 / 6.41 ms |
| Trace anomaly | 38/50 fault-window matches (76%); weak per-trace labels | 50 / 15 | 3.80 / 4.27 ms |
| Patch selection | 12/50 safe-template hypothesis matches (24%); 41/51 outputs, 22 refusals; not repair accuracy | 1 / 40 | 1.17 / 1.38 ms |

Execution counts use raw `learned_execution` and `rule_based` flags. A rule
path can subsequently be refused by the graph, so rule-path and refusal counts
overlap. Effective answer sources are recorded separately in outputs and audits.

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
These heterogeneous timings are not an estimator speed comparison. The latency
distribution includes policy stops and refusals as well as emitted predictions;
it is not a prediction-only latency distribution.

The p95 is the nearest-rank observation at `ceil(0.95 * n)`. There are no latency
acceptance thresholds, repeated-run confidence intervals, network-to-customer
latency estimates or concurrent throughput claims. Timing varies by machine/load.
Compiled graph elapsed time is **229.957 ms**, with recorded
sandbox responses and a fixture catalog; it is not live repair duration.

The loader cache is cleared before each capability's first explicit load. Those
sequential first-load measurements include validation/deserialization; the first
also pays dependency import cost. They are not five independent process cold starts.

| Bundle | Sequential first-load ms | Approved model SHA-256 |
| --- | ---: | --- |
| failure_classifier | 983.252 | `c029aca6c4c0ac197b1e26c444fe2883001a46289101b972b3e181502f5b0d80` |
| candidate_ranker | 23.476 | `036eca89dc9bb450d665dab516096f8012fb31775f6e187af6a05db2e1cd6b47` |
| incident_similarity | 102.903 | `5fc33e1a21d0e6a600e674ee0a64722e989c491b6e92c602d633f84ef8811644` |
| trace_anomaly | 5.203 | `b946fabc97bb703b4449595126f2c29872e1a6319559fd2de4410f75c8415020` |
| patch_selector | 56.517 | `ed7a9ed3f9713b64bf102e54e734b445b3b6be3e12df8fede4101f6f15741c49` |

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

Local verification: **601 agent tests passed, 4 optional integrations skipped**.
The changed gateway/output boundary has **97% statement coverage** (gateway 98%,
output validation 95%). Workflow/security/evaluation/wire checks: **58 passed**.
Strict mypy passes for the new output validator and measurement harness; new
files pass Black and Ruff. Hosted and live-kind outcomes are recorded below with their exact tested revisions.

## Hosted environment proof

The opt-in `e2e/run_model_graph_kind.py` reuses the existing owned-cluster runner.
It commits the controlled probe fixture, starts real dispatch and pinned Ignis,
authenticates a fictional fixture tenant, calls the real catalog adapter over
HTTP, checks all five model result slots, verifies a real unhealthy-to-Ready
repair and sandbox validation, and deletes only its owned namespace. Models
remain disabled in the other normal E2E cases. No AgentHooks/prediction override
is installed, and no GitHub publication credentials are supplied.

**Hosted result: passed.** All seven checks passed for implementation commit
`3cef7b3` / tested PR merge revision `bb2ccd2f9d714efdf61f3ff8d94f6a11761cf2f9`.
The later finalization adds a non-JSON output refusal/control and documentation;
current-head CI is linked on [PR #77](https://github.com/AWaleed-Ahmed/Raphael/pull/77).

- [Core CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40354545306)
  ran the public replay and compiled graph on Python 3.12.15 / `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39`.
  Every execution, coverage and label-match count agreed with the local report.
  This initial hosted run passed 600 agent tests (4 skips); the additional strict
  JSON metadata control brings final local verification to 601 passing tests.
- [Integration CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40354545955)
  passed revision resolution, mock-backend/dispatch, real-kind remediation and
  Secret fixture propagation. It ran the new model-enabled proof successfully.
- [Live proof artifact](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/40354545955/artifacts/12665523524)
  includes real HTTP traces, runner state, actual Pod snapshots and cleanup proof.
  The compact [committed live proof](evidence/model-graph-65/hosted-kind-proof.json)
  retains actual model outputs and validation results. [Hosted replay summary](evidence/model-graph-65/hosted-summary.json)
  retains independent timing and resource measurements.

The controlled fixture commit was `73cb12a5475ca2fa277609c1e2c8ed4a4b7610f7`, on
Kubernetes **v1.35.0**, using a real `hashicorp/http-echo:1.0` Pod. The observed
readiness probe port was 9090 while the application listened on 8080. Production
hooks generated the bounded probe repair, the Pod became Ready, and the run
finished `fix_finalized` after **7.010 seconds**. This is one controlled
repair measurement, not a throughput or general incident-repair latency estimate.

| Live capability | Actual effective source | Learned computation | Important limit |
| --- | --- | --- | --- |
| Failure classifier | Deterministic rule override | Yes | The learned label did not control the final classification |
| Candidate ranker | Trained inference | Yes | Canonical graph-generated candidates retained source evidence |
| Incident similarity | Trained retrieval, empty results | Yes | No matching incident; positive retrieval is covered by public fixtures/#64 |
| Trace anomaly | Abstention, baseline missing | Yes | This Kubernetes probe supplied no APM trace or usable healthy latency |
| Patch selector | Deterministic rule override | No | Learned template execution is proved separately by the real Fission node replay |

Mandatory rollout and signature-comparison checks **passed**, the original
`probe_port_mismatch:payments-api:8080!=9090` signature cleared, and Ready was
independently observed. The sandbox explicitly returned **`full_validation=false`**:
a nonmandatory fidelity check failed because production Secret values were not
present. This is a successful bounded synthetic-fixture repair, not full
production-fidelity validation or an authorization to enable inference.

Hosted process peak RSS was **188.6 MiB**, and the recorded-response compiled graph
took **126.147 ms**. Different machines/environments produced different timings and memory
measurements; neither run establishes a container memory limit or production SLA.
The hosted warm timings below use the same heterogeneous node/adapter timer
boundaries described above:

| Capability | Hosted warm median / p95 ms | Hosted sequential first-load ms |
| --- | ---: | ---: |
| Failure classification | 1.090 / 1.468 | 614.312 |
| Candidate ranking | 1.003 / 1.115 | 13.004 |
| Incident similarity | 3.163 / 3.521 | 57.874 |
| Trace anomaly | 2.087 / 2.172 | 3.150 |
| Patch selection | 0.662 / 0.694 | 30.261 |

No APM trace accuracy or learned-only patch success is inferred from the live
probe control. Default-off, tenant binding, sandbox policy, dry-run publication
and owned-resource cleanup all remain in force.

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
