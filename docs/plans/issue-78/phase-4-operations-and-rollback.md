# Phase 4 — Monitoring, auditability, and rollback

Date: 2026-10-27. Status: proposed implementation plan.
Tracking: #78 checkpoints **14–16**.
Prerequisites: [Phase 2](phase-2-model-evaluation.md), Phase 3 runtime qualification. Next: [Phase 5](phase-5-shadow-pilot-and-decision.md).

## Goal

An operator can explain a decision, detect meaningful degradation, disable model influence, restore a trusted release, and verify safe recovery. Use existing audit/run records, metrics, feedback, stores and pilot scripts. Add only fields or controls missing for these acceptance outcomes; no separate observability platform is required by this plan.

Source IDs and evidence rules are defined in [Phase 1](phase-1-data-and-acceptance.md). Reuse original report/code/telemetry bytes. Alert and crash exercises are labelled operational controls, not new historical incidents. Notification destinations and named owners must be configured before a live pilot; writing these plans does not authorize messaging anyone.

## Checkpoint 14 — Complete, tenant-safe decision evidence

**Three source cases:** K01 original image-pull report, B01 original Tornado failure, O01 original recorded incident. Add B02/B03, O02/O03 and K04 when needed to cover all actual outcome states. Do not force a real artifact to emit a desired answer just to fill a row.

Implementation tasks:

1. Inventory existing audit events, `model_results`, feedback records and `agent/raphael_agent/scripts/metrics.py`. Extend their existing serializers/schema-compatible metadata only where needed. Inspect run stores and JSON/SQLite parity before adding a new storage path.
2. Every attempted capability records correlation/run ID, source case/hash, timestamp, runtime/source revision, artifact+manifest hash or a normalized unavailable state, effective decision source, learned execution, confidence when meaningful, refusal/fallback reason, latency and baseline suitability. Record schema/gate version. Known runtime enums remain authoritative; avoid conflicting parallel labels.
3. Join reviewed outcomes by run/result ID: reviewer-confirmed cause, relevant file, repaired/refused, regression, acceptance and later rollback. Do not treat missing human feedback as a negative label or auto-train from it.
4. Verify request-scoped diagnostics under Phase 3's admitted concurrency. Cross-request errors, tenant IDs and evidence cannot mix. Metrics labels must not contain arbitrary source text, secrets, raw paths or high-cardinality customer IDs.
5. Document access/retention before ingestion. Proposed default for approved replay artifacts: raw downloaded data stays local/restricted through review and is removed within 30 days; redacted run evidence 30 days; compact aggregate reports 90 days. Source licenses and pilot requirements may require shorter periods. Keep existing recovery journals until owned work is terminal; deletion must not strand recovery. Real customer retention is a pilot-owner decision, not inherited consent.

Acceptance:

- [ ] All five capabilities and actual trained/override/abstention/disabled/unavailable/not-applicable states have schema-valid examples, with positive execution using trusted artifacts and negative controls labelled.
- [ ] 100% of evaluated runs have complete identity/version/outcome-source metadata; missing required fields fail evidence validation.
- [ ] Original-source sensitive strings found during review do not appear in durable reports/logs. Supplemental redaction sentinels, if used, are explicitly test controls, never a claim of a historical secret leak.
- [ ] Authorized operators can inspect evidence; wrong-scope requests cannot read another tenant's evidence. Test controls and real pilot authorization are reported separately.
- [ ] Expiry/deletion and recovery-journal exceptions are documented and exercised; report storage access decisions and byte-level evidence hashes.

Deliver `observability-contract.md` and compact example events; proposed new tests belong beside existing audit/metrics/store tests. Preserve existing public contracts; if a required public-field change is discovered, plan it separately through the versioned Raphael/Ignis boundary.

## Checkpoint 15 — Actionable alerts and ownership

**Three source inputs:** K01, B02 and O03. Replay each while exercising runtime-error, resource-pressure and decision-quality controls. Repeated source input is a monitor test, not a new accuracy sample.

Proposed thresholds, to freeze with Phase 1 and the named operator:

