# Public repository sandbox lifecycle tests

## Purpose

On 2026-08-17, Raphael was exercised against ten real public GitHub repositories selected from the public failure records used by the external evaluation. The repositories were checked out at the exact public default-branch commit listed below. No synthetic repository or generated failure was used.

The controller was running locally at `http://127.0.0.1:8090` with the `mock` cluster backend. This exercises Raphael's API lifecycle, clone-at-SHA path, manifest rendering, deterministic signature analysis, validation policy, result finalization, and cleanup. It does **not** claim production-equivalent Kubernetes behavior.

## Lifecycle exercised

For every repository with a deployable manifest, the runner attempted:

1. `POST /v1/sandboxes` with the public clone URL and commit SHA.
2. `POST /v1/sandboxes/{id}/deploy` to clone the repository at that SHA and render the selected YAML or Helm input.
3. `POST /v1/sandboxes/{id}/observe` to obtain the failure signature.
4. `POST /v1/sandboxes/{id}/validate` with an allowlisted `true` command and mandatory `signature_absent` comparison.
5. `POST /v1/sandboxes/{id}/finalize` only when validation passed.
6. `POST /v1/sandboxes/{id}/destroy` in every case where a sandbox was created.

For a healthy public snapshot, validation compares `healthy` to `healthy`; this verifies the lifecycle path but is not a code fix. For a reproduced failure, validation correctly remains blocked until a separate candidate intervention changes the signature.

## Results

