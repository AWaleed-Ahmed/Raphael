# Phase 5 — Shadow evaluation, supervised pilot, and rollout decision

Date: 2026-10-27. Status: proposed implementation plan; no partner/environment has been authorized by this document.
Tracking: #78 checkpoints **17–21**.
Prerequisites: [Phase 1](phase-1-data-and-acceptance.md), [Phase 2](phase-2-model-evaluation.md), Phase 3 runtime qualification, [Phase 4](phase-4-operations-and-rollback.md).

## Goal and evidence boundary

Decide whether each capability should remain deferred, continue a limited pilot, or expand within an explicitly reviewed scope. Historical replay prepares the machinery; only authorized observed incidents and reviewed operating outcomes qualify the live shadow/pilot.

Use existing `docs/pilot-install.md`, `docs/pilot-acceptance.md`, `docs/pilot-week-runbook.md`, permission matrix, metrics, feedback and go/no-go tooling. Preserve PRD §23 requirements and versioned Raphael/Ignis contracts. Correct dated implementation status only when new evidence supports it; do not silently lower acceptance targets.

## Source and scenario allocation

| Evidence set | Sources | Permitted claim |
| --- | --- | --- |
| Historical rehearsal H1/H2/H3 | B01 Tornado, B02 pandas, B03 Scrapy original failing revisions | Replay isolation, paired analysis, evidence handling, disable/rollback rehearsal; not a customer Kubernetes repair pilot |
| Kubernetes rehearsal K1/K2/K3 | K01 Volcano, K03 Jenkins, K06 Bitnami original reports; only Phase 2-qualified reproductions where applicable | Historical diagnosis/refusal and supported repair evidence; report-only cases cannot become successful repairs |
| Telemetry rehearsal T1/T2/T3 | O01 Bank, O02 Telecom, O03 Market exact frozen incident IDs | Recorded telemetry behavior and paired reporting; not current access to the original operating systems |
| Live acceptance L1/L2/L3… | Actual run/delivery IDs from an authorized pilot's original repository SHA, observed signature, telemetry and reviewed outcome | Live shadow or supervised acceptance, labelled with real incident provenance |

L1/L2/L3 are required future evidence slots, not made-up fixtures or already selected incidents. Their concrete source IDs cannot honestly be supplied without an authorized pilot. Require ≥3 distinct real eligible incidents for each checkpoint exercise and the larger floors below for quality claims. No substitution with injected demo failures, duplicated public reports, or a borrowed company's identity.

## Checkpoint 17 — Define the pilot before collecting results

**Three-case rehearsal:** H1/H2/H3 validate the protocol and result schema. **Live requirement:** identify eligibility and evidence contracts that can admit L1/L2/L3 without cherry-picking.

Tasks and acceptance:

- [ ] Record named partner/operator/reviewer, authorized repositories/full SHAs, cluster/context, tenant/company/client scope, read-only production observer permissions, approved sandbox access, data retention, integration choices and incident budget.
- [ ] Explicitly verify production access cannot mutate workloads or read Secret payloads; Ignis receives only authorized sandbox permissions. Public test tenants do not count as this check.
- [ ] List candidate capabilities and failure classes. Only Phase 2 quality passes, Phase 3 deployment passes and Phase 4 operational passes are eligible. Unsupported capabilities stay off; passing ranking does not approve patch selection.
- [ ] Proposed shadow window: at least 14 days and ≥30 independently reviewed eligible incidents, with ≥3 represented services/repos or an explicitly narrower declared envelope. Each enabled capability must also meet Phase 1 sample floors across its independent evidence and report the live subset separately. Extend for insufficient volume; no calendar-only pass.
- [ ] Keep PRD's ≥5 real eligible dry-run failures, ≥5 benchmark reproductions/≥4 correct minimal validated patches, and three consecutive full demos under ten minutes as separate product gates. Record human acceptance (target ≥60% of published pilot PRs when publication is authorized); dry-run suggestions cannot count as accepted PRs. Other PRD product targets retain their own denominators.
- [ ] Freeze stop conditions, alert route, owner availability, rollback pair and proposed operational budgets before collection. No unnamed “on-call owner” is a completed criterion.

The user has requested planning; implementation authorization later does not automatically supply partner access, paid resources, external provider budgets or publication permission. Record missing concrete dependencies; do useful offline work while they remain unresolved.

## Checkpoint 18 — Shadow without influencing the active workflow

**Three historical proof inputs:** H1/H2/H3 for shadow isolation, plus T1/T2/T3 for actual telemetry. **Live proof:** L1/L2/L3 and the full frozen shadow sample.

Implementation tasks:

1. Inspect the existing opt-in gateway behavior: it influences graph state, so setting it on in the primary run is not shadow mode. Build the smallest isolated observer/evaluator path, preferably using a redacted frozen evidence snapshot and a separate model result artifact/store namespace.
2. Keep the active deterministic run's evidence, diagnosis, candidate ordering, patch, policy, terminal state and downstream actions unchanged. The shadow branch receives no production-mutating or GitHub-writing credentials and cannot enqueue sandbox/patch/publish actions. Use actual artifact predictions, not recorded model answers.
3. Budget shadow CPU/memory separately so it cannot degrade the primary service. Shared store/history writes are prohibited; authorized read snapshots are versioned. Labels become available to the evaluator after the predictions are sealed.
4. Compare primary results with shadow counterfactual suggestions and later engineer-confirmed outcomes. A shadow suggestion has no live repair outcome; if separately reproduced in an authorized sandbox, label that separate evaluation explicitly.

Acceptance:

