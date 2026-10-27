# Phase 2 — Original-source paired development evaluation

Date: 2026-10-27. Tracking: #78 checkpoints **5–9**, evaluation owner #66.
Status: development experiment delivered; **production acceptance is not met**.
The [Phase 2 plan](plans/issue-78/phase-2-model-evaluation.md) remains the acceptance specification.

## Result and decision

The present local models have **not demonstrated added benefit** on these original-source development inputs. Keep all five capabilities deferred and default-off. The result does not establish that the models can never help; it identifies what this evidence can support and what currently prevents a valid quality claim.

| Checkpoint / capability | Original sources checked | Model-off versus model-on result | Acceptance |
| --- | --- | --- | --- |
| **5 — Classification** | Six original Kubernetes issue bodies, K01–K06 | Same final classifications in all six pairs. Two image-policy stops; four real estimator executions, all abstained; zero effective learned classifications | Insufficient evidence: no independently reviewed cause/taxonomy labels or learned improvement |
| **6 — Ranking** | Three reproduced BugsInPy failures: Tornado, pandas, Scrapy | Both arms: top-1 **1/3**, top-3 **2/3**, MRR **0.444**. Graph generated candidates in **2/3**; two real ranking executions. **0 wins / 3 ties / 0 regressions** | Insufficient evidence; development results miss proposed 75% top-1, 90% top-3 and improvement gates |
| **7 — Similarity** | K01–K06 against the unchanged trusted public index | Baseline returns no model history; learned retrieval returns **0 matches in 6 queries** | Insufficient evidence: no reviewed relevance/no-match labels or three independent pre-query histories |
| **8 — Trace anomaly** | Original OpenRCA Bank, Telecom and Market trace CSVs, O01–O03 | **3/3 compatibility checks blocked**. Native schemas lack reviewed mappings to required model fields and verified owned healthy baselines. **0 anomaly predictions scored** | Blocked; event precision/recall, delay and false-alert rates remain unmeasured |
| **9 — Patch selection** | Six original Kubernetes reports, including K01/K02/K06 triage and K03/K04 ambiguity/security cases | Same precondition stops in both arms; **0 selector executions, 0 proposals, 0 validated Raphael repairs** | Blocked; no verified historical Ignis reproduction/authorized healthy image baseline |

There are **12 source cases**, **24 case-capability comparisons**, and **48 arm records**. These are not 48 independent incidents. Cases overlap capabilities; no synthetic production incident, authorized customer history, healthy trace, causal label or successful patch was fabricated.

The five-row table is a capability decision, not an aggregate pass score. Missing labels yield `null` quality metrics, never zero or 100% accuracy. Three source checks satisfy development triage coverage; they do not satisfy the final sample floors.

## What changed

- Added `agent/scripts/evaluate_model_readiness.py` with separate **predict** and **score** stages. Predictions are sealed before scoring opens maintainer fix metadata. The runner explicitly refuses final-test splits.
- Prediction bundles use only Phase 1 input-role files plus the hash-pinned original buggy execution logs. Oracle files are hashed for integrity but their contents are not read by the predictor. The trusted index is an existing model artifact, with its known overlap limitations preserved.
- Source/policy/model/protocol hashes, input/adapter/candidate hashes, exact Python/library versions and machine information accompany the predictions. Scoring rejects changed bytes, missing/duplicate arms, differing paired inputs, source drift and attempted substitution of oracle files.
- Source candidates come from the actual production localization node with all models off, then are frozen once for the two ranking arms. Candidate identities/evidence stay unchanged; only scores/order may differ.
- Added distinct-file top-k/MRR, Wilson intervals and a deterministic 10,000-resample incident-cluster bootstrap using seed 7801. Generation misses remain in all-input denominators.
- Production graph logic, weights, manifests, thresholds, index, policies and model defaults are unchanged. This experiment measures the existing baseline, rather than tuning it on evaluation cases.

The seals are reproducibility checks, **not signed independent execution attestations**. A person able to replace both evidence and its seal can forge a new experiment; the recorded source/input identities and review process remain necessary.

## Real-world sources and actual execution

