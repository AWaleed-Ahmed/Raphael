# Phase 3 — Installed runtime, load and failure evidence

Date: 2026-10-27. Tracking: #78 checkpoints 10–13 and #66 runtime measurements.
**Decision: deferred.** The measured gateway passes cold/warm latency, admitted-load latency, throughput and absolute memory limits. It fails the predeclared memory-growth limit. This report does not approve a deployment or change the Phase 2 quality decisions.

## What changed and why

A non-editable installation exposed a real defect: `schema_util` searched for the repository's `contracts/` directory, but the wheel did not contain those schemas. Graph validation outside the checkout raised `FileNotFoundError`. The wheel now installs the unchanged canonical agent and sandbox schemas under `share/raphael/contracts`; the resolver supports a normal virtual environment and `pip --target`, while preserving source-checkout behavior. The installation regression deletes both source and build-time contracts, checks every installed schema byte, validates through the installed resolver and replays all five real model families with networking denied. This is a wheel built from the full repository; a standalone source archive without the parent contracts directory is not qualified.

Added three small-purpose commands: prepare private source-linked jobs, measure the installed gateway, and exercise explicit failure/ownership controls. They do not train models, author historical incidents, or produce repair-accuracy claims. Historical Phase 2 audits still validate the frozen data, arms, protocol, policy and hashes; new scoring continues to demand exact current runtime/verifier source hashes. Old scores do not certify this changed runtime.

## Sources, schema and exclusions

Original sources are pinned in the [Phase 1 manifest](../agent/fixtures/production_readiness/source-manifest.json), with the original collection/reproduction details in [Phase 1](model-readiness-phase-1.md). Acquisition is reused rather than fetching changing issue bodies for each measurement.

