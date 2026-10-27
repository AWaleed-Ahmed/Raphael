# Issue #78 Phase 1 — Original-source preparation and provenance

Date: 2026-10-27. Scope: checkpoints 1–4 of [#78](https://github.com/AWaleed-Ahmed/Raphael/issues/78), with evaluation requirements from [#66](https://github.com/AWaleed-Ahmed/Raphael/issues/66).

**Engineering preparation is implemented; final-test acceptance is not complete.** Twelve concrete original sources were acquired and hash-verified. Three original application bugs reproduce fail-before/pass-after. No model was trained, tuned, or scored; no rollout/default/policy setting was changed. An explicit final-readiness check currently refuses approval.

## Delivered evidence

| Item | Executed result | Limit |
| --- | --- | --- |
| Original source acquisition | 12 concrete cases, 60 original/derived artifact references; 3,801,931,718 verified uncompressed bytes | Raw data remains in an ignored local cache; not redistributed in Git |
| Code reproduction | Tornado, pandas, Scrapy: buggy exit 1; fixed exit 0 on original upstream regressions | Documented Python/compiler/dependency compatibility replay; no exact historic-environment claim |
| Recorded telemetry | Bank task_1, Telecom task_2, Market/cloudbed-1 task_6; matching-day original trace/metric members | Event-level source truth does not create trace-level labels, healthy baselines or repository ownership |
| Wider telemetry inventory | 335 original queries and 335 root-cause record rows across four dataset directories | Query/row count is not automatically a count of statistically independent incidents |
| Paired preparation | 24 sealed job definitions: model-off/model-on for each of 12 sources | Prepared, not executed; zero predictions and zero accuracy claims |
| Provenance audit | Five trusted artifact/manifest pairs match; all nine declared corpus references match available bytes | Eight historical synthetic data files plus the public-index source fixture; generation lineage is not independently attested |
| Exact leakage audit | No selected source URL/commit identifier found in the scanned original training corpus; classifier family and ranker incident groups have zero cross-split intersections | Exact checks do not establish semantic independence; original generation/labels still need review |
| Prior evaluation/index audit | 20 prior local result files inspected; K01–K05 found in prior evaluation; none of the 12 selected source URLs is in the verified public index | K01–K05 remain regression-only; public test partitions are not customer histories |

Machine-readable records: [source manifest](../agent/fixtures/production_readiness/source-manifest.json), [protocol](../agent/fixtures/production_readiness/protocol.json), [preparation/audit](evidence/issue-78/phase-1/preparation.json), [paired jobs](evidence/issue-78/phase-1/paired-jobs.jsonl), [OpenRCA inventory](evidence/issue-78/phase-1/openrca-inventory.json), [telemetry schema](evidence/issue-78/phase-1/telemetry-schema.json), [local training-code hashes](evidence/issue-78/phase-1/local-training-code.json), [reproduction proofs](evidence/issue-78/phase-1/reproductions.json), and [review worksheet](evidence/issue-78/phase-1/label-review.csv).

## Original sources and eligibility

| ID | Upstream source | Current use / exclusion from final-test claims |
| --- | --- | --- |
| K01 | [Volcano dashboard #295](https://github.com/volcano-sh/dashboard/issues/295) | Original report plus all 4 comments; prior evaluation overlap; image provenance and repair remain unqualified |
| K02 | [Weave Net #3917](https://github.com/weaveworks/weave/issues/3917) | Original report plus all 5 comments; prior evaluation overlap; archived dependencies and causal resolution need review |
| K03 | [Jenkins Kubernetes plugin #2772](https://github.com/jenkinsci/kubernetes-plugin/issues/2772) | Original report plus all 2 comments; prior evaluation overlap; reaper defect must not be conflated with an image-pull symptom |
| K04 | [Zalando postgres-operator #1722](https://github.com/zalando/postgres-operator/issues/1722) | Original report plus its comment; prior evaluation overlap; security-policy failure is not authority to weaken policy |
| K05 | [Prometheus #14195](https://github.com/prometheus/prometheus/issues/14195) | Original report plus both comments; prior evaluation overlap; memory symptom alone is not verified causal truth |
| K06 | [Bitnami charts #20222](https://github.com/bitnami/charts/issues/20222) | Original report plus all 21 comments; development candidate; closure does not establish a supported reproduced repair |
| B01 | [BugsInPy Tornado 1](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/tornado/bugs/1) | Original buggy/fixed code and metadata; compatibility regression reproduced; development only |
| B02 | [BugsInPy pandas 1](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/pandas/bugs/1) | Original buggy/fixed code and metadata; compatibility regression reproduced; development only |
| B03 | [BugsInPy Scrapy 1](https://github.com/soarsmu/BugsInPy/tree/11c5f1eea954a42132cfd06bf257766a7963e0fd/projects/scrapy/bugs/1) | Original buggy/fixed code and metadata; compatibility regression reproduced; development only |
| O01 | [OpenRCA Bank](https://github.com/microsoft/OpenRCA/tree/2a481ae63cb045c3eadbeca9eddaa10ec1151979), task_1, 2021-03-04 | Existing question/oracle records and original matching-day trace/metric files; development only |
| O02 | [OpenRCA Telecom](https://github.com/microsoft/OpenRCA/tree/2a481ae63cb045c3eadbeca9eddaa10ec1151979), task_2, 2020-04-11 | Existing question/oracle records and original matching-day trace/metric files; development only |
| O03 | [OpenRCA Market/cloudbed-1](https://github.com/microsoft/OpenRCA/tree/2a481ae63cb045c3eadbeca9eddaa10ec1151979), task_6, 2022-03-20 | Existing question/oracle records and original matching-day trace/metric files; development only |

The OpenRCA archives came from the [upstream-linked public folder](https://drive.google.com/drive/folders/1wGiEnu4OkWrjPxfx5ZTROnU37-5UDoPM). Only selected ZIP members were downloaded through checked byte ranges, decompressed, CRC-checked and SHA-256-hashed. Complete archive hashes are not claimed. A separate [cold rehydration check](evidence/issue-78/phase-1/rehydration-check.json) fetched one original query member from each of the three archives through the committed fetcher and independently matched its locked hash. All four query/record directory pairs were acquired for inventory; full trace/metric members were acquired for the three selected cases.

No demo failure was injected into Online Boutique, OpenTelemetry Demo or Train Ticket. No normalized error signature was authored to match a model. The three code reproductions exercise genuine historical application defects; they do not establish that Raphael's Kubernetes template generator can repair arbitrary Python code.

## Reproduction method and exact scope

Source identity: BugsInPy `11c5f1eea954a42132cfd06bf257766a7963e0fd`. Original buggy and fixed repository archives were acquired by full SHA. Both source trees were built/tested separately. As the upstream BugsInPy checkout procedure does, the fixed revision's **unmodified regression test file** was copied over the buggy tree; application code was not fixed by the evaluator. Predictor source bundles retain the original buggy archive; fixed tests/fixes remain evaluator-only except the explicitly collected real failure output in later ranking work.

| Case | Original upstream regression | Buggy outcome | Fixed outcome |
| --- | --- | --- | --- |
| B01 | `tornado.test.websocket_test.WebSocketTest.test_nodelay` | Actual assertion failure in the WebSocket path; exit 1 | Upstream test passes; exit 0 |
| B02 | `pandas/tests/dtypes/test_dtypes.py::TestCategoricalDtype::test_not_string` | Actual incorrect categorical/string dtype behavior; exit 1 | Upstream test passes; exit 0 |
| B03 | Original `TestOffsiteMiddleware4` helper and processing targets | Actual type error for the original offsite domain input; exit 1 | Upstream targets complete; exit 0 |

Interpreter: CPython 3.8.20 obtained in an isolated tool environment. Historical metadata asks for 3.7.0 (Tornado) and 3.8.3 (pandas/Scrapy). Docker daemon was unavailable. pandas' historical Cython output initially failed GCC 13's array-bounds warning under its `-Werror` build; retry used `CFLAGS=-Wno-error=array-bounds`, with no source edit. Scrapy uses the Linux-relevant dependency subset; the upstream requirements contain Windows-only entries. These are genuine defect reproductions under a documented compatible environment, not proofs of identical historical binaries or full production environments.

[Reproduction environment](evidence/issue-78/phase-1/reproduction-environment.json) records interpreter identity, packages and the compiler flag. Raw command logs and their SHA-256 values are retained locally and referenced in `reproductions.json`. Neither model predictions nor model-selected repairs were run.

To repeat after source acquisition, use the original per-case `run_test.sh`, original code SHAs, dependency metadata and unmodified fixed test overlay. Use Python 3.12's safe tar extraction (`filter="data"`) to prepare archives; never execute fetched shell files blindly. The observed environment setup was:

```bash
uv python install 3.8.20
uv venv --python 3.8.20 --seed /tmp/raphael-legacy
/tmp/raphael-legacy/bin/python -m pip install \
  'setuptools<59' wheel 'numpy==1.18.4' 'Cython==0.29.19' \
  'pytest==5.4.2' 'hypothesis==5.15.1' \
  'python-dateutil==2.8.1' 'pytz==2020.1'
/tmp/raphael-legacy/bin/python -m pip install \
  'Scrapy==2.1.0' 'Twisted==20.3.0' 'pyOpenSSL==19.1.0' \
  'cryptography==2.9.2' 'lxml==4.5.1'
```

Build each original pandas tree sequentially with the recorded compiler flag and `pip install --no-build-isolation --no-deps -e <tree>`. Select each original tree with explicit `PYTHONPATH` and execute the exact target recorded in `reproductions.json`; use `python -m pytest` for pandas and `python -m unittest -q` for the other two. Before any repeat, verify archive and fixed-test hashes against the manifest/proof. These legacy dependencies belong only in a disposable reproduction environment.

## What the audit establishes

The release-owned trust registry matches all five installed artifact and manifest identities. Original classifier, ranker, trace and patch data still exist locally and match every corresponding declared dataset hash. The classifier's original train/validation/test fingerprint-family groups and ranker's incident IDs have zero intersections in the checked splits. The final classifier/ranker training scripts combine train plus validation; this is recorded as historical code evidence, not a new training run.

The current similarity model is the #64 format-2 fixture index, whose verified source list identifies 49 available reports from a 50-row query fixture, repeated in four explicitly fictional ownership partitions. The audit checks that verification-file hash as well as the fixture and artifact hashes. It does not substitute the retired unowned synthetic index or infer actual customer tenancy.

Available ignored training/runtime code is hashed separately. No independent attestation binds those precise script bytes or the original synthetic-generation procedure to the shipped weights. Exact absence of new source URLs/commits in declared training text is consequently reported as a limited exact scan, not a guarantee of unseen-incident generalization. Old result files were scanned for selected identifiers without scoring or tuning on their predictions.

## Checkpoint disposition

| #78 checkpoint | Delivered now | Still required before closure |
| --- | --- | --- |
| 1 | Frozen baseline/artifact/policy identities; 24 identical-context prepared pairs; mismatch controls | Actual graph comparisons in Phase 2 and reviewed independent final corpus; prepared jobs are not executed predictions |
| 2 | Original reports/code/telemetry; three real fail-before/pass-after code reproductions | Independent cause/repair labels, eligible historical Kubernetes repairs, and review of evidence completeness |
| 3 | Raw/member hashes, role separation, source/index/prior-result audit, cross-split controls and exclusions | Terms/redaction/retention approval, generation-lineage resolution and two-human label/input reviews |
| 4 | Versioned proposed gates, resource envelope, sample floors, 95% uncertainty method and stopping policy before new scoring | Owner approval and adequate final coverage; detailed class/history/healthy-exposure labels are not yet frozen |

The [worksheet](evidence/issue-78/phase-1/label-review.csv) intentionally contains no invented reviewer names or approvals. All twelve source cases remain regression/development. Sample floors of 100 classification/ranking/retrieval/fault cases and 30 historical repair attempts are unmet by this first concrete source set; the OpenRCA inventory alone does not waive independence or label requirements. Existing public reports without a verified cause/reproduction remain report evidence or exclusions, never automatic positive labels.

## Tool behavior and tests

Implementation: `agent/raphael_agent/readiness.py`, `agent/scripts/fetch_readiness_evidence.py`, `agent/scripts/prepare_model_readiness.py`. See [usage](../agent/fixtures/production_readiness/README.md).

The offline preparer verifies source metadata, selected production-source/artifact identities, input/oracle separation, independent grouping and paired contexts. The optional raw-data pass streams exact-file hashes; no deserialization, inference or fit is performed. Corrupt bytes, escaping paths, nonfinite contexts, unknown roles, oracle content in inputs, same-incident cross-split placement, mismatched protocol/arms and unreviewed final-test claims refuse. The fetcher only publishes completely verified files, refuses redirects/unapproved hosts, bounds output and checks exact ZIP ranges/CRC.

`--require-final-ready` currently exits 2 with explicit blockers. Normal metadata preparation can be green in CI while reporting unavailable raw data and pending reviews. That is intentional; this PR does not close #78 or #66.

Local verification and hosted checks are recorded in the implementation PR. No production resource, tenant history, model weight, trust registry, public contract, default enablement, external provider or GitHub publication policy was changed.


## Local validation record

- Agent: **657 passed, 4 skipped** (existing optional integrations).
- Dispatch: **89 passed**.
- Workflow/security/evaluation/wire assertions: **58 passed**.
- New focused provenance/acquisition/preparation controls: **56 passed**, **97% combined coverage** of the three new verifier/CLI files.
- Strict mypy passes on all three new implementation files; Black, Ruff and diff checks pass.
- The [final-gate control](evidence/issue-78/phase-1/final-gate-check.json) exits 2 as required; pending approvals cannot become an automatic pass.

The disposable local tool environment initially lacked setuptools/wheel and used an unqualified pip trust bundle. Installing the repository's build tools and hash-pinned `requirements-bootstrap.txt` resolved those setup failures; repository safety checks were not weakened. Three original archived bug proofs and three cold archive-member fetches were exercised separately from unit controls. Hosted results are linked from the PR, not inferred from this local record.
