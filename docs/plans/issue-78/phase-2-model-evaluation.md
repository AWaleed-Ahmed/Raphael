# Phase 2 — Model evaluation and supported repair validation

Date: 2026-10-27. Status: development replay implemented; final acceptance pending.
Execution: [Phase 2 development report](../../model-readiness-phase-2.md).
Tracking: #78 checkpoints **5–9**, evaluated through #66.
Prerequisite: [Phase 1](phase-1-data-and-acceptance.md); next: Phase 3 runtime qualification.

## Goal

Determine which existing capabilities measurably improve the current deterministic graph on original, independent real cases. A useful negative result is “keep this capability deferred.” Do not retrain, tune on final labels, add general-purpose repair generation, or weaken any safety gate to obtain a positive score.

Use the Phase 1 source catalogue and frozen thresholds verbatim. Source IDs K01–K06, B01–B03, O01–O03 refer to that catalogue. Three named cases per capability are minimum functional coverage; the larger sample floors and intervals govern quality claims.

## Architecture and evaluation protocol

1. Run from an immutable clean checkout with the packaged inference extra and trusted artifacts. Capture Python/library versions, artifact/manifest hashes, source hashes, contracts and Ignis revision, machine profile, seed, commands, and input hashes.
2. Extend the planned `agent/scripts/evaluate_model_readiness.py` around the existing `ModelGateway` and graph. Keep the current #65 replay as regression proof. Do not pass projected benchmark answer features into the new ranking or classification evaluation.
3. The primary comparison is the current deterministic configuration versus the opt-in complete configuration on identical evidence. Add per-capability opt-in ablations to attribute benefit. Use the same external LLM-off, learning-off, publication dry-run policy and authorized history in every arm.
4. Record trained-estimator execution, effective trained decisions, deterministic overrides, abstentions, policy blocks, unavailable fallbacks, and not-applicable calls separately. If rules determine every answer, do not claim learned classification benefit even when an estimator executes.
5. For classification/trace ablations, use actual artifact outputs as a secondary diagnostic; raw predictions cannot bypass graph gates or count as user-visible success. For retrieval, compare against the frozen existing non-model assistance actually present; state if its baseline returns no candidates.
6. Make predictions before opening evaluator-only answers. Run offline evaluators after prediction files are sealed and hashed. Compare each paired incident, not unrelated averages; preserve wins, ties, regressions, exclusions, timeouts and failures.

## Checkpoint 5 — Failure classification

**Outcome:** verified causes are correctly classified within the declared supported taxonomy, with visible uncertainty and measurable value beyond rules.

**Source cases:** K01 image-pull report, K04 pooler/security-context startup failure, K05 OOM report. These are regression seeds; select independent equivalent reports for final scoring. K03 is an important ambiguity control: a pull-state marker does not by itself identify the reaper defect's cause.

Tasks:

- Fetch full bounded original report/evidence, affected revision and resolution; reviewers separate observed symptom from confirmed cause. A security-policy error is not automatically a missing ConfigMap key.
- Use the normal collector and classifier call site in `agent/raphael_agent/graph/nodes.py`. Exclude known answer markers inserted by earlier fixture adapters.
- Evaluate in-domain, unsupported, missing-evidence, and unfamiliar cases separately. Map unsupported taxonomy to abstention/escalation rather than forced diagnosis.
- Report per-class confusion, macro-F1, supported all-input accuracy, accepted accuracy, coverage, errors, rule/model contribution, and the Phase 1 paired improvement interval.
- Evaluate probability calibration only for meaningful trained probabilities: Brier score and reliability plots; ECE bins require enough observations (target ≥20/bin) and are otherwise marked insufficient. Any calibration fit uses development data only. Effective rule outputs are not calibrated model probabilities.

Acceptance: all Phase 1 classifier gates and sample floors pass; original deterministic blocks remain; zero prohibited patch/proposal calls for unsupported/blocked cases. Three replayed reports alone cannot qualify the learned classifier.

## Checkpoint 6 — Candidate ranking

**Outcome:** prioritize actual fix locations using candidates produced from actual failures.