| # | Public repository | Commit SHA | Real deployment input | Sandbox | Result | Observed fingerprint / blocker |
|---:|---|---|---|---|---|---|
| 1 | [volcano-sh/dashboard](https://github.com/volcano-sh/dashboard) | `2d6be1818c1fedc2e621c6632e272fc066ae6e1d` | YAML `deployment/volcano-dashboard.yaml` | `sb-9e71505ef59d` | Lifecycle finalized | `healthy`; reproduced `false` |
| 2 | [anuragvishwa/kgroot-test-app](https://github.com/anuragvishwa/kgroot-test-app) | `efad08bdabbabf95322b5cf0caf54b26e0e9bb7a` | YAML directory `kubernetes/` | `sb-ba31485a8661` | Validation blocked | `service_port_mismatch:payment-service:8081`; confidence `0.90`; `TargetPortMismatch`; container ports `[8080, 8080, 8080, 5432, 6379]`, target port `8081` |
| 3 | [jenkinsci/kubernetes-plugin](https://github.com/jenkinsci/kubernetes-plugin) | `52f3080db8cd2e14914903715187116169355493` | YAML `src/main/kubernetes/jenkins.yml` | `sb-3037f240fc81` | Lifecycle finalized | `healthy`; reproduced `false` |
| 4 | [awslabs/benchmark-ai](https://github.com/awslabs/benchmark-ai) | `c698d93541edbd5a455f7ae1fdee89a00c548921` | YAML directory `executor/deploy/base/` | `sb-c8a9cd8d2e57` | Validation blocked | `missing_configmap_key:outputs-infrastructure:availability_zones`; confidence `0.95`; `CreateContainerConfigError`; executor pending |
| 5 | [NVIDIA/nodewright](https://github.com/NVIDIA/nodewright) | `3c13b4a58292870dde185457ad85e7a58cf603bd` | Helm chart `chart/`, release `nodewright` | `sb-d0c7aec246d7` | Deployment rejected | Helm renderer rejected a template that deploys to the forbidden `default` namespace: `nodewright/templates/validations.yaml` |
| 6 | [canonical/microk8s](https://github.com/canonical/microk8s) | `d099c907d3646a2dae3d3e33f07aef5a5bc8a090` | YAML `tests/templates/simple-deploy.yaml` | `sb-fed37e917d5d` | Lifecycle finalized | `healthy`; reproduced `false`; image `nginx:1.14.2` |
| 7 | [gpustack/gpustack](https://github.com/gpustack/gpustack) | `9b15b7e2a92913208155c71f6f3bb49a46ffeed9` | Helm chart `charts/gpustack-chart/`, release `gpustack` | `sb-38f91f0a3721` | Deployment rejected | Helm dependencies were not vendored: `higress-core` was declared in `Chart.yaml` but missing from `charts/` |
| 8 | [docker-hardened-images/catalog](https://github.com/docker-hardened-images/catalog) | `d7a252e4b76dccc1f9a9d34ffcd5f74aae55c3cd` | YAML `chart/alertmanager/helm/1.yaml` | `sb-554ed9b75b80` | Lifecycle finalized | `healthy`; reproduced `false` |
| 9 | [muramasa-git/pagerduty-repo-test](https://github.com/muramasa-git/pagerduty-repo-test) | `3b092fa4988d0e7d731a448b6c39a4e6a68fd652` | None found in repository tree | None | Not reproducible | No deployable Kubernetes YAML, Helm chart, or Kustomize overlay was available |
| 10 | [aboigues/k8t](https://github.com/aboigues/k8t) | `d974012e60a3413adeb998375144275491b5dd15` | YAML `tests/manual/manifests/05-test-success.yaml` | `sb-81d2561c8081` | Lifecycle finalized | `healthy`; reproduced `false`; image `nginx:latest` |

## Aggregate outcome

- 10 real repositories inspected.
- 9 repositories had a deployment input selected from their public tree.
- 5 complete lifecycles reached finalization: cases 1, 3, 6, 8, and 10.
- 2 real failures were reproduced and validation correctly failed closed: cases 2 and 4.
- 2 deployments were correctly rejected before observation: cases 5 and 7.
- 1 repository had no deployable manifest: case 9.
- Every created sandbox was explicitly destroyed. The mock backend reported fidelity score `0.8333333333333334` for successful deployments, with these material gaps:
  - mock cluster backend is not the customer's API server;
  - image tags were not resolved to immutable digests.
- No source patch or PR was generated. The public snapshots did not provide a last-known-good revision plus an authorized repository target for a safe intervention. This is expected fail-closed behavior, not a fabricated success.

## Additional rerun bookkeeping

Cases 5–10 were also rerun with compact output while collecting the complete report. Those reruns produced the following additional sandbox IDs and were destroyed as well:

- Nodewright: `sb-0cf583e9d42f`
- MicroK8s: `sb-7047dc5095b4`
- GPUStack: `sb-78028fdcb32f`
- Docker Hardened Images: `sb-ac1c9e28282b`
- k8t: `sb-0f61f0e1fe70`

Other historical sandbox records may exist in the controller data directory; they were not part of this test and are intentionally not removed by the cleanup.

## Interpretation

The run proves that Raphael can consume real public repository revisions, render real deployment inputs, produce deterministic Kubernetes failure signatures, block unsafe or incomplete deployments, validate healthy snapshots, finalize result records, and destroy sandboxes. It does not yet prove customer-equivalent runtime behavior because the run used the mock backend and did not perform a real source intervention. The next production-grade test should use `RAPHAEL_CLUSTER_BACKEND=kind` or a customer's isolated cluster, provide the failing and last-good SHAs, and supply a concrete patch candidate so the revert/redeploy/replay/repeatability path is exercised.


## Model layer: inputs, outputs, and relationship to this run

Raphael has five lightweight CPU model artifacts under `models/`. The graph adapters are implemented in `agent/raphael_agent/model_gateway.py`. They are advisory: deterministic fingerprint rules, candidate evidence scoring, policy rules, and sandbox validation remain authoritative.

The ten-repository controller runner above exercised the sandbox controller directly. It did not run the complete Python LangGraph graph, so it did not automatically populate `run_record.model_results` for every repository. To make model behavior concrete, the observed signatures from the seven repositories that reached `observe` were then passed through the trained local inference functions. Those model calls used the real fingerprints/evidence produced by the run; cases rejected before rendering and the no-manifest case have no runtime model input.
The mock controller did not emit real OpenTelemetry spans or application latency. For the standalone model replay, failure observations were normalized into the adapter contract (for example, `status_code=500` and `span_error_count=1` for the two explicit Kubernetes failures) so the model’s explicit-error rule could be inspected. These are derived failure signals, not claims that a real customer trace was collected.

### Model pipeline in a normal agent run

| Graph step | Model | Input assembled by the adapter | Output | Safety use |
|---|---|---|---|---|
| Evidence | `trace_anomaly` | `service_name`, operation/route, span sequence, latency, error-span count, status code, and optional healthy-trace baseline fields | `is_anomaly`, `abstained`, probability, threshold, rule evidence | Detects silent/trace failures; explicit error spans and HTTP errors override the learned score |
| Diagnosis | `failure_classifier` | Fingerprint, normalized reason, service, environment, evidence text, span-error count, stack-present flag, trace-present flag | Failure class, confidence, alternatives, abstention state, rule evidence | Exact Kubernetes reasons/fingerprint prefixes take precedence over the classifier |
| Localization | `incident_similarity` | The same provider-neutral failure record | Top historical incidents with similarity, prior fix template, and sandbox result | Supplies historical context; it does not prove causality |
| Localization | `candidate_ranker` | Deterministically generated candidate path/symbol/type plus runtime anchor, stack, trace, changed-file, log, compatibility, historical-similarity, and dependency features | Candidates with learned score, evidence score, and combined model score | Candidates must already be generated from real source evidence; scores are not compared across incidents |
| Patch | `patch_selector` | Failure class, normalized reason, manifest field, candidate type/path, and source/image requirement flags | Policy decision, safe template, template confidence, alternatives, `requires_sandbox_validation` | Hard-deny rules and sandbox validation always win; no model output directly changes customer code |

### Model artifacts and quality results

| Artifact | Implementation | Local holdout result | External/public benchmark result |
|---|---|---:|---:|
| `failure_classifier` | TF-IDF plus logistic regression with abstention | Macro F1 `0.9933` | `50/50` accuracy, coverage `1.0` |
| `candidate_ranker` | Character TF-IDF plus numeric evidence and logistic score | Recall@1 `1.0000` | Recall@1 `0.76`, Recall@3 `0.90`, MRR `0.8497` |
| `incident_similarity` | Sparse word/character TF-IDF retrieval | Class Recall@1 `1.0000` | Top-1/top-3 `0.96` (`48/50`) |
| `patch_selector` | Conservative policy classifier plus allowlisted templates and hard denies | Policy Macro F1 `1.0000`; safe-template Recall@3 `1.0000` | Acceptable template `47/50` (`0.94`); policy allowed `50/50` |
| `trace_anomaly` | Span n-grams plus numeric trace features and baseline rules | Macro F1 `1.0000` | Broad fault-window accuracy `0.76`; observable-signal accuracy `0.94` |

These are evaluation measurements, not guarantees of customer accuracy. The model artifacts were trained from local datasets and must abstain or defer when evidence is outside their supported taxonomy.

## Per-repository model dry run

### 1. Volcano Dashboard

The controller produced this model input:

```json
{
  "fingerprint": "healthy",
  "normalized_reason": "Healthy",
  "service_name": "volcano-dashboard",
  "evidence_text": "all containers ready",
  "span_error_count": 0,
  "stack_present": false,
  "trace_present": false
}
```

The trace adapter also received an empty span sequence, status `200`, and no healthy baseline. It returned `is_anomaly=false`, probability `0.026292`, and `abstained=true` because a silent-failure decision requires an explicit signal or baseline.

The failure classifier returned `abstained=true` because `Healthy`/`healthy` is outside its failure taxonomy. Its raw top class was `bad_image_reference` at `0.827268`, but that incidental prediction was discarded. Incident similarity returned no result above its `0.2` minimum. Patch selection returned `policy_allowed=false` with `out_of_distribution`. Candidate ranking was not run because this controller-only case generated no source candidates.

### 2. kgroot test app

The model input was:

```json
{
  "fingerprint": "service_port_mismatch:payment-service:8081",
  "normalized_reason": "TargetPortMismatch",
  "service_name": "payment-service",
  "evidence_text": "service targetPort 8081 does not match container ports ConnectionRefused: service targetPort mismatch",
  "span_error_count": 1,
  "stack_present": false,
  "trace_present": false
}
```

The trace adapter returned `is_anomaly=true`, probability `0.993241`, with rule evidence `explicit_error_span_or_status`.

The failure classifier's learned top class was incorrectly `bad_image_reference` at `0.742042`, but deterministic evidence recognized the phrase and returned the correct final class `service_port_mismatch` with `rule_based=true`.

Incident similarity returned three historical service-port incidents with similarities `0.266545`, `0.261891`, and `0.252286`. Their templates included `align_container_port`, `fix_service_target_port`, and `update_ingress_backend_port`.

Patch selection received `failure_class=service_port_mismatch`, `candidate_type=kubernetes_manifest`, and `manifest_field=targetPort`. It returned:

```json
{
  "policy_allowed": true,
  "safe_template": "fix_service_target_port",
  "template_confidence": 0.99,
  "allowed_probability": 0.99,
  "requires_sandbox_validation": true
}
```

The actual sandbox run did not apply this template, so the observed signature remained unchanged and validation correctly failed.

### 3. Jenkins Kubernetes plugin

The controller record was a healthy observation with service `jenkins`, status `200`, no errors, no stack, and no spans. The model outputs were:

- Trace anomaly: `is_anomaly=false`, probability `0.026292`, `abstained=true`.
- Failure classifier: `abstained=true`; raw top class `bad_image_reference` at `0.827268` was discarded.
- Incident similarity: no result above `0.2`.
- Patch selector: `policy_allowed=false`, `out_of_distribution`.
- Candidate ranker: not invoked because no deterministic source candidates were created by this runner.

The sandbox lifecycle finalized because the observed signature was already healthy.

### 4. AWS Benchmark AI

The model input was:

```json
{
  "fingerprint": "missing_configmap_key:outputs-infrastructure:availability_zones",
  "normalized_reason": "CreateContainerConfigError",
  "service_name": "executor",
  "evidence_text": "configmap outputs-infrastructure missing key availability_zones Failed: Error: configmap key not found",
  "span_error_count": 1,
  "stack_present": false,
  "trace_present": false
}
```

Trace anomaly returned `is_anomaly=true`, probability `0.993241`, using explicit error/status evidence.

The failure classifier returned `invalid_missing_config` at `0.747914`, with deterministic rule evidence `normalized_reason:CreateContainerConfigError`.

Incident similarity returned three missing-configuration incidents with similarities `0.545231`, `0.520193`, and `0.50856`. Their historical templates included `revert_configmap_entry`, `correct_env_var_type`, and another `revert_configmap_entry`.

Patch selection received `failure_class=invalid_missing_config`, `candidate_type=kubernetes_manifest`, and `manifest_field=configMapKey`. It returned:

```json
{
  "policy_allowed": true,
  "safe_template": "restore_configmap_key",
  "template_confidence": 0.99,
  "allowed_probability": 0.99,
  "requires_sandbox_validation": true
}
```

The public run did not apply a patch. The unchanged signature caused validation to fail closed.

### 5. NVIDIA Nodewright

Helm failed during rendering because the chart used the forbidden `default` namespace. Since no manifest was rendered:

- No runtime observation existed.
- No failure-record model input existed.
- No trace anomaly, classifier, similarity, ranker, or patch-selector prediction was made.
- The policy error stopped the lifecycle before model inference.

### 6. Canonical MicroK8s

The selected Nginx manifest produced a healthy observation with no errors or spans. Model outputs:

- Trace anomaly: `false`, probability `0.026292`, abstained.
- Failure classifier: abstained; raw top class `bad_image_reference` was rejected as out-of-distribution.
- Incident similarity: empty result set.
- Patch selector: blocked as out-of-distribution.
- Candidate ranker: not invoked.

The sandbox lifecycle finalized because no failure signature was present.

### 7. GPUStack

Helm failed because the declared `higress-core` dependency was absent from the chart's `charts/` directory. No rendered workload existed, so no runtime model input or output was produced. Helm dependency validation was authoritative and the sandbox was destroyed after the deploy rejection.

### 8. Docker Hardened Images catalog

The selected Alertmanager YAML produced a healthy observation. Model behavior:

- Trace anomaly: `false`, probability `0.026292`, abstained.
- Failure classifier: abstained; raw top class was discarded.
- Incident similarity: no result above threshold.
- Patch selector: out-of-distribution and blocked.
- Candidate ranker: not invoked because no source-candidate set was produced.

The healthy lifecycle was finalized and the sandbox destroyed.

### 9. PagerDuty repository test

No deployable Kubernetes, Helm, or Kustomize input was found. The pipeline stopped during manifest discovery, before sandbox creation. All five models were therefore not applicable.

### 10. k8t

The selected public success manifest produced a healthy observation. Model behavior:

- Trace anomaly: `false`, probability `0.026292`, abstained.
- Failure classifier: abstained because healthy is not a failure class.
- Incident similarity: empty result set.
- Patch selector: blocked as out-of-distribution.
- Candidate ranker: not invoked.

The lifecycle finalized as healthy and the sandbox was destroyed.

## Important conclusion about model outputs

The two reproduced failures demonstrate the intended hybrid behavior: the learned classifier can be uncertain or wrong on a narrow manifest failure, but deterministic evidence rules correct the final class. The trace model confirms explicit failure signals, similarity supplies prior validated patterns, and the patch selector proposes only bounded templates that still require sandbox validation.

The healthy repositories correctly caused the models to abstain rather than invent a failure or patch. The render-blocked and no-manifest repositories correctly produced no model input at all. This is safer than manufacturing predictions for data that never reached runtime observation.


## Detailed repository lifecycle dry run

The following is the exact state transition for each repository. “Finalize” means Raphael persisted a result record; it does not mean a source change was applied. For failure cases, the unchanged fingerprint deliberately prevented finalization.

### 1. Volcano Dashboard

1. GitHub metadata identified the `main` branch and commit `2d6be1818c1fedc2e621c6632e272fc066ae6e1d`.
2. Tree inspection selected `deployment/volcano-dashboard.yaml`.
3. Sandbox `sb-9e71505ef59d` and namespace `raphael-run-public-1...` were created.
4. The controller cloned the repository at the exact SHA.
5. YAML rendering found a Deployment, ServiceAccount, ClusterRoleBinding, ClusterRole, and Service. It extracted image `volcanosh/volcano-dashboard:latest`.
6. Mock deployment returned `status=deployed` and fidelity score `0.8333333333333334`.
7. Observation returned `healthy`, confidence `0.8`, evidence `demo-0 phase=Running`, and `reproduced=false`.
8. Validation ran `true` and compared `healthy` to `healthy`; it passed.
9. Finalization created a result record and content hash.
10. The sandbox namespace and resources were destroyed.

### 2. kgroot test app

1. GitHub metadata identified commit `efad08bdabbabf95322b5cf0caf54b26e0e9bb7a`.
2. Tree inspection selected the real `kubernetes/` directory.
3. Sandbox `sb-ba31485a8661` was created.
4. The controller cloned the repository at that SHA.
5. YAML rendering loaded the API, CPU, notification, order, payment, Postgres, Redis, and worker resources.
6. The deterministic analyzer compared Service target ports with container ports and found payment-service target port `8081` while the available container ports included `8080`.
7. Observation returned `service_port_mismatch:payment-service:8081`, confidence `0.90`, reason `TargetPortMismatch`, and `reproduced=true`.
8. Validation ran without an intervention. The before and after keys were identical, so mandatory `signature_absent` failed.
9. Finalization was refused; Raphael did not claim a fix.
10. The sandbox was destroyed.

### 3. Jenkins Kubernetes plugin

1. GitHub metadata identified commit `52f3080db8cd2e14914903715187116169355493`.
2. Tree inspection selected `src/main/kubernetes/jenkins.yml`.
3. Sandbox `sb-3037f240fc81` was created.
4. The repository was cloned at the exact SHA.
5. The Jenkins YAML rendered successfully.
6. Mock deployment returned `deployed`.
7. Observation returned `healthy` with `demo-0 phase=Running` evidence.
8. Validation compared healthy to healthy and passed.
9. The run was finalized.
10. The sandbox was destroyed.

### 4. AWS Benchmark AI

1. GitHub metadata identified commit `c698d93541edbd5a455f7ae1fdee89a00c548921`.
2. Tree inspection selected `executor/deploy/base/`.
3. Sandbox `sb-c8a9cd8d2e57` was created.
4. The repository was cloned at that SHA.
5. Rendering loaded the executor ConfigMap, Deployment, Roles, RoleBindings, and ServiceAccounts.
6. The analyzer found that the executor referenced ConfigMap `outputs-infrastructure` key `availability_zones`, which was absent.
7. Observation returned `missing_configmap_key:outputs-infrastructure:availability_zones`, confidence `0.95`, reason `CreateContainerConfigError`, and an executor pending state.
8. Validation ran without a candidate patch. The same key remained before and after, so validation failed closed.
9. No successful result was finalized.
10. The sandbox was destroyed.

### 5. NVIDIA Nodewright

1. GitHub metadata identified commit `3c13b4a58292870dde185457ad85e7a58cf603bd`.
2. Tree inspection selected the real Helm chart at `chart/`.
3. Sandbox `sb-d0c7aec246d7` was created.
4. The repository was cloned at the exact SHA.
5. Helm lint/template processing began.
6. Helm failed while rendering `nodewright/templates/validations.yaml` because it targeted the forbidden `default` namespace.
7. Raphael’s security policy rejected the deployment before any workload could run.
8. No observation, validation, or finalization was allowed.
9. The sandbox was destroyed.

### 6. Canonical MicroK8s

1. GitHub metadata identified commit `d099c907d3646a2dae3d3e33f07aef5a5bc8a090`.
2. Tree inspection selected `tests/templates/simple-deploy.yaml`.
3. Sandbox `sb-fed37e917d5d` was created.
4. The repository was cloned at that SHA.
5. Rendering found an Nginx Deployment, Service, and Ingress using `nginx:1.14.2`.
6. Mock deployment succeeded.
7. Observation returned `healthy` with `demo-0 phase=Running` evidence.
8. Validation passed because the signature was healthy before and after.
9. The result was finalized.
10. The sandbox was destroyed.

### 7. GPUStack

1. GitHub metadata identified commit `9b15b7e2a92913208155c71f6f3bb49a46ffeed9`.
2. Tree inspection selected `charts/gpustack-chart/`.
3. Sandbox `sb-38f91f0a3721` was created.
4. The repository was cloned at the exact SHA.
5. Helm inspected `Chart.yaml` and found dependency `higress-core`.
6. The dependency was not vendored in the chart’s `charts/` directory.
7. Helm returned a dependency-rendering error.
8. Raphael stopped before deployment observation.
9. No validation or finalization occurred.
10. The sandbox was destroyed.

### 8. Docker Hardened Images catalog

1. GitHub metadata identified commit `d7a252e4b76dccc1f9a9d34ffcd5f74aae55c3cd`.
2. Tree inspection selected `chart/alertmanager/helm/1.yaml`.
3. Sandbox `sb-554ed9b75b80` was created.
4. The large catalog repository was cloned at the exact SHA.
5. The selected Alertmanager YAML rendered successfully.
6. Mock deployment succeeded.
7. Observation returned `healthy` with `demo-0 phase=Running` evidence.
8. Validation passed.
9. Finalization created the result record.
10. The sandbox was destroyed.

### 9. PagerDuty repository test

1. GitHub metadata identified commit `3b092fa4988d0e7d731a448b6c39a4e6a68fd652`.
2. Recursive tree inspection searched for YAML, Helm, and Kustomize inputs.
3. No deployable Kubernetes YAML, Helm chart, or Kustomize overlay was found.
4. Raphael recorded `not_reproducible` at manifest discovery.
5. No sandbox was created, so no clone, deployment, observation, validation, or destruction call was necessary.

### 10. k8t

1. GitHub metadata identified commit `d974012e60a3413adeb998375144275491b5dd15`.
2. Tree inspection selected `tests/manual/manifests/05-test-success.yaml`.
3. Sandbox `sb-81d2561c8081` was created.
4. The repository was cloned at the exact SHA.
5. Rendering found the public success Pod using `nginx:latest`.
6. Mock deployment succeeded.
7. Observation returned `healthy` with `demo-0 phase=Running` evidence.
8. Validation passed.
9. The result was finalized.
10. The sandbox was destroyed.

## What was and was not tested

Tested end to end:

- Public repository metadata and commit pinning.
- Real repository clone-at-SHA.
- Real YAML and Helm inputs.
- Manifest rendering and dependency checks.
- Sandbox creation and isolation metadata.
- Deterministic Kubernetes failure fingerprints.
- Model inference against the real observed fingerprints.
- Validation pass/fail behavior.
- Finalization and result records.
- Sandbox cleanup.

Not tested in these ten controller-only runs:

- Running the customer’s actual containers in a production-equivalent cluster.
- Replaying a real customer request or workload.
- Mapping a real stack frame to a customer source file.
- Applying a real source patch.
- Reintroducing the original faulty hunk.
- Opening a pull request against a customer repository.

Those steps require a real failing revision, a last-known-good revision, source/coverage artifacts, an authorized repository token, and either a Kind or customer-isolated Kubernetes backend. The implementation is designed to fail closed until those inputs exist.