| Signal | Condition | Expected action |
| --- | --- | --- |
| Ownership/provenance/policy violation | Any confirmed occurrence | Stop new model-influenced work for affected scope immediately; page owner through an approved destination; retain redacted evidence |
| Runtime unavailable/error | >1% of ≥100 attempts in 5 minutes, or 3 consecutive failures at low traffic | Mark capability degraded, notify owner, use deterministic fallback/refusal; distinguish disabled/not-applicable from errors |
| Memory / CPU / latency | Memory >80% of limit for 5 minutes, CPU saturation for 5 minutes, or p95 exceeding the Phase 3 budget for 3 windows | Investigate/limit admission; disable affected capability if service cannot remain within its envelope |
| Refusal/fallback change | >10 percentage-point change versus matched baseline, ≥100 comparable calls in 30 minutes | Investigate input mix, baseline gaps and model version; refusal changes alone are not proof of lost accuracy |
| Reviewed quality | Primary metric falls below frozen gate on a sufficiently sized matched reviewed sample, or any confirmed harmful recommendation | Pause affected capability; immediate harmful-action stop does not wait for the sample floor |
| Cleanup/recovery | Owned cleanup exceeds current executor deadline or uncertain publication remains unresolved | Operator reconciliation; never retry uncertain remote mutation blindly |

Quality alerts require reviewed labels and comparable incident mix; unlabelled drift is an investigation signal, not measured accuracy. Alert silence at zero traffic is not health proof; include a bounded installed-runtime health check without patch/publication effects.

Acceptance:

- [ ] Each alert has a named human owner, approved delivery route, severity, metric query, minimum denominator/window, runbook link and recovery condition; unresolved ownership blocks the live pilot.
- [ ] Every proposed signal is exercised with ≥3 original source inputs and separately recorded operational triggers; correct alert and clear/recovery are observed.
- [ ] Proposed detection budget: configured alert within one evaluation window plus 60 seconds; immediate safety stop prevents subsequent model influence before the next action boundary. Measure both timestamps.
- [ ] No duplicate alert storm for one continuing condition; low-volume gaps are visible and not represented as passing quality.

## Checkpoint 16 — Disable, restore and reproduce

**Three source cases:** B01, B02 and B03, supplemented by K01 for image provenance and an O03 case for baseline behavior. Run each with the exact evaluated release and with inference disabled; use a previously approved trusted release only when one actually exists.

Runbook to implement and exercise:

1. Identify scope, running revision, process/worker topology and affected capability. Record the incident and decision boundary without copying secrets.
2. Disable new model influence using the operator-owned service configuration (`RAPHAEL_MODEL_ENABLED=0` for the existing global control), and explicitly restart/reload every process that reads it. An export in another shell does not update a server. No per-capability kill switch is assumed; use the current global stop if finer control is absent.
3. Cancel or drain affected in-flight model-influenced jobs according to existing safe boundaries. Recheck policy before downstream proposal/publication; do not assume changing the flag reverses an already made decision. Uncertain mutation follows existing reconciliation rules.
4. Verify running process version/config, deterministic fallback or refusal and no new model execution. Check queues, leases, owned sandbox cleanup and health.
5. Restore a prior approved runtime/artifact combination with matching trust registry, Python/ML versions and immutable bytes. Never replace `model.joblib` alone or modify a hash to accept it. If no previously approved pair is available, remain inference-off; a fabricated rollback target is not a passing restoration drill.
6. Replay saved redacted inputs with the original baseline/history snapshot and source files. Match policy/refusal/classification/canonical candidate outcomes; allow documented numerical tolerances and deterministic tie rules. Reproducing a floating score is not enough to reproduce the decision.
7. Complete owner review before re-enablement. Record cleanup and resulting capability state.

Proposed acceptance budgets: new model influence stops within 60 seconds of operator execution; supported restore finishes within 15 minutes; model-disabled core health within Phase 3's restart budget. Existing uncertain-side-effect reconciliation may take longer and remains an explicit incident, not a successful automatic recovery.

- [ ] ≥3 real-source replay drills prove disable/restart and no further influence; observed in-flight behavior is documented.
- [ ] One actual approved prior pair is restored and tested on all three sources, or restore remains unqualified while safe-disable passes.
- [ ] Canonical decisions and evidence identities reproduce from versioned inputs; journals/cleanup remain valid and no duplicate branches/PRs occur.
- [ ] A second operator can follow the runbook from recorded commands/config references; no credentials are embedded.

## Delivery and handoff

Expected seams: existing graph model audit, run stores, `record_feedback.py`, `metrics.py`, `pilot_go_nogo.py`, service startup/configuration and executor cleanup. Test redaction, event completeness, wrong-scope access, degraded-state detection and real restart/restore behavior. Do not write tests that merely repeat a serializer's implementation.

Deliver operator runbook, event/metric definitions, alert exercise log, retention/access policy, restore inventory and per-case drill results. Phase 5 admission requires named owners and executed controls; a Markdown runbook alone does not close checkpoints 14–16.