| Source group | Authentic input used here | Boundary |
| --- | --- | --- |
| K01–K06 | Reports from [Volcano dashboard #295](https://github.com/volcano-sh/dashboard/issues/295), [Weave #3917](https://github.com/weaveworks/weave/issues/3917), [Jenkins Kubernetes plugin #2772](https://github.com/jenkinsci/kubernetes-plugin/issues/2772), [Postgres operator #1722](https://github.com/zalando/postgres-operator/issues/1722), [Prometheus #14195](https://github.com/prometheus/prometheus/issues/14195), [Bitnami charts #20222](https://github.com/bitnami/charts/issues/20222) | Original issue bodies enter the existing collector/gateway. No image provenance or successful reproduction is invented. |
| B01 / B03 | Frozen graph-generated candidates from the original [Tornado](https://github.com/tornadoweb/tornado) and [Scrapy](https://github.com/scrapy/scrapy) buggy code/log replays in Phase 2 | Two usable ranking inputs. B02 [pandas](https://github.com/pandas-dev/pandas) produced no candidates and is excluded from ranking, rather than supplied invented candidates. Exact revisions and log hashes remain in the manifests. |
| O01–O03 | Original [OpenRCA](https://github.com/NetManAIOps/OpenRCA) Bank, Telecom and Market telemetry, previously verified from the pinned archive | All three remain excluded from trace inference: native schema/units and an authorized healthy baseline have not been qualified. O03's first unchanged native CSV row is used only as a classifier fault-control substrate. |
| Prior #65 controls | Three existing source-linked [RCAEval](https://huggingface.co/datasets/phamquiluan/RCAEval/tree/main/re3ob_adservice_f3_1) trace projections, and the existing [Fission #102](https://github.com/fission/fission.io/issues/102) learned patch-refusal projection | Operational regression inputs, **not** new independent historical traces, validated repairs or accuracy evidence. |

The private load bundle has **24 jobs**: 18 K-report jobs, two ranking jobs, three prior trace projections and one prior learned patch-refusal projection. The public [input metadata](evidence/issue-78/phase-3/input-metadata.json) identifies every job, tier and input digest; [input sizes](evidence/issue-78/phase-3/input-envelope.json) give JSON bytes, candidates and issue characters. Tokens are unmeasured: these local estimators do not consume an LLM token budget. Repetition increases operational calls, not the number of independent incidents. Raw reports/code/telemetry are kept in the ignored source cache, not copied into this report.

Job schema: `{id, capability, source_ids, tier, input_sha256, state, candidates?}`. Call evidence: `{job_id, capability, phase, batch, elapsed_ms, output_sha256, serial_match, unavailable_reason, learned_execution, execution_source, abstained, policy_allowed}`. Resource evidence records monotonic time, cgroup CPU/memory limits and counters, affinity, completed jobs and batch duration. No report body is logged in these samples.

## Frozen deployment profile and footprint

[Profile](evidence/issue-78/phase-3/runtime-profile.json): Ubuntu 24.04 / Linux 7.0.0-38, x86-64 Intel i5-10400H developer host; Python 3.12.3, BLAS/OpenMP threads fixed to one. A real systemd cgroup enforced **CPU quota 200%, memory 2 GiB, swap zero**. `taskset` fixed the soak to logical CPUs 0/1; separate short probes used 2/3 on the same host. These are logical CPU affinity and quota measurements, not certification of two dedicated cloud vCPUs. Shared hardware/noisy neighbors remain a limitation. No Docker daemon was available locally.

The clean non-editable virtual environment was installed offline from captured wheels, after the repository's hash-pinned pip bootstrap. Package import paths in the raw records point inside that environment, outside the checkout. All inference calls in the worker deny socket connect/DNS/bind through a Python audit hook. Gateway timing includes adaptation, artifact/cache checks, inference and output validation; dataset acquisition and sandbox execution are outside this measurement.

| Footprint | Bytes |
| --- | ---: |
| All captured dependency/runtime wheels | 78,563,345 |
| Installed virtual environment | 358,187,642 |
| Five model directories, including metadata | 2,887,391 |
| Corrected agent wheel | 243,671 |

The profile records every wheel/model/bootstrap SHA-256 and size. The [installation report excerpt](evidence/issue-78/phase-3/installation-report.json) binds resolved versions and the original report hash; unrelated package README/license bodies are omitted. These are the repository's dependencies, including its currently declared test tooling; no smaller production-only dependency set is claimed. ML versions are joblib 1.6.0, NumPy 2.5.2, SciPy 1.18.1 and scikit-learn 1.9.0. The [wheel source binding](evidence/issue-78/phase-3/wheel-source-binding.json) verifies every packaged Python source and canonical schema against this branch. The wheel was built from base `deaca2746779b2aff57e0064b77c05af37a11558` plus the packaging fix before its commit; its exact bytes, rather than a claim of an already clean commit, identify the tested runtime.

## Performance results

Thirty alternating off/on pairs used **fresh Python processes**, including real imports and verified artifact loading. OS disk cache was not flushed. Model-on cold p95 was **1.252 s** (maximum 1.259 s), below the proposed 5 s limit; disabled p95 was 0.110 s. The recorded service-wrapper elapsed time is a conservative process-start-to-completion boundary, not a public health endpoint's readiness time. [Cold samples and quantiles](evidence/issue-78/phase-3/cold-start.json).

Serial warm measurements made **1,000 calls per capability per arm**. Values below are complete gateway milliseconds. The soak then used a ten-minute warm-up followed by **7,200 measured seconds**, concurrency four, offering four mixed jobs each second. Each mixed job runs one call per capability, sequentially; four mixed jobs run concurrently.

| Capability | Warm on p95 / p99 ms | Warm off p95 ms | Warm learned calls / 1,000 | Soak p95 / p99 ms |
| --- | ---: | ---: | ---: | ---: |
| Candidate ranking | 1.663 / 1.893 | 0.055 | 1,000 | 48.928 / 59.413 |
| Failure classification | 1.012 / 1.065 | 0.008 | 1,000 | 16.644 / 26.784 |
| Incident similarity | 0.995 / 1.256 | 0.006 | 1,000 | 21.260 / 30.250 |
| Patch selection | 1.200 / 1.228 | 0.008 | 142 | 8.450 / 16.903 |
| Trace anomaly | 0.992 / 1.023 | 0.004 | 1,000 | 9.799 / 17.388 |

“Learned” records estimator execution, including abstentions; it does not mean the decision was correct or useful. Patch's other calls are existing out-of-domain/refusal paths. Disabled timings measure the cheap disabled gateway, not a full rules-only incident. No improvement in quality follows from these numbers.

[Cgroup CPU counters](evidence/issue-78/phase-3/cpu-assessment.json) show 496.860 CPU-seconds over the 7,199.004-second first-to-last steady-sample interval: 0.069 average logical cores (3.45% of the two-core quota), with zero recorded throttled seconds. This includes the benchmark, excludes warm-up/final aggregation, and is not a cloud billing estimate.

The soak completed **28,788/28,788 accepted mixed jobs** (143,940 measured capability calls), **3.998 jobs/s**, with **zero runtime errors and zero serial-output mismatches**. Three scheduled batch opportunities were skipped because the closed-loop driver waits for an accepted batch before admitting another; no accepted request was lost. The ranker's worst individual call was **3,408.7 ms**, despite passing p95/p99. This is not a hard deadline guarantee. [Full soak summary](evidence/issue-78/phase-3/soak-summary.json).

| Short probe | Measured seconds | Mixed jobs/s | Ranker p95 ms | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Concurrency 1, period 50 ms | 60 | 20.00 | 7.81 | Saturation exploration |
| Concurrency 4, period 50 ms | 60 | 55.80 | 42.20 | Saturation exploration |
| Concurrency 8, period 50 ms | 60 | 131.87 | 33.52 | Saturation exploration; noisy, non-monotonic result |
| Concurrency 16, period 50 ms | 60 | 124.80 | 59.97 | Exceeds proposed 50 ms gate |
| Two-times burst, concurrency 8, period 1 s | 60 | 8.00 | 67.72 | Exceeds proposed 50 ms gate |

All short probes had zero accepted-job loss, runtime errors and serial mismatches. They had only five seconds of warm-up and are **not** qualified sustained plateaus or a maximum-capacity claim. The only long plateau is concurrency four at the proposed four jobs/s, which includes more than five minutes of warm-up and thirty minutes of measurement. This bounded benchmark admission is not a production HTTP queue, timeout, cancellation or overload-rejection implementation. No new production concurrency setting is enabled.

## Memory gate: failed

The full measured cgroup, including worker threads and benchmark I/O, peaked at **135.715 MiB**, below 1.5 GiB. However, first steady ten-minute median memory was **103.715 MiB**, versus **133.375 MiB** in the last ten minutes: **28.598% growth**, above the predeclared 10% limit. Ten-minute medians also resume rising after a mid-run drop. [Window assessment](evidence/issue-78/phase-3/memory-assessment.json).

The driver streams calls instead of retaining latency lists during the timed phase, but cgroup accounting also includes file cache charged by its growing output files. No historical `memory.stat` anonymous/file split or process RSS series was captured. File cache is a possible contributor; **this does not establish the cause or disprove a runtime leak**. The strict gate remains failed. A follow-up must capture anonymous/file/RSS and process-tree ownership, fix any demonstrated runtime or measurement retention, then rerun the full frozen-duration profile. Do not subtract guessed cache bytes or loosen the gate retrospectively.

## Failure, recovery and safety matrix

Operational faults are explicitly injected into disposable copies or owned processes while authentic inputs run. They are not historical incidents and do not add independent accuracy cases. [Machine-readable matrix](evidence/issue-78/phase-3/failure-matrix.json).

| Control | Real source contexts / denominator | Observed result and limit |
| --- | --- | --- |
| Missing/corrupt artifact, missing/corrupt manifest, forged artifact/manifest pair | K01, B02, O03 × 5 controls | 15 cold rejections before deserialization. Already verified warm cached objects remain usable; clearing cache exposes damage. Restoring trusted bytes recovers. No hot replacement is certified. |
| Wrong dependency version, estimator warning, runtime exception, malformed/nonfinite/unknown-class output | K01, B02, O03 × 6 controls | 18 bounded refusals; injected private exception text/class names absent; original input unchanged. Dependency/warning failures are controlled injections, not installation of an arbitrary incompatible stack. |
| Each registered family rejects changed bytes | Five families | Five additional pre-deserialization rejections; 38 total artifact/output fault rows. |
| Tenant/company/client mismatch and valid ownership | K01, K03, K04 × four scope patterns × eight repetitions | 96 parallel outcomes agree with serial outcomes; zero observed ownership leaks. Test partitions of public reports are not real customer authorization. |
| Nonfinite output at concurrency four | K01, B02, O03 × eight repetitions | 24 denials; three subsequent actual predictions remain available. |
| Image provenance, unsupported controller repair, security-sensitive report | K01, K03, K04 through actual evidence/diagnose/patch nodes | Three escalations, zero patch proposals. K04 still has the Phase 2 classification error; lack of reproduction blocks proposals. These are precondition checks, not successful repairs. |
| Real catalog connection refusal | K01, K03, K04; a reserved, non-listening local port | Three explicit `localization_failed` results; zero fabricated healthy baselines/candidates. Local transport failure does not prove every remote outage/timeout mode. |
| Actual kernel OOM and owned-process SIGKILL | K01, B02, O03 × two controls | Six non-successful victims, zero false completed markers. Fresh actual classifier recovery 1.022–1.061 s, below 60 s. OOM uses a deliberate **128 MiB** cgroup; it is not an OOM claim about the 2 GiB profile. |
| CPU pressure | K01, B02, O03 × ten calls, two owned CPU burners in the 2-CPU cgroup | 30 real calls match serial hashes; zero runtime errors. Both owned burners terminated and reaped. |

[Resource-control evidence](evidence/issue-78/phase-3/resource-controls.json) contains victim/restart outcomes and logs. A `started_not_completed` marker is never interpreted as success. Some systemd console summaries report stale, implausibly small memory peaks; resource measurements use the worker's actual kernel cgroup files, rather than those console summaries. This verifies an owned inference process's failure/restart; it does **not** prove automatic production supervisor recovery, journal reconciliation, a crash during downstream sandbox work, exactly-once publication, or orphan cleanup after such a crash. Those requirements remain open. Existing lease/cancellation and hosted kind controls are regression coverage with their own boundaries.

## Hosted healthy-sentinel regression

The first hosted remediation run passed probe repair and both image-provenance cases, then failed the healthy-sentinel assertion. The [authentic CI trace](evidence/issue-78/phase-3/ci-healthy-startup/source.json) shows a Ready pod retaining a startup `Readiness probe failed` event. The existing deterministic analyzer selected a probe hypothesis, but the observed signature was healthy / `reproduced=false`; the reproduction precondition escalated with `reproduction_failed`, without a patch or publication. The proof incorrectly required the earlier `low_confidence` stop exclusively. It now accepts those two specific refusal gates while still requiring observed health, no reproduction, no patches/validation/publication and discard instructions. A regression replays the actual wire trace and rejects unrelated terminal reasons or a claimed successful reproduction. Runtime diagnosis is unchanged; the stale-event false positive remains a quality limitation. This owned Kubernetes control is not an additional historical accuracy case.

## Acceptance and next work

| Checkpoint | Measured conclusion | Remaining acceptance work |
| --- | --- | --- |
| 10: deployment/CPU cost | Named local cgroup, installed wheel, 30 cold pairs, 1,000 warm calls/capability, complete hashes/footprints | Approved provider/container profile, independent budget owner, full paired graph overhead and incident latency; historical RSS/anonymous-memory accounting |
| 11: concurrency/load | Two-hour gateway plateau: throughput, latency, accepted completion and deterministic outputs pass | **Memory stability fails**; burst latency fails. Diagnose and rerun. Production admission/timeout/cancellation and partner arrival mix are not certified. |
| 12: failures/recovery | Recorded corruption/output/ownership/CPU/OOM/kill controls pass within their measured boundaries | Three-source downstream journal/sandbox crash, lease reconciliation, supervisor health and cleanup proofs; live remote outage modes |
| 13: safety | Zero observed bypasses/proposals/leaks in the stated controls; existing safety regression suites pass | New live downstream lifecycle proof and independent security/authorization review; no universal safety guarantee |

Local validation: **712 agent tests passed / 4 optional skips**, with the original public cache explicitly enabled; dispatch **89 passed**; workflow/wire assertions **59 passed**, including a recorded hosted-Kubernetes regression. The three new scripts have **98% combined statement coverage** (preparation 96%, runtime 98%, faults 99%). Targeted strict mypy checks pass for these scripts with imported legacy modules followed silently; a whole-repository strict run exposes pre-existing errors and is not represented as passing. Formatting/lint checks cover changed Python files. Ordinary unit CI omits the multi-GB cache and skips the two original-cache tests; the compressed evidence audit still runs offline. Hosted PR checks are recorded on the PR.

Neither #66 nor #78 is closed or marked production-qualified. Models remain default-off. Phase 4 can consume these failure semantics and evidence, but a pilot remains blocked by Phase 2 quality gaps and this phase's unmet gates.

## Reproduction and evidence audit

Use the repository's [bootstrap instructions](../requirements-bootstrap.txt), the pinned original-source acquisition from Phase 1, and the captured dependency inventory. Build the agent wheel from the full repository, install `agent[local-inference]` non-editably in a clean environment, then copy the model tree and standalone worker/fault scripts to a new temporary directory. Set `RAPHAEL_MODEL_ROOT` to that model copy for graph controls. Do not run long controls on a production supervisor or cluster.

```bash
# In agent/, using the source environment and already verified original cache:
python -m scripts.prepare_model_runtime --cache-root "$SOURCE_CACHE" --output "$RUN_DIR/inputs"
# Copy scripts/qualify_model_runtime.py to "$RUN_DIR/worker.py".
# RUNTIME_PYTHON is the clean installed environment; RUN_DIR is a new private directory.
systemd-run --user --wait --pipe --collect \
  -p CPUQuota=200% -p MemoryMax=2G -p MemorySwapMax=0 \
  -p RuntimeMaxSec=9000 -p WorkingDirectory="$RUN_DIR" \
  /usr/bin/taskset -c 0,1 "$RUNTIME_PYTHON" "$RUN_DIR/worker.py" load \
  --jobs "$RUN_DIR/inputs/jobs.json" --model-root "$RUN_DIR/models" \
  --output "$RUN_DIR/soak" --enabled --warmup 600 --duration 7200 --concurrency 4 --period 1
```

Use `probe` in 30 alternating disabled/enabled fresh-process pairs, `warm --repeats 1000` for each arm, and the same `load` command at the documented short-probe settings. The [measurement index](evidence/issue-78/phase-3/measurement-index.json) preserves exact executed argv, UUID units, durations and exit codes. Historical [drivers](evidence/issue-78/phase-3/drivers) preserve the actual local orchestration, including owned resource controls; their absolute paths identify this run and require a disposable directory when replayed. They are evidence, not production entry points.

The [seal](evidence/issue-78/phase-3/seal.json) binds public file hashes and harness source hashes. Gzip files preserve **all** bounded soak calls/resources and cold probes. The evidence-audit regression recomputes hashes, accepted-call denominators and memory-window growth offline. This detects accidental evidence drift; an unsigned repository hash manifest is not an independent attestation. A new preparation run includes fresh run timestamps, so its whole-state digest can differ; freeze a new bundle before a new run rather than relabelling it as the old bundle.
