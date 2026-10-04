# Raphael #30 implementation plan

Planning date: 2026-10-04. Raphael branch: `docs/contributor-handoff`.

Status: implemented and reviewed on `docs/contributor-handoff`. Ignis [PR #18](https://github.com/AWaleed-Ahmed/Ignis/pull/18) is merged and annotated `contracts-v1.3.0` is published. Raphael pins and snapshot are updated together; hosted Raphael mock/kind verification remains before merge.

## Goal and assumptions

Raphael should identify required Secret references that the authorized synthetic fixtures cannot satisfy. A covered workload must remain eligible for the existing repair flow. Optional references, missing coverage reports, and incomplete evidence must not cause a new structural Secret refusal.

- Use the explicit operator-selected fixture set already propagated by both execution paths. An unset selection means no fixtures are selected; a Secret name does not authorize a fixture.
- Secret names and key names may be recorded. Secret values and value hashes must not enter coverage reports, run records, model input, logs, or artifacts.
- Coverage describes the sandbox's synthetic fixtures. It does not establish whether a Secret exists in production.
- Retain the existing textual `production_secret_required` safety rule and its precedence. Introduce the distinct `unresolved_secret_dependency` reason for structural evidence.
- Keep Raphael implementation on this branch. Ignis implementation belongs on its own development branch, coordinated with the existing Prompt B owner before shared-path edits. The available Ignis checkout is on `fix/kubectl-cluster-backend-name`; refresh and inspect the intended Ignis base before implementing.
- Review the proposed public contract and hosted Ignis results before merge or tagging, as required by the handoff. Raphael pins follow the approved release.

## 1. Correct the private report validation prerequisite

**Problem:** the graph emits reasons and attempt statuses the escalation schema rejects, while the JSON and SQLite stores serialize reports without schema validation.

1. Inventory every `_escalation` producer and its current reason/status, including diagnosis-only, textual Secret refusal, privileged/host refusal, and patch/validation errors. Compare them with `contracts/agent/escalation_report.json` and the run-record schema.
2. Record an explicit private-schema decision: retain distinct `production_secret_required`, `privileged_or_host_access`, and `diagnosis_only` reasons where they reflect existing intentional behavior; allow `completed` for an attempt that completed diagnosis without proposing a fix. Do not replace an existing reason with a generic label merely to fit the enum. Add the new structural reason when its analyzer is integrated.
3. Validate a non-null escalation report against the schema at the shared durable-record preparation boundary, before either JSON or SQLite writes. This is a targeted report validation change, not a blanket requirement that every historical or partially constructed run satisfy the full run-record schema.
4. Reject an invalid new report without overwriting a previously valid record. Validate before SQLite commit as well as before JSON serialization. Existing persisted records remain readable; migration is a separate decision if one is needed.
5. Ensure the caller handles validation failures through a bounded system-error path without repeatedly attempting to save the same invalid report. Verify terminal dispatch cleanup still happens.

**Files to inspect/edit:** `contracts/agent/escalation_report.json`, graph escalation producers, `agent/raphael_agent/store/patch_content.py` (shared durable preparation), JSON/SQLite stores, and persistence/report tests.

**Verify:** schema-valid real reports for each producer; unknown reason and unknown attempt status rejected; both stores preserve an existing record after rejection; original refusal reason retained; no Secret values in persisted reports.

**Checkpoint:** review the producer/schema mapping and validation-failure behavior before adding structural coverage integration.

## 2. Persist successfully applied fixture inventory in Ignis

1. Have fixture loading return the renderable Secret YAML and separate metadata containing only object names and key names. Keep values in the local application path; do not use the rendered Secret YAML as a coverage artifact.
2. After successful fixture application, store the applied inventory against the actual sandbox namespace and selected fixture set in the sandbox registry and SQLite record. Coverage must use this saved inventory rather than rereading the fixture file.
3. Treat an application error or partial application as incomplete/unknown inventory. A failed apply must never produce a complete inventory based solely on the attempted YAML.
4. A fresh sandbox with no selected fixtures can record a known empty fixture inventory. Restored records from older versions that lack inventory are unknown, not known empty. Distinguish these cases explicitly.
5. On restart, restore the saved names/key inventory. Changing a fixture file after sandbox creation must not change that sandbox's recorded coverage. Discard the inventory with the sandbox during terminal cleanup.

**Ignis locations:** `controller/src/fixtures.rs`, `controller/src/domain/service.rs`, `controller/src/state/registry.rs`, `controller/src/state/sqlite.rs`, and fixture-application implementations in `controller/src/k8s/`.

**Verify:** successful apply, failed/partial apply, explicit no-fixture selection, old persisted record, restart with a changed fixture file, multiple Secrets, and terminal deletion. Inspect registry, SQLite, and artifacts for value leakage.

## 3. Evaluate references from the final rendered workload

Extract references from the same rendered workload used for application, after namespace mapping. Match against the saved inventory for that sandbox namespace. Do not scan raw manifest excerpts with a regex or infer coverage from `dependencies_available`.

| Reference | Required coverage | Optional behavior |
|---|---|---|
| `env[].valueFrom.secretKeyRef` | Referenced object and specific key | Missing object/key never triggers structural refusal when `optional=true` |
| `envFrom[].secretRef` | Referenced object; no individually specified key requirement | Missing object never triggers structural refusal when optional |
| `volumes[].secret` with `items` | Referenced object and every listed key | Respect volume optionality |
| `volumes[].secret` without `items` | Referenced object | Respect volume optionality |
| Same env references in init containers | Same rules as ordinary containers | Preserve the init-container identity |
| Projected Secret sources, ephemeral containers, or unsupported workload shapes | Support explicitly with tests, or mark unknown | Never turn an unsupported shape into an inferred missing requirement |

Each reference retains workload kind/name, sandbox namespace, container kind/name or volume identity, Secret name, optional key, optionality, and evaluation status. A volume is a Pod-level reference; do not invent a container name for it. Parse supported Pod templates structurally for Deployment, StatefulSet, DaemonSet, Job, CronJob, and Pod; unsupported templates make completeness explicit.

Use these meanings:

- `covered`: the required object/key is present in complete applied fixture metadata.
- `missing_object`: the object is absent from complete applied fixture metadata; this is not a statement about production.
- `missing_key`: the object is in complete applied metadata but the requested key is absent.
- `unknown`: inventory/report is unavailable or incomplete, or the reference cannot be interpreted safely.

**Proposed bounds for review:** at most 256 reference entries, 128 applied Secret objects, and 1,024 key names in the inventory, plus a total serialized-report byte limit. Use fixed limits rather than adding configuration for this task. Truncation is deterministic, reported explicitly, and makes coverage incomplete; omitted entries must not be presented as covered or missing.

**Verify:** nested Pod templates, multiple workloads/containers, duplicate references, namespace mapping, optional missing keys/objects, init containers, volume item lists, unsupported forms, and every truncation boundary.

## 4. Define and review the public fidelity addition

Propose an optional `secret_coverage` object on the fidelity report, with an internal format version, completeness flag, bounded reference entries, and an incomplete/truncated indicator. The applied inventory is persisted privately in Ignis; the public report needs only the reference evaluations required by Raphael.

1. Define field names, enums, maximum sizes, and exact namespace/workload identity rules in Ignis's contract and typed models. Keep the existing score/checklist/material-gap fields compatible.
2. Make new Ignis accept restored old state and make new Raphael accept fidelity reports without the addition. Absent data becomes unknown. Closed older schemas may reject the new property, so test that limitation and coordinate deployment; an optional field does not guarantee old consumers accept it.
3. Define how missing required coverage contributes a material gap and keeps `full_validation=false`. Optional-only missing references must not create a required-dependency gap. Unknown/incomplete coverage must not count as a proof of complete Secret fidelity.
4. Review the relationship to `dependencies_available` and the fidelity score; do not silently reinterpret that boolean as proof of Secret coverage.
5. Run contract/schema tests and drift checks, then publish the candidate diff and hosted results for review. The handoff proposes `contracts-v1.3.0`; confirm that version remains available and appropriate before releasing.

**Done when:** the contract shape, completeness semantics, rollout compatibility, and release sequence have been reviewed against the test evidence.

## 5. Carry coverage into Raphael and gate patching

After the approved Ignis release, update the vendored sandbox contracts, `CONTRACTS_VERSION`, and all relevant `IGNIS_REF`/runtime pins together. The implementation now pins both the contract snapshot and workflow runtime to `contracts-v1.3.0`.

1. Preserve the bounded, redacted coverage object from the deploy response in private run state before diagnosis. Dispatch currently retains rendered files only in its ephemeral patch store; do not rely on those files remaining available after restart.
2. Integrate a shared structural evaluator into direct and dispatch execution. Dispatch receives coverage during deployment before `_after_observe` diagnoses; the direct graph diagnoses before reproduction, so it must evaluate the later coverage after deployment and before patch generation.
3. Escalate with `unresolved_secret_dependency` only when authoritative coverage establishes an uncovered required reference. The implementation requires a supported report version and complete inventory/reference evaluation before this new refusal. Missing, old, malformed, or truncated reports remain unknown and do not trigger the new structural rule.
4. Keep textual `production_secret_required` and existing immutable safety blocks ahead of the structural rule. No classifier, model, or patch generator may bypass an established block.
5. A fully covered control must continue to the existing reproduction, diagnosis, patch, and validation gates. A Secret reference alone must not authorize a repair or alter #34 image provenance.
6. Include bounded names/keys and workload references in the escalation evidence and next checks. Add the new reason deliberately to the private report schema and any relevant diagnosis/run-state contracts.
7. Preserve coverage through JSON/SQLite storage, dispatch restart, action replay, and terminal cleanup. Reacquiring patch manifests must not discard or fabricate the coverage assessment.

**Verify:** direct and dispatch parity; structural refusal without textual decoration; covered control proceeds; optional-only control proceeds; unknown/legacy reports do not structurally refuse; textual rule wins when both apply; blocked paths make zero model/proposal calls; persisted reports validate.

## 6. Test cases and evidence to record

| Case | Expected result | Evidence source |
|---|---|---|
| Required `secretKeyRef`, object/key applied | Covered; proceed to other repair gates | Unit/mock plus kind workload |
| Required object absent | Missing object; structural escalation with complete evidence | Unit/mock plus kind startup failure |
| Object exists but required key absent | Missing key; structural escalation | Unit/mock plus kind startup failure |
| Optional missing object or key | No structural escalation | Unit/mock plus kind Ready control |
| `envFrom`, Secret volume, init-container reference | Exact reference identity and correct required/optional outcome | Unit/mock; representative kind controls |
| Several workloads, only one uncovered reference | Report exact affected workload/reference | Unit/mock |
| No fixtures selected in a fresh sandbox | Known empty inventory, correctly evaluated references | Unit/mock |
| Old record or absent coverage field | Unknown; no new structural refusal | Compatibility and persistence tests |
| Unsupported form, exceeded bounds, incomplete apply | Incomplete/unknown; no inferred missing claim | Unit/mock |
| Restart, then fixture file changes | Saved applied inventory and outcome unchanged | SQLite restart test |
| Textual production-secret signal plus structural evidence | Existing textual refusal retains precedence | Agent/dispatch safety tests |
| Fully covered probe/image incident | Existing repair safety and provenance gates still apply | Outcome evaluations |
| Unique synthetic value seeded for leak inspection | Value/hash absent from all inspected reports/logs/state/artifacts | Redaction and persistence tests |

Record commands, candidate Git SHAs, selected fixture identifier, backend, Kubernetes version where applicable, expected/actual result, skip reasons, and inspected artifact paths in a dedicated #30 implementation review note. Label mock outcomes, real kind consumption, and hosted proof separately. A Pod Ready control needs a positive condition such as an independently served readiness endpoint; do not rely on the coverage report to declare its own correctness.

Run focused tests after each implementation phase. Then run the relevant Ignis/controller contract suite, agent and dispatch suites, drift check, controlled outcome evals, and kind controls. Retain #33/#34/#37 regressions. Record failures and fix them before claiming a phase complete.

## Delivery order and completion criteria

1. Private report-schema/persistence prerequisite on this Raphael branch, with reviewed producer mapping and validation tests.
2. Ignis inventory, evaluator, optional contract addition, and controlled mock/kind evidence on a separate reviewed branch.
3. Report the Ignis diff and hosted results; review before merge/tag; release the approved contract/runtime version.
4. Update Raphael snapshot/pins on this branch and add structural integration in both execution paths.
5. Review the final diff and evidence, then run hosted integration against the approved immutable Ignis release.

#30 is complete when required uncovered references produce a valid, persisted structural escalation; covered and optional controls continue; restart and truncation behave as specified; Secret values are absent from recorded surfaces; and approved contract/runtime pins plus hosted mock/kind results are documented. Investigation or unit tests alone do not close the release or hosted-proof milestones.