**Source cases:** B01 Tornado websocket failure, B02 pandas dtype failure, B03 Scrapy offsite-middleware failure. Original BugsInPy metadata pins buggy/fixed revisions and relevant test paths.

Tasks:

- Run each upstream reproduction in its required isolated legacy Python environment. Archive commands, dependency/image hashes, unedited test output and exit status. Confirm failure on the buggy revision and pass on the fixed revision before accepting the oracle.
- Feed captured failure evidence and the buggy checkout through Raphael's actual localization path. Hold upstream fix filenames/diff and answer-bearing test metadata out of model-visible inputs. Do not manufacture a production stack or derive candidate features from the expected fix.
- Freeze the graph-generated candidate list once per incident; compare unchanged ordering versus model ranking. Preserve candidate path, line, symbol, evidence reference and mapping method.
- Count candidate-generation misses as misses in all-input top-k; also publish conditional ranking metrics where the true fix file was generated. Multi-file fixes need a predeclared relevance rule and file-level primary metric.
- Test unavailable/ambiguous stack mapping honestly. If this pipeline cannot produce source candidates for a case, record that limitation; gateway-only ordering of oracle-built candidates is not end-to-end localization proof.

Acceptance: Phase 1 top-1/top-3, improvement and sample gates; no identity/evidence mutation. Python benchmark success qualifies localization/ranking only, not Kubernetes patch repair.

## Checkpoint 7 — Incident similarity

**Outcome:** retrieve useful earlier incidents while respecting ownership and rejecting poor matches.

**Source cases:** K01, K02 and K03 as regression queries/history candidates; extend with independently reviewed related and irrelevant reports before freezing the final test. Reusing the exact query as an indexed document is prohibited for generalization scoring.

Tasks:

- Form histories from earlier independent incidents and create labels with two reviewers: relevant cause/fix, superficially similar symptom, irrelevant, or no match. Mask query answers. Hold exact incident, duplicate text, shared fix thread and later reports out of its index.
- Freeze a compatible trusted index release built from approved pre-query history; any rebuild follows #63's registry/hash/version and #64's ownership rules. Holdout labels/queries never enter the build. If the current release index contains the exact query or cannot represent the authorized history, it remains a regression-only artifact; do not relabel it as qualified or load an unregistered replacement.
- Test at least three distinct histories with original reports. Public-source ownership bindings are test control metadata, not proof of actual customer tenancy; production ownership requires authorized identities in Phase 5.
- Exercise `incident_scope.py`, scoped catalog retrieval, and the production graph, not a separate similarity function. Cross-owner records must not be returned or influence ranker history features.
- Report precision@3 with actual returned-count denominator and a fixed-k companion measure, MRR, complete-label recall where available, query coverage, no-match false positives, and paired relevance improvement. No-match queries never disappear from the denominator.

Acceptance: Phase 1 relevance/no-match/benefit gates and sample floors; zero observed ownership violations. If authorized real history is unavailable, report public historical retrieval only and defer tenant-history usefulness claims.

## Checkpoint 8 — Trace anomaly

**Outcome:** detect verified fault episodes and quantify false alerts using existing telemetry.

**Source cases:** one frozen original episode each from O01 Bank, O02 Telecom, and O03 Market; expand to the frozen sample floor. Download actual OpenRCA archives and identify files, timestamps and incident IDs before scoring.

Tasks:

- Read dataset schema, clocks, units, missingness and root-cause records. Ground truth stays outside model inputs. Preserve native trace/service/request relationships; do not invent spans or error/status values for missing fields.
- Verify whether each incident supplies individual trace truth, only event-level truth, or no compatible label. Use the existing model only where the recorded fields support its input contract. A general RCA benchmark score is not automatically anomaly accuracy.
- Build a healthy baseline only from a documented clean earlier interval with matching service/environment/operation/repository and operator-approved ownership. If a required identity cannot be verified, baseline remains missing and expected behavior is abstention. Do not mark arbitrary pre-fault traces “verified healthy.”
- Predeclare alert aggregation and matching: group correlated anomalous traces by service/operation into episodes (proposed 60-second grouping); count one true positive per labelled fault within the documented fault interval; count unmatched alert episodes as false alerts. Freeze timing windows on development data only.
- Report event precision/recall/F1, service-hours of verified healthy exposure, false-alert rate, detection delay (event-to-available-telemetry delay separately), missing-baseline coverage, per-system slices, and trace-level metrics only where labels support them.