- [ ] On all three rehearsals, comparison with observer absent/present proves canonical active-run decisions/actions identical; count zero shadow model-to-primary state writes, sandbox requests, patch attempts and GitHub mutations.
- [ ] Live L1/L2/L3 and subsequent sample retain actual input/revision/timing/ownership, independent labels and paired results; no fake incidents fill volume gaps.
- [ ] Resource overhead respects the chosen primary and observer budgets; loss of shadow monitoring cannot change primary decisions.
- [ ] Failed model predictions and no-match/refusal cases remain in the report; model and reviewer access separation is verified.

Expected seams: standalone evaluation/replay around existing collectors and `ModelGateway`, with narrowly tested configuration/store boundaries. Any production graph code change requires the applicable ecosystem/LangGraph skills at implementation time. Do not implement a second orchestration architecture.

## Checkpoint 19 — Publish paired evidence and uncertainty

**Three minimum report slices:** H1/H2/H3 during rehearsal; O01/O02/O03 for per-system telemetry; L1/L2/L3 plus the full live sample for actual acceptance.

Deliver a report for each capability with frozen gate version, source IDs, trained vs rule behavior, wins/ties/regressions, accepted/abstained/blocked/fallback denominators, 95% incident-level intervals, operational cost, resource failures, safety violations and human-reviewed outcomes. Publish per-repository/system/class slices and candidate-generation/healthy-baseline coverage.

Acceptance:

- [ ] Independent recomputation from sealed predictions reproduces all summary counts/metrics; derived tables link their exact evidence hashes.
- [ ] All reviewed incidents, exclusions and unresolved labels are accounted for; retrospective eligibility changes require an explicit separate analysis.
- [ ] Historical replay, controlled runtime perturbation, recorded telemetry, live shadow and actual validated repairs appear as distinct evidence tiers.
- [ ] No aggregate hides a failing class/capability or small sample. No observed trained benefit means no learned-benefit claim, even if complete-system rules succeed.
- [ ] Public reports/README contain only approved redacted aggregates and source links; sensitive raw evidence stays in authorized storage. Updating GitHub or messaging people requires its own task authorization.

## Checkpoint 20 — Admit only passing capabilities to a supervised pilot

**Three rehearsal checks:** replay H1, H2 and H3 through admission logic and verify that deliberately unmet evidence gates refuse admission. These are gate controls over real inputs, not fabricated positive model results. **Live:** L1/L2/L3 and required samples support the actual decision.

Tasks:

1. Produce a five-row admission matrix: evaluated envelope, quality gates, sample/uncertainty, runtime profile, operational readiness, source evidence, reviewer, decision and expiry/review date.
2. Reject admission on any critical safety failure, unresolved ownership/provenance/fidelity gap, failed quality/resource gate, missing owner/rollback target or insufficient independent evidence. Passing one capability cannot waive another's gate.
3. Start with one qualified capability and explicitly scoped repositories/services in dry-run supervised assistance. Ranking is only a candidate, not pre-approved. If existing enablement is global, do not claim independent per-capability rollout; implement and test minimal operator-owned selection or keep the global runtime off.
4. Stage expansion only after observed benefit at the original thresholds. Permission for read-only assistance does not authorize patch publication. Live draft PRs require separate explicit approval, scoped credentials, proven classes and human review. Never auto-merge or mutate production.

Acceptance: gate evaluator refuses every incomplete matrix; real pilot starts only with actual authorization and all applicable passes. Capture effective service configuration after restart; an edited `.env` or an unset-by-default field is not proof of what is running.

## Checkpoint 21 — Exercise stopping and make the rollout decision

**Three real-input drills:** H1/H2/H3, supplemented by original Kubernetes/telemetry evidence where their controls apply. **Live exercises:** at least three L-series incidents/drills are linked to actual operator timestamps and safe resulting states; drill perturbations are labelled separately from original incident causes.

Stop immediately for confirmed ownership leak, unsafe/prohibited proposal/action, unverified artifact, missing required provenance, or a validity-affecting sandbox fidelity gap presented as success. Stop/limit for Phase 3 budget breaches and Phase 4 alert conditions; reviewed quality decline follows the frozen denominator and severity rules. Harmful outcomes do not wait for statistical significance.

Acceptance:

- [ ] Disable during active observed work and demonstrate no subsequent model influence or prohibited downstream action; in-flight cancellation/drain follows the documented boundary.
- [ ] Execute restoration of the approved trusted pair or remain safely inference-off if no qualified restore exists. Owned resources and uncertain remote effects are reconciled explicitly.
- [ ] An operator reviews outcomes and records one decision per capability: **deferred**, **continue limited pilot**, or **expand within named envelope**. Include remaining failures, incidents covered, version, sample limits and next review trigger.
- [ ] Repeated runs/duplicate webhook deliveries do not create duplicate branches/PRs. Proof comes from the actual authorized delivery path; offline replay alone cannot establish it.
- [ ] Product acceptance, inference acceptance, publication approval, and broad production claims remain distinct. Default-off stays unless a separately authorized change explicitly changes it.

## Deliverables and issue closure

Deliver `shadow-protocol.md`, reviewed scope/access record, paired shadow/live report, five-row admission matrix, drill evidence, operator runbook links and a concise README summary of passed scope and unresolved limits. Proposed artifacts live under `docs/evidence/issue-78/`; raw customer material never enters Git automatically.

Checkpoint closure requires actual evidence, not plans. #66 can close on its specified reproducible evaluation/recommendation even when the recommendation is defer; #78's unmet live acceptance remains open. Only close #78 when every applicable criterion has executed proof or the human owner explicitly revises its scope with an auditable decision. Do not silently mark blocked pilot work “complete” because public replays passed.
