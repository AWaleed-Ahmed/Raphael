# Phase 1 — Source verification, dataset freezing, and acceptance criteria

Date: 2026-10-27. Status: engineering implementation and original-source evidence prepared; final-test approval remains pending. See the [execution report](../../model-readiness-phase-1.md).
Tracking: [#78](https://github.com/AWaleed-Ahmed/Raphael/issues/78), checkpoints **1–4**; evaluation owned by [#66](https://github.com/AWaleed-Ahmed/Raphael/issues/66).
Next: [Phase 2](phase-2-model-evaluation.md).

## Goal and scope

Produce an auditable, independent evaluation corpus and freeze passing criteria before scoring. The user requires original signatures, code, repositories, and recorded telemetry: do not author broken manifests, invent stack traces, manufacture root-cause labels, or describe injected application faults as historical incidents.

The five plans are sequential: data → model benefit → runtime → operations → authorized pilot. Their checkpoint numbering matches the 21 checkboxes in #78. They are plans, not shipped behavior, completed evaluations, authorization to deploy, or a promise that all capabilities will pass.

## Baseline and constraints

- Remote Raphael main inspected on this date: `840762c4c164453f0ad6d8e13d61836c6612e8f2`, the merged #77/#65 qualification. Re-resolve main, `CONTRACTS_VERSION`, and the immutable Ignis partner revision when implementation starts; record the exact tested pair.
- Existing runtime seams: `agent/raphael_agent/local_inference/`, `model_gateway.py`, `model_outputs.py`, `incident_scope.py`, graph nodes, and `agent/scripts/qualify_model_graph.py`. Reuse them; do not build a second inference stack.
- #63–#65 prove packaged execution, scoped retrieval, and graph/safety integration. Their 251 inputs are regression evidence, not independently labelled production accuracy. Existing issue markers are weak labels; recorded sandbox stubs cannot establish repairs.
- Existing dated PRD/handoff/pilot documents contain historical availability statements. Use merged code and dated evidence to determine delivery status; preserve PRD goals rather than treating stale implementation notes as current facts.
- Production remains read-only. Inference, learning, external LLM calls, and publication remain off unless explicitly enabled for a qualified, authorized scope. No retraining, paid infrastructure, public-contract change, or new patch family is part of this plan.

## Verified source catalogue

“Verified” below means the upstream page or metadata was accessible during planning. Dataset archives, historical environments, labels, licenses for redistribution, and reproduction have not yet been qualified. Exact final incident IDs must be chosen during Phase 1; do not claim that a dataset family is already an executed case.

| ID | Original source | Evidence available / intended use | Current limitation |
| --- | --- | --- | --- |
| K01 | [Volcano dashboard #295](https://github.com/volcano-sh/dashboard/issues/295) | Published manifest/image-pull report; original issue text and repository | Used in #65; regression seed. Image absence and an approved replacement require independent evidence. |
| K02 | [Weave Net #3917](https://github.com/weaveworks/weave/issues/3917) | Reported `ImagePullBackOff`, command output, historical environment | Used in #65; archived project. Reproduction and maintainer-confirmed cause/fix unqualified. |
| K03 | [Jenkins Kubernetes plugin #2772](https://github.com/jenkinsci/kubernetes-plugin/issues/2772) | Image-pull state plus failure of pod cleanup/reaper behavior | Used in #65. The cleanup defect must not be mislabelled simply as a missing-image root cause. |
| K04 | [Zalando postgres-operator #1722](https://github.com/zalando/postgres-operator/issues/1722) | Reported production pooler startup failure, v1.7.0, original nonnumeric-user/`runAsNonRoot` error | Used in #65; unresolved report when inspected. Security policy must not be relaxed to produce a “repair.” |
| K05 | [Prometheus #14195](https://github.com/prometheus/prometheus/issues/14195) | Existing OOM report referenced in the qualification corpus | Re-fetch full discussion and validate cause; an OOM marker alone does not establish a memory-leak label. |
| K06 | [Bitnami charts #20222](https://github.com/bitnami/charts/issues/20222) | PostgreSQL-HA install command, chart context, Kubernetes events and startup logs | New candidate relative to the listed #65 seeds, not proven training-independent. Historical image/storage availability and actual resolution need checking. |
| B01 | [BugsInPy Tornado bug 1](https://raw.githubusercontent.com/soarsmu/BugsInPy/master/projects/tornado/bugs/1/bug.info) | Buggy `6a5a0bfa370b6c0d3dbbf9589a560a98202d2baa`; fixed `4677c54cc18bbfbdf0f4dadf11610fab6203fd63`; `tornado/test/websocket_test.py` | Metadata verified; Python 3.7 environment and failing/passing tests not yet run. |
| B02 | [BugsInPy pandas bug 1](https://raw.githubusercontent.com/soarsmu/BugsInPy/master/projects/pandas/bugs/1/bug.info) | Buggy `3fd150c9e6e3a1a39622577745a7d821611c09d3`; fixed `e41ee47a90bb1d8a1fa28fcefcd45ed8ef5cb946`; `pandas/tests/dtypes/test_dtypes.py` | Metadata and full buggy SHA verified; Python 3.8.3 environment and reproduction pending. |
| B03 | [BugsInPy Scrapy bug 1](https://raw.githubusercontent.com/soarsmu/BugsInPy/master/projects/scrapy/bugs/1/bug.info) | Buggy `c57512fa669e6f6b1b766a7639206a380f0d10ce`; fixed `9d9dea0d69709ef0f7aef67ddba1bd7bda25d273`; `tests/test_spidermiddleware_offsite.py` | Metadata verified; Python 3.8.3 environment and reproduction pending. |
| O01 | [OpenRCA Bank](https://github.com/microsoft/OpenRCA#-installation) | Published `Bank/query.csv`, `record.csv`, dated log/metric/trace directories | Archive download, terms, individual incident IDs, and span-level labels pending. |
| O02 | [OpenRCA Telecom](https://github.com/microsoft/OpenRCA#-installation) | Same published schema for Telecom; distinct system evidence | Same archive/access/label checks; system-level truth is not automatically trace-level truth. |
| O03 | [OpenRCA Market](https://github.com/microsoft/OpenRCA#-installation) | Market/cloudbed-1 and cloudbed-2 telemetry and queries | Preserve system/cloudbed and time boundaries; do not treat correlated records as independent failures. |

The [BugsInPy framework](https://github.com/soarsmu/BugsInPy) supplies checkout/test instructions for original buggy and fixed revisions. Metadata branch inspected: `11c5f1eea954a42132cfd06bf257766a7963e0fd`; freeze this full revision and each file hash when acquiring B01–B03. Fetch its upstream test scripts, patches, setup, and project repository metadata before execution. The [OpenRCA project](https://microsoft.github.io/OpenRCA/) describes recorded failures from three software systems; its repository links the [original telemetry archive folder](https://drive.google.com/drive/folders/1wGiEnu4OkWrjPxfx5ZTROnU37-5UDoPM). The folder landing page was reachable, but archive files were not downloaded or integrity-checked during planning. Its code license does not by itself settle every dataset redistribution question.

These are a starting catalogue, not the final held-out set. Expand within the original upstream issue/PR histories, BugsInPy projects, and OpenRCA incidents to meet coverage requirements. Freeze additional IDs, full SHAs, source evidence, and selection criteria before scoring. A closed issue is not automatically a confirmed fix. Already inspected cases can be development/regression cases; never silently move them into blind evaluation.

[RCAEval](https://github.com/phamquiluan/RCAEval), Online Boutique, OpenTelemetry Demo, and Train Ticket are not substitutes for the user's requested historical incidents. Existing RCAEval controlled-fault evidence may remain labelled regression evidence; newly injected faults or newly authored demo cases are excluded from the primary evaluation.

## Evidence model and storage

Add a small manifest and executable replay adapter, not a new benchmark service. Proposed location: `agent/fixtures/production_readiness/` for redistributable metadata and `docs/evidence/issue-78/` for compact reviewed summaries. Large/restricted raw data belongs in an approved artifact store, referenced by content hash; do not commit it automatically.

Each case records: stable ID, upstream URL, retrieval date, license/terms decision, raw hash, redacted hash, repository/full buggy SHA, oracle fix SHA, original signature/log pointers, environment/dependency/image pins, incident family/system/time, split, training/index overlap status, label and rationale, two reviewer decisions, supported capability, reproduction command/status, exclusions, and evidence tier.

Separate model-visible inputs from oracle material: fix diff, answer-bearing issue comments/titles, failing tests that directly disclose the fix, `query.csv` answers, and `record.csv` labels are evaluator-only when they leak the target. Preserve original raw evidence in access-controlled storage; any redaction/projection is deterministic and logged. Do not supply a normalized “correct failure class” as an input to score that same classification.

Proposed implementation files are new and not yet present: `agent/scripts/evaluate_model_readiness.py`, `agent/tests/test_model_readiness_evaluation.py`, and a minimal manifest schema. Reuse existing graph/gateway calls and validators. A manifest with missing required provenance fails ingestion; unsupported data goes into the exclusions ledger.

## Work packages and checkpoint acceptance

| Checkpoint | Implementation / verification | Three required sourced cases | Exit criterion |
| --- | --- | --- | --- |
| 1 — Paired baseline | Freeze artifact hashes, graph revision, policies, inputs, candidate set, authorized history, and run order; execute deterministic and opt-in runs on identical bytes | B01, B02, B03 | Harness emits paired per-case results and rejects mismatched inputs/revisions. Scored outputs remain Phase 2 work. |
| 2 — Real evidence | Fetch original reports/code/telemetry; prove buggy test fails and fixed test passes where executable; reviewers verify causal labels | K01, B01, O01 incident | Distinguish report-only, reproducible-code, recorded-telemetry, and live evidence. No invented replacement signature, baseline, or fix. |
| 3 — Provenance/leakage | Audit duplicates, related commits/issues, time overlap, artifact training data, and retrieval corpus; record redaction/retention decisions | K03, B02, O02 incident | All included cases have provenance and split status. Unknown training overlap cannot be called held-out. No same incident in training/development/final test. |
| 4 — Predeclared thresholds | Save gate version, supported envelope, sample floors, scoring, resource budget, and stopping rule before final labels are inspected | K06, B03, O03 incident | Reviewer signs off frozen criteria or records unresolved decisions; no post-result relaxation. |

For O01–O03, replace the family with at least one concrete archived incident ID per system before execution; archive availability is a blocking dependency. K01–K05 support regression coverage but cannot alone satisfy independent evaluation. Every checkpoint ultimately needs at least three distinct sourced cases; repeat runs are not new cases.

## Dataset design and statistical rules

1. Keep existing #65 inputs in regression; audit actual training data and artifact manifests. If original training provenance cannot be reconstructed, label overlap “unknown” and defer independent-generalization claims for that artifact.
2. Create development and locked final-test splits grouped by incident, related fix, project/system, and time. Include a cross-project/system slice where possible. Hold history before query time; remove the exact incident and duplicates from its retrieval index.
3. Two human reviewers label cause, relevant files/incidents, allowed repair, and unsupported/OOD status without seeing model outputs. Resolve disagreements or exclude as ambiguous. An agent-produced label alone is not independent adjudication.
4. Pre-register primary metrics and paired comparisons. Count one independent incident as the sampling unit; cluster related traces/requests. Use 95% intervals for rates and incident-cluster paired bootstrap intervals for deltas. Three examples are functional coverage, never a statistical production claim.
5. Provisional sample floors: classification ≥100 independent incidents and ≥30 for each claimed class; ranking ≥100 reproduced bugs across ≥3 projects; retrieval ≥100 reviewed queries across ≥3 histories; trace ≥100 independent fault episodes across ≥3 systems plus labelled healthy exposure; patch ≥30 eligible historical repair attempts across ≥3 repositories. Report feasible subsets separately; unmet floors mean insufficient evidence.
6. Freeze budgets and thresholds below before scoring. These are proposed engineering gates, not measured results or existing accepted policy. Owner review during Phase 1 can revise them once using deployment needs, not final-test outcomes. A failed artifact can remain deferred; retraining is a separate development cycle with a new untouched final set.

## Proposed quality gates for Phase 2

| Capability | Metrics to publish | Proposed admission gate, limited to declared envelope |
| --- | --- | --- |
| Classifier | Per-class precision/recall/F1, macro-F1, confusion matrix, all-input accuracy, accepted accuracy, coverage, OOD refusals, raw learned vs effective rule results | Supported-case all-input accuracy ≥90% (abstentions count as misses), macro-F1 ≥0.85, accepted accuracy ≥95%; positive paired all-input accuracy delta with 95% lower bound >0; no critical safety regression. |
| Ranker | Candidate-generation coverage, conditional/all-input top-1/top-3, MRR, per-project paired deltas | Top-1 ≥75%, top-3 ≥90%, ≥5 percentage-point top-1 gain over baseline and 95% paired delta lower bound >0; zero invented identities/evidence changes. |
| Similarity | Precision@3, recall@3 where complete relevance labels exist, MRR, answer coverage, no-match false-positive rate, ownership failures | Returned-result precision@3 ≥80% with answer coverage ≥50% of answerable queries, no-match false-positive rate ≤5%, positive paired MRR delta with lower bound >0; zero observed ownership violations. Always show eligible/answered denominators and fixed-k precision. |
| Trace | Event precision/recall, false alerts per service-hour, latency to detection, healthy exposure, missing-baseline/OOD coverage; trace metrics only with trace truth | Event precision ≥90%, recall ≥80%, ≤1 false alert per 100 verified healthy service-hours; positive paired event-F1 delta with lower bound >0. Missing time/healthy/span truth leaves the corresponding gate unqualified. |
| Patch | Eligible-case coverage, correct allowed-template choice, proposal precision, unsafe proposals, validated success/eligible cases and /attempts, regressions and refusal reasons | ≥80% eligible historical cases achieve independently validated repair with no manual edits; paired success delta lower bound >0 for learned-benefit claims; zero observed unsafe/policy-bypassing proposals; mandatory checks pass. Model template agreement never substitutes for repair. |

Publish 95% intervals even if a point threshold passes. A sample meeting the floor does not guarantee enough power; uncertainty overlapping the required benefit means defer or collect the predeclared additional sample. Report safety failures by severity rather than averaging them into accuracy. Zero observed failures is bounded evidence, not a proof of universal safety.

PRD §15/§23 targets (including ≥5 benchmark reproductions, ≥4/5 correct minimal patches, three demos under ten minutes, and pilot acceptance targets) remain separately visible. The new per-capability gates do not replace or claim those product outcomes.

## Completion and handoff

- [ ] Source manifest, exclusions ledger, label adjudication, split hashes, training/index audit, and raw-data access/retention decisions exist.
- [ ] Each checkpoint has ≥3 concrete source IDs; OpenRCA archives and exact cases are verified, not just linked.
- [ ] Final labels/oracle fixes cannot enter model inputs; transformation tests cover leakage and mismatched paired inputs.
- [ ] Thresholds, sample sizes, supported envelope, and resource proposal are frozen and reviewed before final scoring.
- [ ] Missing historical repair evidence, human reviewers, data terms, or training provenance are named blockers with owners, not filled with synthetic evidence.

Deliver an evaluation protocol and manifests for #66/#78; leave checkboxes open until execution evidence exists. No current source file, model artifact, README result, issue status, or runtime setting is changed by writing these plans.