Acceptance: Phase 1 gates, sample floor and positive paired event-F1 benefit. Missing healthy exposure or event truth blocks those gates. The current model may legitimately fail compatibility or coverage; record the failure instead of adapting labels to its predictions.

## Checkpoint 9 — Patch selection and repairs

**Outcome:** independently validate useful, minimal supported repairs on original historical failures.

**Source triage cases:** K01, K02, K06. These are original source candidates, not three certified runnable or supported repairs. K04 and K03 additionally test refusal of security relaxation or unsupported controller-code changes. If triage yields fewer than three eligible original cases from distinct repositories, this checkpoint remains blocked until further original reports and linked fixes are verified.

Tasks:

- Resolve exact broken manifest/chart/app revision and original environment from report and fix history. Verify the failure before attempting repair. Capture real observed signature, target identity, and evidence chain through Ignis.
- Accept only concrete generators already implemented in `agent/raphael_agent/patch/templates.py`. A template name is not proof its generator can produce a patch. Missing ConfigMap values must not be invented; probe-path/timeout suggestions must still pass actual generator constraints.
- Image repair requires independently observed pull absence and an authorized healthy baseline for the same owned repository/workload/container; knowing a maintainer's later image tag is not sufficient authorization. No safe baseline means refusal.
- Hide maintainer fix diffs during proposal. Compare against their intended outcome after the generated patch is sealed; exact textual equality is unnecessary, minimal safe behavior is required.
- Run original failure reproduction, mandatory validation, source/repository regression checks, independent Ready/functional checks, signature clearance and cleanup. Record full fidelity, required Secret-coverage behavior and all substitutions. `full_validation=false` must never be reported as full production fidelity; validity-affecting gaps prevent acceptance.
- Keep eligible coverage, attempted repair success, all-eligible success, refusals, unsupported cases, unsafe proposals and unrelated regressions separate. Model selection alone is advisory; do not count the maintainer patch applied by the evaluator as a Raphael repair.

Acceptance: ≥3 independent original repository cases first, then Phase 1 patch sample and quality gates for a capability claim. The PRD ≥5 reproductions/≥4 correct minimal patches remains a separate minimum product demonstration. No new patch family or general Python repair is implied. No manual edit may turn a failed proposal into a scored success.

## Implementation slices and validation

| Slice | Expected seams | Verification |
| --- | --- | --- |
| Case acquisition/reproduction | Planned manifest adapter plus isolated upstream test commands | Original hashes and fail-before/pass-after evidence; unavailable images/dependencies recorded as exclusions |
| Paired evaluation | Existing gateway/graph plus planned `evaluate_model_readiness.py` | Same input/policy/candidate hashes across arms; oracle never loaded into prediction inputs |
| Scoring and report | Planned evaluator tests, compact per-case JSONL, Markdown summary | Independently recompute metrics/intervals; schema-valid outputs; stable paired identities |
| Regression protection | Existing blocked-model, gateway, graph, provenance, isolation and kind tests | No safety regression; appropriate agent/dispatch/contract/E2E checks for actual changed code |

Use negative stubs only for malformed-output/blocked-path controls. Positive capability proof must execute the real trusted artifacts. No new LangGraph architecture is needed; any actual graph-code edit must follow the ecosystem and LangGraph skills during implementation.

## Outputs and exit decision

- [ ] `evaluation-summary.md` and per-case machine-readable predictions, hashes, metrics, intervals, exclusions and outcome source.
- [ ] Five-row capability acceptance matrix: passed / failed / insufficient evidence / blocked, with the exact claimed envelope and frozen gate version.
- [ ] #66 receives linked evidence; no claim that better template agreement is better repair accuracy.
- [ ] At least three sourced cases are executed for each relevant checkpoint; final sample deficits stay open.
- [ ] Capabilities without demonstrated benefit stay off; failure of one does not get hidden by another's aggregate score.

Runtime testing may investigate failed capabilities safely, but only those passing this phase can proceed toward pilot admission.
