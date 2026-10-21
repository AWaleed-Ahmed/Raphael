# Raphael release milestones

Updated 2026-10-20. The original eight milestone IDs are retained; expired
week/date promises are replaced by observable completion gates. The product is
not declared pilot-complete by closing implementation issues.

## Verified delivery and pending changes

The shipped baseline is Raphael main `a614d47e65904d55e085143ab07c1c5358d5d69e`
with Ignis `contracts-v1.4.2` / `2bfcc644f278da3e16845d6e4408ee9b6048922d`.
Runtime and contract snapshot currently match. See
[canonical installation](pilot-install.md) and the
[issue reconciliation](issue-closure-reconciliation-2026-10-20.md).

[#30](https://github.com/AWaleed-Ahmed/Raphael/issues/30),
[#33](https://github.com/AWaleed-Ahmed/Raphael/issues/33),
[#34](https://github.com/AWaleed-Ahmed/Raphael/issues/34) and
[#37](https://github.com/AWaleed-Ahmed/Raphael/issues/37) are closed for their
original scope. #34 closure does not qualify live baseline ingestion.
[#49](https://github.com/AWaleed-Ahmed/Raphael/issues/49) remains open for
negative-control wording reconciliation; the positive kind proof now passes.
[#58](https://github.com/AWaleed-Ahmed/Raphael/pull/58) (BYOK corrections/evidence)
and [#59](https://github.com/AWaleed-Ahmed/Raphael/pull/59) (default-off inference
deferral) are merged at `a614d47` and `e9a3c66` respectively. #40 remains open despite
delivery of its explicit deferral path. Local inference defaults off; trained
runtime availability is not claimed.

## Milestones

| ID | Status / delivered scope | Remaining acceptance gap | Dependency | Completion criterion | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | Delivered: recovered clone fidelity, persisted claims, bounded deadlines, result-delivery/restart handling. | No original recovery work remains; executable patch-byte restart limits remain explicit. | Reviewed Raphael #50 / Ignis #21 and later corrections. | Keep current lifecycle regressions green on the selected pair; do not restart the lost-code task. | [#50](https://github.com/AWaleed-Ahmed/Raphael/pull/50), [Ignis #21](https://github.com/AWaleed-Ahmed/Ignis/pull/21). |
| 2 | Delivered and verified: structural Secret coverage with metadata preservation, incomplete-form handling, fixtures, precedence and cleanup. #30 closed. | No scoped #30 blocker; no universal no-values claim in named raw channels. | Released Ignis #20 and consumer #55/#56. | Preserve missing/covered/optional and sentinel/persistence acceptance with approved raw-channel exceptions. | [#55](https://github.com/AWaleed-Ahmed/Raphael/pull/55), [#56](https://github.com/AWaleed-Ahmed/Raphael/pull/56). |
| 3 | Verified on Linux: runtime image ownership/cause, target-only repair/refusal, clone fidelity/authentication matrix, lease denial/restart and process termination. | #49 issue wording still needs reconciliation. Native Windows and independent authenticated registry lookup are not qualified. | Owned Linux/kind controls and approved scope. | Retain required positive/negative cases; reconcile #49 without weakening runtime gates. | [shared checklist](https://github.com/AWaleed-Ahmed/Raphael/blob/0dc46c47b976a42dd958ad4d8e56dcfaf8b154ab/docs/ignis-11-13-17-completion-checklist.md), [#51](https://github.com/AWaleed-Ahmed/Raphael/pull/51). |
| 4 | Delivered: runtime tag v1.4.2; all 29 vendored contract blobs match. | None for this pair; future pin changes require their own review. | Immutable approved runtime release. | Build the exact runtime and pass canonical contract Check without moving tags. | [#56](https://github.com/AWaleed-Ahmed/Raphael/pull/56), [Ignis CI](https://github.com/AWaleed-Ahmed/Ignis/actions/runs/39363877121). |
| 5 | Verified on main: core/contracts, real-process mock, four kind remediation controls, six Secret kind controls and released-pair CRLF. | Revalidate relevant behavior after future source/pin changes. | Milestones 1–4 and exact tested SHAs. | Inspect current-head artifacts and require mandatory controls; old green runs do not qualify a new pair. | [main core](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470746), [main pair](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470736), [CRLF](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39364091364). |
| 6 | Partial: ten BYOK identifiers implemented; bounded pinned Gemini synthetic patch evidence exists on an earlier snapshot. Scoped Supabase adapter and seeded-baseline kind proof exist. | Automatic Gemini post-fix live qualification, other advertised live providers, actual Supabase baseline ingestion/authorization and wrong-scope write/read/repair remain unqualified. | Explicit endpoint/budget approval, test credentials and approved tenant data flow; merged #58 controls. | Qualify only paths included in the pilot cut; label/exclude the rest and keep models off until qualified. Synthetic provider success does not prove repair quality. | [#58](https://github.com/AWaleed-Ahmed/Raphael/pull/58), [BYOK record](byok-live-qualification-2026-10-20.md), [PRD §17.6](../prd.md#176-localization-prove-or-cut-gate). |
| 7 | Partial: canonical local mock installation has fresh-environment/build/startup checks; Linux/source-checkout boundary is documented. | Default-off policy is merged (#59); #40 remains open. Customer ingress, credentials, persistence/recovery and permission signoff remain staging gates. | Pilot scope decision, operator-owned staging environment; merged #59 default. | Install selected immutable pair in authorized staging; prove webhook/connector auth, supported repairs/refusals and recovery. Explicitly disable unavailable local inference. | [installation](pilot-install.md), [verification](pilot-local-preflight.md), [#59](https://github.com/AWaleed-Ahmed/Raphael/pull/59). |
| 8 | Pending: real partner pilot and product acceptance. | No verified five-real-failure pilot, empirical confidence/localization/learning improvement or general production reliability result. | Permission approval and milestones 6–7 for the chosen cut. | Review ≥5 real eligible dry-run failures, record false positives/human feedback, meet acceptance/go-no-go and forbidden-patch gates before separately authorized live drafts. | [acceptance](pilot-acceptance.md), [runbook](pilot-week-runbook.md), [PRD §23](../prd.md#23-mvp-acceptance-criteria). |

## Next actions

1. Reconcile #49's original unverified-pull-control wording with the documented
   labelled-mock versus missing-replacement distinction.
2. Retain merged #58/#59 controls, explicitly set `RAPHAEL_MODEL_ENABLED=0`
   and leave external models off until their selected pilot paths are qualified.
3. Choose the pilot cut: deterministic supported paths first; qualify or exclude
   optional providers, live baselines and generative behavior. Do not require all
   providers merely because their adapters exist.
4. Complete operator-owned staging checks, then collect the real pilot evidence.

Historical recovery/qualification reviews and decision entries retain their
original results. Their pending-status statements are superseded by this dated
roadmap and the current completion checklist, not rewritten as if earlier runs
proved later code. This roadmap authorizes no releases, paid calls or production mutations.