Sources, original hashes and acquisition commands remain in the [Phase 1 source manifest](../agent/fixtures/production_readiness/source-manifest.json) and [Phase 1 execution report](model-readiness-phase-1.md). Raw issue/comments, original code archives, telemetry and logs remain in the ignored local cache; this PR does not redistribute them.

| ID | Original source | What ran in Phase 2 |
| --- | --- | --- |
| K01 | [Volcano dashboard #295](https://github.com/volcano-sh/dashboard/issues/295) | Original report through the normal issue collector, diagnosis, scoped retrieval and patch preconditions |
| K02 | [Weave Net #3917](https://github.com/weaveworks/weave/issues/3917) | Same; image-pull text does not become verified controller evidence |
| K03 | [Jenkins Kubernetes plugin #2772](https://github.com/jenkinsci/kubernetes-plugin/issues/2772) | Same; an image-pull symptom does not certify the controller reaper defect's cause |
| K04 | [Zalando Postgres operator #1722](https://github.com/zalando/postgres-operator/issues/1722) | Same; runAsNonRoot/nonnumeric-user evidence is not a missing ConfigMap value |
| K05 | [Prometheus #14195](https://github.com/prometheus/prometheus/issues/14195) | Same; OOM evidence is not proof of a memory-leak root cause |
| K06 | [Bitnami charts #20222](https://github.com/bitnami/charts/issues/20222) | Same; a closed thread is not a sandbox-validated repair |
| B01 | [BugsInPy Tornado 1](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/tornado/bugs/1) | Unmodified buggy source plus actual Phase 1 failure frames → production localization → paired ranking |
| B02 | [BugsInPy pandas 1](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/pandas/bugs/1) | Same; abbreviated pytest assertion output yields no recognized application frames/candidates |
| B03 | [BugsInPy Scrapy 1](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/scrapy/bugs/1) | Same; actual offsite-middleware frames produce candidates |
| O01 | [OpenRCA Bank, task_1, 2021-03-04](https://github.com/microsoft/OpenRCA/tree/2a481ae63cb045c3eadbeca9eddaa10ec1151979) | Whole-member SHA/size verification and fixed first-1,000-row native trace-schema check |
| O02 | Same pinned OpenRCA source: Telecom, task_2, 2020-04-11 | Same; native fields remain native rather than receiving inferred success/status/units |
| O03 | Same pinned OpenRCA source: Market/cloudbed-1, task_6, 2022-03-20 | Same; no healthy intervals or HTTP semantics inferred from field names |

OpenRCA's [official documentation](https://github.com/microsoft/OpenRCA/blob/main/README.md) describes a root-cause-analysis benchmark, not per-span anomaly truth. It records fault times in UTC+8 and warns that telemetry sampling may not coincide with a fault timestamp. This run does not invent an alert interval, duration unit, healthy exposure, causal component or trace-level label from those records.

The Phase 1 cache verification covers **60 artifacts / 3,801,931,718 bytes**. All three full trace members are verified; the 1,000-row prefixes are compatibility inspections, not full-day anomaly evaluations. The 335 OpenRCA query/record pairs inventoried previously are not 335 independent scored incidents in this run.

## Findings that explain the result

### Issue evidence loses detail at the model adapter

This experiment feeds the declared body-only input through `collect_issue_evidence`, without adding a title from an evaluator-only raw snapshot. That collector supplies the default summary `GitHub issue` and a bounded report excerpt. `ModelGateway._failure_record` currently chooses `summary or content_excerpt`, so the classifier/retrieval adapter sees only **12 evidence characters** for each of the six reports, despite collected excerpts of 1,071–4,000 characters. No normalized reason, class hint or answer-bearing fingerprint is injected to compensate.

Consequently, the four allowed classifier calls produce the same raw highest-probability class (`bad_image_reference`, 0.827268), then correctly abstain as out-of-distribution. This is not evidence of calibrated confidence or good causal diagnosis. Real webhooks carrying nonempty issue titles would retain those titles, but still lose the body at this adapter; this replay does not claim to measure that different input envelope.

K04 also exposes a pre-existing deterministic limitation: the broad `CreateContainerConfigError` rule produces `invalid_missing_config` on a security-context startup report. This is an observed symptom/taxonomy mismatch for review, not an independently adjudicated misclassification count. Model-on leaves it unchanged and patching stops without reproduction. No security policy was relaxed.

These findings are documented rather than silently repaired inside the frozen comparison. A body-preserving adapter fix and a more specific deterministic rule need a separately versioned development comparison with the same safety tests. Neither requires retraining; final labels must remain untouched.

### Real candidates are weaker than projected benchmark candidates

| Case | Graph candidates | Maintainer changed application file | Baseline distinct-file rank | Model rank |
| --- | ---: | --- | ---: | ---: |
| B01 Tornado | 5 | `tornado/websocket.py` | 3 | 3 |
| B02 pandas | 0 | `pandas/core/dtypes/common.py` | miss | miss |
| B03 Scrapy | 4 | `scrapy/spidermiddlewares/offsite.py` | 1 | 1 |

Only actual Python `File ... line ... in ...` application frame coordinates are retained from the original logs. Paths are normalized from the known source archive root to repository-relative coordinates after checking that they exist in the pristine buggy tree. Test frames, copied fixed-test bodies, assertions and test commands are excluded; pytest abbreviated locations are not synthesized into frames. This is an explicit input projection, not a production path-normalization improvement.

No upstream fix filename, patch hunk, changed-file feature or expected label is available while generating/ranking candidates. The scorer reads the original maintainer commit's changed `.py` files afterward, excluding `test`/`tests` directories. The predeclared development relevance rule is **any changed non-test Python source file**; this checks file localization, not causal line correctness or a successful repair.

Tornado exposes how concatenated tracebacks plus the current five-frame/anchor ordering can prioritize an I/O-loop frame over the failing websocket source. pandas exposes an unsupported traceback format. Scrapy has multiple anchors in one actual fix file; those anchors count as one file, not four successful incidents.

Top-1 1/3 has Wilson 95% interval **6.15–79.23%**; top-3 2/3 has **20.77–93.85%**. Conditional on generating a relevant candidate, top-1 is 1/2 in both arms. The observed paired top-1 delta is zero, with a bootstrap interval [0, 0] because all three observed pairs tie. That degenerate interval does not establish population-wide equivalence with only three incidents.

The 74% projected-fixture ranker result in #65 and this 33.3% original-failure result use different candidate-generation and input envelopes. They must not be presented as an accuracy regression over time or averaged together.

### Retrieval, telemetry and repairs remain evidence-limited

The index remains the registry-pinned 49-source public release. Its four ownership partitions are copies of the same public corpus, not four independently collected tenant histories. Existing #64/#65 ownership controls remain regression evidence. This run uses one labelled test scope and an empty loopback REST healthy catalog, not live Supabase or customer authorization.

All six queries return no matches; returned-result precision has denominator zero and remains unscored. Zero returned matches do not prove correct no-match decisions because no independent relevance/no-match labels exist. K01–K05 were seen in earlier evaluations and remain regression cases; exact URL/commit checks are not proof of semantic training independence.

The telemetry checks stop before zero-filled or guessed records can be advertised as anomaly proof. A reviewed adapter, native-unit/clock mapping, matching verified healthy baseline, precise fault intervals and verified healthy service-hours are necessary for event metrics. Patching similarly stops at the real diagnosis/reproduction boundary. Upstream fail-before/pass-after bug reproductions are maintainer-fix evidence, **not Raphael-generated repairs**; Phase 2 does not rerun those legacy test commands or claim Docker fidelity.

## Reproduce and inspect

Use the packaged inference extra and trusted release artifacts, as described in [Phase 1](model-readiness-phase-1.md). The cache is intentionally not in Git; acquisition is performed by the existing hash-locked fetcher. The three reproduction logs must come from the documented Phase 1 commands and match their committed hashes.

From the repository's `agent/` directory:

```bash
python -m scripts.evaluate_model_readiness predict \
  --cache-root /absolute/path/to/production_readiness_phase1 \
  --output /tmp/readiness-predictions

# Only after prediction files have been written and sealed:
python -m scripts.evaluate_model_readiness score \
  --cache-root /absolute/path/to/production_readiness_phase1 \
  --predictions /tmp/readiness-predictions \
  --output /tmp/readiness-score

# Original-data integration test; otherwise this cache-dependent test skips.
RAPHAEL_READINESS_CACHE=/absolute/path/to/production_readiness_phase1 \
  python -m pytest tests/test_model_readiness_evaluation.py -q
```

Output directories must be empty/new; prior experiments are not silently overwritten. The script writes no source changes, runs no downloaded code, rebuilds no index, trains/tunes no model and publishes/deploys nothing. Local fixtures only use loopback HTTP. Learning and external LLMs are off, publication is dry-run, and test credentials replace inherited publication credentials while the evaluation runs.

Evidence: [sealed predictions](evidence/issue-78/phase-2/predictions.jsonl), [execution seal](evidence/issue-78/phase-2/seal.json), [machine-readable scores](evidence/issue-78/phase-2/summary.json), [generated five-capability summary](evidence/issue-78/phase-2/evaluation-summary.md). All source hashes in the seal identify the executed code revision; later evidence/documentation commits do not change those runtime files.

## Performance and verification limits

The execution seal records the Intel Core i5-10400H CPU, Python 3.12.3, exact inference libraries, cold artifact-load measurements, peak process RSS and per-record elapsed times. Timings cover a single development replay, including adapter/node overhead and local REST where relevant. Trace checks with no prediction have zero elapsed placeholders, not measured inference latency. Cold artifact loading is not process cold start. This is not a sustained-load, p95 hosting-budget or installation-footprint qualification; those remain Phase 3/#66 work.

The actual original-cache integration test covers prediction, source extraction, collector/localization call sites, sealed output validation and post-seal scoring. Unit mutations and metric arithmetic controls are clearly labelled; mocked controls are not positive model evidence. CI can recompute committed metrics and verify the execution seal offline; without the private local cache it does not independently rerun the multi-GB original-data experiment.


| Capability | Baseline median / maximum ms | Model-on median / maximum ms | Measured arms |
| --- | ---: | ---: | ---: |
| failure_classifier | 1.95 / 2.50 | 2.40 / 19.17 | 6 per arm |
| candidate_ranker | 0.32 / 0.37 | 2.14 / 29.73 | 3 per arm |
| incident_similarity | 0.93 / 1.04 | 2.97 / 102.54 | 6 per arm |
| patch_selector | 2.92 / 3.19 | 3.30 / 3.99 | 6 per arm |

These are single-pass node/adapter times (including cold reloads and local HTTP), not warm p95 estimates. Patch rows time a refusal path, and no trace-inference latency was measured. Whole-process peak RSS was **433,096 KiB (422.95 MiB)**, including source extraction and evaluation overhead; it is not incremental model memory. The nominal cold-load measurements in the seal share an already-running interpreter and ordered imports.

## Engineering validation

- Full agent suite with the actual original-data integration enabled: **692 passed, 4 existing optional tests skipped**.
- Focused evaluator/integrity/original-data suite: **35 passed**; combined statement coverage **99%** (metrics 100%, predictor/scorer 98%).
- Dispatch: **89 passed**. Workflow, dependency-security, evaluation and wire checks: **58 passed**.
- Strict mypy on both new modules, Black, Ruff and `git diff --check` passed.
- Hosted CI result is linked in the PR; it reruns integration/safety controls and the offline evidence audit, not the ignored source-cache experiment.

## Remaining acceptance work

- Protocol-owner approval, source terms/input review, two independent human label reviews and an independent final test set remain outstanding from Phase 1.
- Final floors remain classification 100 incidents/30 per claimed class; ranking 100 bugs across three projects; retrieval 100 queries/three distinct histories; trace 100 faults/three systems plus 100 verified healthy service-hours; patch 30 eligible historical attempts/three repositories.
- Classification still needs reviewed confusion/per-class precision/recall, macro-F1, accepted-error/coverage and meaningful calibration. Retrieval needs independently labelled relevant/irrelevant/no-match histories. Trace and patch need compatible original execution evidence before scoring.
- These are isolated per-capability ablations with upstream model effects held at baseline. A complete model-on production-graph comparison and interaction ablations remain necessary on eligible original cases. #65's compiled recorded control and live kind control retain their original, narrower meaning.
- No checkpoint 5–9 is checked off as production-qualified, #66/#78 stay open, and this PR does not authorize model enablement or pilot admission. A useful Phase 2 outcome is deferral with specific evidence; green engineering CI is not an accuracy pass.
