# Raphael issue #40: local inference resolution

> **Release status — 2026-10-20:** [PR #59](https://github.com/AWaleed-Ahmed/Raphael/pull/59)
> merged at `e9a3c66`. The default-off deferral below is shipped; the trained
> inference runtime remains unavailable. #40 is still open. Refer to the
> [canonical guide](pilot-install.md) for the selected release pair.


## Outcome

**Chosen path: explicit deferral.** Local inference is disabled by default with `RAPHAEL_MODEL_ENABLED=0`. Deterministic diagnosis, localization ranking, patch policy, and sandbox validation remain the active path. Setting `RAPHAEL_MODEL_ENABLED=1` is non-fatal; attempted calls in a clean checkout/package report that the prediction runtime is not packaged. This does not claim trained inference.

Reviewed/tested base commit: `0dc46c47b976a42dd958ad4d8e56dcfaf8b154ab` (current `origin/main`), plus the issue #40 changes on `codex/local-inference-deferral`. The initial audit used `86017638001c62c0710deacb2eb7bd675d094cff`; review moved only the issue #40 changes to a separate worktree and preserved unrelated user work. Issue #40 was fetched successfully during review after retrying network access outside the sandbox; it remains open. Its wire-or-defer decision is resolved here using the explicit deferral authorized by this task.

## Root cause and audit

`agent/raphael_agent/model_gateway.py` resolves `raphael/model/predict.py` relative to the repository and dynamically imports it after mutating `sys.path`. `raphael/` is ignored wholesale (`.gitignore: /raphael/`), so this runtime is present in this developer checkout but absent from a fresh clone and installed package. The sibling `common.py` and `rules.py` imports have the same packaging dependency. This also makes execution depend on repository-relative files, contrary to the packaged-runtime requirement.

All five model bundles are tracked at `models/<name>/model.joblib`, with tracked manifests and metrics. They are joblib/pickle artifacts. Manifests identify Python 3.12.3, joblib 1.5.3, NumPy 2.5.2, SciPy 1.18.0, and scikit-learn 1.9.0. `agent/pyproject.toml` currently allows broader versions, so compatibility against those exact versions has not been established. Training metrics describe synthetic data and are not production accuracy evidence.

The local prediction code contains useful preprocessing and policy logic, but a clean-package integration is not currently demonstrated. In particular, incident similarity returns records from the bundled index and does not filter by the caller's `client_id`/`company_id`; enabling it before tenant-scoped retrieval is demonstrated risks returning another tenant's incident data. The patch selector contains deterministic rules and allowlist checks, so its output must be reported separately from learned selection. The trace adapter accepts an optional healthy baseline, but its deployment behavior with absent/unsuitable baselines has not been proven. The classifier has a rule override and confidence/OOD abstention; its final label alone cannot prove a learned result.

## Capability audit

| Capability | Gateway / graph contract | Current execution and limitation |
|---|---|---|
| Failure classification | `classify_failure(state)` maps fingerprint, normalized reason, runtime observation, and bounded evidence to a taxonomy result; graph merges only non-blocked, contract-allowed output. | No packaged inference. Local function can return deterministic rule labels, learned labels, or abstention, so rule overrides must not be counted as learned inference. |
| Fault-candidate ranking | `rank_candidates(state, candidates, comparisons)` preserves candidate records and canonical path/line/symbol IDs while adapting evidence features. | No packaged inference. Deterministic candidate generation/ranking remains active. |
| Incident similarity | `similar_incidents(state, top_k)` passes the incident record and returns similar embedded records. | No packaged inference. Current local retrieval has no client/company scope filtering; do not enable until tenant isolation is implemented and tested. |
| Trace anomaly detection | `trace_anomaly(state)` adapts span sequence, status, error count, latency, and the first available healthy comparison. | No packaged inference. Missing/unsuitable baseline behavior and real model result recording are unverified. |
| Patch-template selection | `select_patch(state)` adapts diagnosis and top candidate; graph only passes an allowlisted selection toward existing patch policy and sandbox validation. | No packaged inference. Current function can use deterministic rule selection before its learned model; neither behavior proves trained inference. Safety policy remains authoritative. |

Graph call sites are `node_evidence` (trace), `node_diagnose` (classifier), `node_localize` (similarity and ranker), and `node_patch` (patch selector). Disabled/unavailable status is now recorded in `model_results` for these capabilities, with trace status also in audit events. Classifier/trace/patch calls remain behind existing blocked-status gates. Blocked-decision tests use non-abstaining adversarial stubs to establish that safety does not depend on model unavailability.

## Tracked artifacts

Manifest artifact identities (SHA-256):

- `failure_classifier`: `c029aca6c4c0ac197b1e26c444fe2883001a46289101b972b3e181502f5b0d80`
- `candidate_ranker`: `036eca89dc9bb450d665dab516096f8012fb31775f6e187af6a05db2e1cd6b47`
- `incident_similarity`: `38115467e972fd9498637e33b5a9cfab3f6e08029af8d09f34bb5b707bc45a41`
- `trace_anomaly`: `b946fabc97bb703b4449595126f2c29872e1a6319559fd2de4410f75c8415020`
- `patch_selector`: `ed7a9ed3f9713b64bf102e54e734b445b3b6be3e12df8fede4101f6f15741c49`

Artifact location is configured through `RAPHAEL_MODEL_ROOT`; the current default points to repository `models/`. This documents storage only and does not imply runtime availability. No artifacts were loaded as part of this deferral proof.

## Safety and verification

- `RAPHAEL_MODEL_ENABLED` now defaults to `0`.
- Explicit enablement of the absent runtime returns unavailable and records a bounded reason; it does not crash deterministic execution.
- Blocked decisions remain final; the existing adversarial non-abstaining model stubs stay in the safety tests.
- Model confidence cannot bypass diagnosis evidence, patch allowlists, sandbox validation, or human review. Automatic merge and production mutation remain prohibited.
- Full agent suite: **461 passed, 4 existing skips**. This includes the focused model gateway, adversarial blocked-boundary, graph localization/phase 2, image-provenance, and escalation-reason checks. Dispatch: **88 passed**. Evaluator unit tests: **10 passed**. The initial sandboxed suite stalled at the Alertmanager TestClient test; running outside the sandbox completed in 5.37 seconds.
- The unavailable-runtime regression now explicitly points `MODEL_SCRIPT` at a nonexistent temporary file for all five capabilities. It cannot accidentally execute an ignored developer runtime. Graph regressions verify disabled trace, similarity, and candidate-ranker audit status while preserving deterministic candidates.
- A wheel was built and installed with `pip --no-deps --no-build-isolation --target /tmp/raphael-issue40-installed-final`, using the existing Debian system build tools through `PYTHONPATH=/usr/lib/python3/dist-packages`. No model dependencies or artifacts were loaded for this deferral check. From `/tmp`, import provenance confirmed the installed copy; default configuration returned `enabled=false`, `output=null`, and `reason=disabled_by_environment`. With explicit enablement, **all five capabilities** returned `output=null` and `reason=predict_script_missing:raphael/model/predict.py is not packaged`. This verifies installed fallback behavior; trained inference remains deferred.
- No real artifact inference was claimed or used. Therefore cold start, warm latency, peak memory, real graph inference, and inference resource measurements are **not applicable / not measured** on the deferral path.

## Reproduce the deferral verification

Run in the reviewed checkout, using a Python 3.12 environment with the existing
agent/dispatch test dependencies. `RAPHAEL_REVIEW_PYTHON` must be an absolute
interpreter path because the checks change working directories. The review used
`/home/home/Documents/work/Projects/Raphael/agent/.venv/bin/python`.

```bash
export RAPHAEL_REVIEW_PYTHON=/absolute/path/to/python3.12
(cd agent && PYTHONPATH=../dispatch "$RAPHAEL_REVIEW_PYTHON" -m pytest -q)
(cd dispatch && PYTHONPATH=../agent "$RAPHAEL_REVIEW_PYTHON" -m pytest -q)
(cd agent && "$RAPHAEL_REVIEW_PYTHON" -m pytest -q ../evals/test_run_evals.py)
PYTHONPATH=/usr/lib/python3/dist-packages "$RAPHAEL_REVIEW_PYTHON" -m pip install --no-deps --no-build-isolation --no-cache-dir --target /tmp/raphael-issue40-installed-final ./agent
(cd /tmp && PYTHONPATH=/tmp/raphael-issue40-installed-final "$RAPHAEL_REVIEW_PYTHON" - <<'PYCODE'
import os
import raphael_agent.model_gateway as module
from raphael_agent.model_gateway import ModelGateway, model_error
assert module.__file__.startswith('/tmp/raphael-issue40-installed-final/')
os.environ.pop('RAPHAEL_MODEL_ENABLED', None)
gateway = ModelGateway()
assert not gateway.enabled
assert gateway.classify_failure({}) is None
assert model_error(gateway) == 'disabled_by_environment'
os.environ['RAPHAEL_MODEL_ENABLED'] = '1'
for name in ('classify_failure', 'trace_anomaly', 'similar_incidents', 'rank_candidates', 'select_patch'):
    gateway = ModelGateway()
    result = (gateway.rank_candidates({}, [{'path': 'src/app.py', 'line': 1}], [])
              if name == 'rank_candidates' else getattr(gateway, name)({}))
    assert result is None
    assert model_error(gateway) == 'predict_script_missing:raphael/model/predict.py is not packaged'
PYCODE
)
```

Use a fresh target directory for each staged install. The build-tool path above
is specific to the Debian review host; other environments can provide
`setuptools` and `wheel` through their normal Python build environment. The
TestClient suites require an execution environment where local async/thread
operations are supported; the review ran those suites outside the sandbox.

## Bounded follow-up and acceptance

Revisit implementation only after all of these are completed:

1. Move only inference-time preprocessing/rules/prediction code into the tracked `raphael_agent` package; leave training scripts and datasets ignored/separate. Remove `sys.path` and repository-relative runtime imports.
2. Pin or explicitly validate artifact-compatible Python/library versions and verify the tracked artifacts by manifest hash before loading trusted deployment artifacts. Never load customer-provided joblib files. Honor `RAPHAEL_MODEL_ROOT` from an explicit, documented artifact layout.
3. Add tenant/company filtering to similarity records and prove wrong-scope rows are never returned.
4. Through the production gateway and actual graph, prove learned execution, rule override, abstention, and fallback separately for all five capabilities; include canonical candidate IDs, trace baseline gaps, classifier taxonomy, and approved patch-template boundaries.
5. Run outside the repository and from a clean staged install excluding ignored files. Measure cold start, warm prediction latency, artifact size, and peak memory using a reproducible method. Do not infer accuracy from synthetic metrics.
6. Re-run blocked-model, image-pull, graph safety, agent, and affected evaluator regressions. Keep non-abstaining adversarial stubs and deterministic safety gates.

Suggested commands after the tracked runtime exists:

```bash
(cd agent && python -m pytest -q tests/test_model_gateway.py tests/test_blocked_model_boundary.py)
(cd agent && python -m pytest -q tests/test_graph_localization.py tests/test_graph_phase2.py tests/test_image_provenance.py)
(cd agent && python -m pytest -q)
python -m pip install --no-deps --target /tmp/raphael-agent-stage ./agent
(cd /tmp && PYTHONPATH=/tmp/raphael-agent-stage RAPHAEL_MODEL_ENABLED=1 RAPHAEL_MODEL_ROOT=/path/to/tracked/models python -c 'from raphael_agent.model_gateway import ModelGateway; print(ModelGateway().classify_failure({}))')
```

The final command is a future acceptance check, not a result claimed here. A deployment that passes every gate above may change the default only after all five capabilities and tenant boundaries have reproducible proof.
