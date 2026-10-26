# Raphael contributor map

**Issue #49 company workload proof — 2026-10-26:** the required kind workflow now
also exercises Google Online Boutique product catalog from pinned upstream
v0.10.4. Local assertions pass; hosted proof is pending. D-20261026-01 reconciles
the original issue wording: unverified pull evidence refuses as
`image_pull_evidence_unverified`; verified absence without an approved replacement
refuses as `patch_value_unavailable`. These remain separate controls, with no
production gate change. See [proof and acceptance record](docs/issue-49-google-image-proof-2026-10-26.md).

**HTTPS maintenance candidate — 2026-10-25:** targeted certificate-trust,
Pip bootstrap and Node runtime fixes are prepared on
`fix/https-security-2026-10-25`, with corresponding Ignis dependency fixes.
See [versions, regression cases and executed results](docs/https-security-validation-2026-10-25.md).
Deployment and executor release verification remain pending; existing contract
and runtime release pins are unchanged.

**Supabase migrations — 2026-10-20:** user-authorized run applied telemetry,
client-scope RLS, and API privilege restriction migrations to Raphael. All seven
versions now match remotely; 31 live SQL checks passed. Public Flask repository
identity fixtures used synthetic tenants and simulated issuer claims, not observed
healthy deployments. Zero fixture rows remain; existing row hashes match. Actual
JWT HTTP access, ingestion and sandbox repair remain deferred. See
[migration validation](docs/supabase-migration-validation-2026-10-20.md). Delivery
is isolated on `fix/supabase-localization-qualification` from main `52e5305`;
unrelated working-tree edits are excluded. Agent/kind-harness tests: 524 passed,
4 skipped. The earlier investigation below predates the authorized database run.

**Issue reconciliation — 2026-10-20:** #30 structural Secret coverage, #33 observed
signature identity, #34 replacement-image provenance policy, and #37 image-gap
presentation meet their original acceptance criteria on GitHub main `0dc46c4`
with released Ignis `contracts-v1.4.2` / `2bfcc64`. All four issues are now closed
as completed with linked evidence. #49 remains open: its positive kind proof passes, but the original
mock refusal wording must be reconciled with PR #50 / D-20261019-02. Live
Supabase baseline ingestion remains a separate unqualified milestone; closing
#34 certifies the scoped provenance policy. See the
[reconciliation and inspected evidence](docs/issue-closure-reconciliation-2026-10-20.md).
This checkpoint supersedes older pending-status statements for these four
issues; older checkpoints below describe their recorded dates.

**Current baseline — 2026-10-20:** Raphael main `a614d47` with Ignis
`contracts-v1.4.2` / `2bfcc64`; all 29 contract blobs match. Start with the
[current release milestones](docs/release-milestones-2026-10-18.md),
[canonical installation](docs/pilot-install.md), and
[executed local checks](docs/pilot-local-preflight.md). PR #58 (BYOK corrections)
and #59 (default-off local inference deferral) are merged. #40 remains open;
trained inference is still unavailable. Current-main [core](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470746)
and [paired E2E](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39369470736) are green.
The current working branch may retain older pins; select the verified checkout
rather than editing pins to make instructions match.

The dated checkpoints below retain their historical results. They do not define
current open work or current test counts. [prd.md](prd.md) distinguishes product
requirements from delivery evidence.

## Historical contributor checkpoints (October 4–5)

**2026-10-20 #30 completion follow-up:** `fix/structural-secret-dependencies` preserves validated Secret metadata, orders direct live observation before diagnosis/model refinement, names required gaps and cleans up on refusal. Ignis #20 is reconciled with current deadlines/leases and recomputes bundled fixture inventory per deployment. Local and hosted candidate acceptance controls pass, including covered-Secret probe repair on real kind; see [Raphael #55](https://github.com/AWaleed-Ahmed/Raphael/pull/55) and the linked review for exact runs. Raphael #55 and Ignis #20 are now merged. User-approved `contracts-v1.4.2` is published at `2bfcc644f278da3e16845d6e4408ee9b6048922d`; Raphael #56 is merged and pins that release; automatic and CRLF released-pair verification pass. See [completion plan](docs/issue-30-completion-plan.md) and [case-by-case review](docs/issue-30-completion-review.md). Older #30 checkpoints below remain historical.

**#11/#13/#17 qualification:** remaining image/clone/lease controls are implemented
in [Ignis #22](https://github.com/AWaleed-Ahmed/Ignis/pull/22) and
[Raphael #51](https://github.com/AWaleed-Ahmed/Raphael/pull/51). Full local results:
agent443/4skip, dispatch88, Rust92 plus seven tool controls in one integration
test, contracts19, harness47, Linux matrix72 hosted, and paired denial cleanup.
Four real-kind cases are required automatically. The [candidate CRLF run](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39278732657) passed all three jobs; inspected artifacts prove image controls, lease-denial cleanup and real kubectl cancellation. The approved runtime release is published and canonical sync/Check passes. Released-pair [automatic checks](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39312614037), [core CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39312613954) and [CRLF qualification](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/39312629725) pass at runtime/pin head `ea7b313`; artifacts are inspected. Raphael #51 and the subsequent #56 pin update are merged. Final delivered identities and post-merge runs are recorded in the checklist; no persistent hosting is needed.
See [qualification review](docs/qualify-11-13-17-review-2026-10-19.md) and the
[shared completion checklist](docs/ignis-11-13-17-completion-checklist.md).
Older checkpoints below are history, not the current remaining implementation.

**2026-10-19 CI/runtime alignment:** the user-approved annotated Ignis
`contracts-v1.4.0` now points to reviewed merged `f1f3b2c858c6ce246308eae395e280856459d9a5`.
Canonical GitHub sync/Check passes. One validated reference from CONTRACTS_VERSION
(or a shared explicit tag/SHA override) feeds every paired CI job. New mock image
evidence is recognized only on the mock backend; without a verified healthy
replacement the eval requires patch_value_unavailable, no patch and no publish.
Legacy/unverified and real-backend mock refusals remain agent controls. This
supersedes older descriptions of unstructured mock evidence, not the separate
pending real-kind positive proof. Local results: agent441/4skip, dispatch88,
workflow/eval/wire/kind assertions41, wire3, production-hook smoke and all7 evals.
See [the CI repair record](docs/historical/ci-repair-review-2026-10-19.md) for failed runs,
release identity, reruns and hosted status links. D-20261019-02 records the choice.

**2026-10-19 delivery correction:** final result-delivery errors now use journaled
cleanup after bounded cached-result retries. Identical committed terminal results
replay their safe envelope after restart, subject to tenant/owner/fingerprint
checks. The recheck findings are resolved and D-20261019-01 records the choices.
Fresh local counts: agent441/4skip, dispatch88, Rust86, contracts19, harness31,
checkout matrix36, paired mock3. See [cases/results and CI limits](docs/historical/result-delivery-fix-review-2026-10-19.md).
Reviewed contract release/pins and current-pair hosted qualification remain open.

**2026-10-19 #13/#17 recovery implemented:** both persistent repositories use
`fix/restore-clone-leases`. Source edits recovered from session history were
reviewed and reimplemented with additional lifecycle fixes; the old Git hashes
remain unavailable. Owned checkout fidelity, persisted claim/renewal, atomic
expiry/result commit, total publication/server deadlines, heartbeat handover,
cancellation and partial-journal recovery are implemented. Fresh local results:
agent441/4skip, dispatch86, Rust82, contracts19, harness/evaluator31,
checkout matrix36, paired mock scenarios3. Independent standards/spec rechecks
have zero remaining findings. See the [plan](docs/historical/restore-13-17-plan-2026-10-18.md),
[detailed cases/results](docs/historical/restore-13-17-review-2026-10-19.md) and
[remaining qualification checklist](docs/ignis-11-13-17-completion-checklist.md).
Authenticated clone, system-attribute/full fidelity controls, hosted deadline/
denial/kind runs, reviewed contract release/pins and #11 positive repair remain.
No #11/#13/#17 closure or release is declared. Dated missing-code statements
below describe the earlier preservation checkpoint and are superseded here.

**2026-10-18 BYOK expansion (local implementation):**
`feature/byok-provider-support` adds named OpenAI/Gemini/Anthropic/Groq/
OpenRouter/Together/Mistral/DeepSeek/xAI configurations through the shared
`complete_json()` path, retaining custom compatible gateways and model
discovery/quota rotation. Native Anthropic has a small wire adapter; callers
and transport stay shared. Compilation/diff checks and regressions passed: agent438 (4skips),
dispatch77, evaluator/proof assertions27; focused BYOK100 is included in the
agent total. All26 contract files match the pinned Ignis release. Live provider
and current-head hosted qualification remain pending. See the
[provider guide](docs/byok-provider-guide.md),
[implementation record](docs/historical/byok-provider-implementation-review-2026-10-18.md)
and [eight pilot-release milestones](docs/release-milestones-2026-10-18.md).
This does not restore the lost #13/#17 commits or close those issues.

**2026-10-18 preservation checkpoint:** see the shared
[#11/#13/#17 completion checklist](docs/ignis-11-13-17-completion-checklist.md).
New `feature/ignis-11-13-17-completion` branches preserve the recoverable code
in both repositories. The final local `/tmp` fix commits from the prior session
are missing and were never pushed; their reported test results do not qualify
these branches. Restore/reimplement those fixes, then complete the issue-specific
behavioral checks, reviewed contract release/pins and current-pair hosted proof.
No issue is declared complete by this checkpoint.

**Current checkpoint — 2026-10-15:** Raphael main is `5a1771e`; the push run after PR #47 and scheduled main runs through [38537751212](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/38537751212) were red on the obsolete eval/no-provenance expectations. PR #48 corrects those expectations; its [hosted run 38631691054](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/38631691054) passes core CI, all seven mock evals, the wire harness, real-hooks smoke, and the Secret-fixture kind job. The kind job's no-provenance control also passes. Its positive verified-provenance case still refuses: that run used Ignis `contracts-v1.3.0`, whose signature lacked the structured runtime fields required by Raphael's gate, despite the cluster observing `ErrImagePull`/`not found`. Ignis PR #19 supplies that runtime evidence but is not yet merged/released. Probe repair remains the current mock `fix_finalized` baseline; bad-image repair is not currently proven end-to-end. The positive case remains in the runner as a clearly labelled manual-dispatch-only pending case tied to [Raphael #49](https://github.com/AWaleed-Ahmed/Raphael/issues/49) and [Ignis #19](https://github.com/AWaleed-Ahmed/Ignis/pull/19); restore it to required checks in the Raphael PR that consumes the reviewed, released, pinned runtime evidence. This defers the proof without changing its expected outcome or provenance gate.

**Current checkpoint — 2026-10-05:** [PR #44](https://github.com/AWaleed-Ahmed/Raphael/pull/44) merged at `78c5e0e` after approval and green head checks. Escalation-report validation now fails closed before publication/action issuance; `save_run()` remains permissive. The old broad storage catch remains a separate open item, not a report-validation catch. Post-merge [core CI](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37303560041) and [E2E/kind](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37303559981) both passed.

**#30 is shipped, not done.** The read-only audit of Ignis `176a13e` / `contracts-v1.3.0` and Raphael main found skipped unsupported forms, a hardcoded dependency checklist, omitted bundled fixture inventory, coverage erased by generic redaction, and missing combined-precedence/sentinel/two-mock-eval proofs. Covered kind controls prove Ready, not covered-plus-probe remediation to terminal. The [audit comment](https://github.com/AWaleed-Ahmed/Raphael/pull/42#issuecomment-5992136207) supersedes earlier completion/review claims below; those paragraphs are historical checkpoints, not the current safety verdict. No independent approval is recorded in the GitHub reviews/discussion for #18/#42.

**Reserved follow-up:** `fix/secret-coverage-safety`, Ignis first and Raphael after the reviewed Ignis merge/tag. Before application edits, resolve the bundled-Secret sentinel boundary: raw manifest bytes currently appear in deploy `rendered_files`, manifest artifacts and durable controller `rendered_yaml`. Stripping values would change the existing actual-file/patch-input semantics; do not silently narrow the no-values test or redact patch bytes without a reviewed decision. Branch protection is also pending owner action: the authenticated account has write access but no administration permission in either repo. Require one independent approval, hosted checks and no bypass; contract/safety work also needs an approved design before implementation.

Earlier checkpoints below are historical; use this checkpoint and the open-work table for the next task.

**2026-10-05 continuation:** PR #43 is merged at `9e652d9`; its post-merge core and E2E/kind runs are green. The next branch is `fix/escalation-report-fail-closed`: shared report validation returns a safe terminal rather than raising or ignoring schema errors, with persistence kept permissive. The newly found optional `patch_id: null` producer defect is corrected by omission, not schema weakening; safety tests now use valid reports without weakening their original assertions. Local tests: 327 agent passes / 4 skips and 77 dispatch passes; 10 evaluator unit tests. See D-20261005-02 and [the review](docs/historical/escalation-fail-closed-review-2026-10-05.md). Seven-eval validating-wrapper proof still requires this branch's hosted run. Ignis Prompt B already merged in PR #18 (`176a13e`, annotated `contracts-v1.3.0`), consumed by Raphael PR #42; the older local Ignis draft is not the released implementation.

**2026-10-05 review checkpoint:** PR #42 and Ignis PR #18 are merged, and post-merge main CI passed on Raphael `122d2d0`, pinned to annotated Ignis `contracts-v1.3.0` / `176a13e`. The old local Secret-coverage draft must not be merged over that release. A separate `test/escalation-reason-drift` branch adds complete report-vocabulary/source checks and reviews the report-validation gate that #42 enabled. Production persistence policy is unchanged on that branch and still requires review; see [the exact risks and remaining decisions](docs/historical/escalation-persistence-review-2026-10-05.md). Older setup results below are historical snapshots, not the new branch's test counts.

The core dispatch -> connector -> sandbox -> diagnosis -> patch -> validation chain works and is continuously tested. This is operational hardening and coverage work, not an architecture rebuild. The remaining limits below are deliberate claims about what has actually been tested.

**Latest completed work:** Raphael [PR #39](https://github.com/AWaleed-Ahmed/Raphael/pull/39) merged at `60c03cf`. Deterministic safety blocks now survive every model-refinement/patch entry point. [Issue #40](https://github.com/AWaleed-Ahmed/Raphael/issues/40) separately tracks the missing local inference runtime; a flag-on fallback must not be described as trained-model proof. Both post-merge hosted runs linked in the proof table are green. Current #30 local results are in [the implementation review](docs/historical/implementation-review-2026-10-04-issue-30.md).

**Current task:** structural Secret-dependency detection, [Raphael #30](https://github.com/AWaleed-Ahmed/Raphael/issues/30). Prompt B investigation is complete. Implementation is reviewed: Raphael changes are in [PR #42](https://github.com/AWaleed-Ahmed/Raphael/pull/42) from `docs/contributor-handoff`; Ignis [PR #18](https://github.com/AWaleed-Ahmed/Ignis/pull/18) is merged and `contracts-v1.3.0` is published. The implementation review has corrected malformed-report handling, duplicate fixture names, and compatibility with current Ignis image fidelity. Local suites pass. Raphael contract/runtime pins are updated; hosted mock/kind proof passed in run 37217777910; the user has authorized pushing and merging reviewed changes. Prompt A's safety prerequisite is merged.

**Documentation checkpoint:** the original contributor map merged in PR #41. PR #42 updates completion status, release pins, implementation plans and review/test evidence for #30/#33/#34/#37.

### Working locations on this machine

| Location | Purpose / caution |
|---|---|
| `C:\dev\raphael-pr27` | Current docs worktree, `docs/project-handoff`, based on `60c03cf`. The directory's historical name does not mean PR #27 is still open. |
| `C:\dev\ignis` | Ignis main checkout, verified at `ece2029`. |
| `~/src/raphael` in WSL | Fresh Linux-native main clone used to execute the setup and tests below. |
| `~/src/ignis` in WSL | Fresh Linux-native checkout at `contracts-v1.2.1`; release binary is `~/src/ignis/controller/target/release/raphael-sandbox-controller`. |
| `~/venvs/raphael-dispatch` in WSL | Tested Python environment, editable agent/dispatch installs point at the Linux-native Raphael clone. |

Do not resume from the old Desktop checkout. `C:\dev\raphael` has separate local docs/history-script changes: preserve them, rather than assuming that checkout is clean or replacing them. These are local conveniences, not paths the CI runner requires.

### Historical setup verification (2026-10-04)

On 2026-10-04, setup/build/run commands were executed from fresh Linux-native clones, not just read:

- Agent: **259 passed, 4 existing skipped**; dispatch: **72 passed**; evaluator unit tests: **9 passed**.
- Ignis: release build, format check and locked check passed; **47 Rust tests passed**, no Rust warnings.
- Combined Raphael app and Ignis both served health checks; authenticated empty polling returned `200 {"messages": [], "pending": false}`.
- Wire Scenarios 1-3, real-hooks smoke and all seven evals passed in dry-run mode. Restart Scenario 3 reused `sb-f46a9671fc16`: kill at approximately t+3.0s, restarted process ready at t+3.3s, `fix_finalized` at t+62.5s.
- Local trace: `~/src/raphael/e2e/e2e-dispatch-trace.jsonl`; machine results: `~/src/raphael/evals/out/eval-results.json`, with per-scenario evidence under `evals/out/`. Hosted artifacts remain the shareable evidence linked below.
- Contract drift check passed from a fresh **Windows-native** checkout with PowerShell 7. WSL lacked `pwsh`, and Windows execution from the WSL UNC path hit script policy; neither was bypassed. The setup docs now state the PowerShell prerequisite and native-checkout/CI alternative.

Owned test processes were stopped afterward. Windows `git status` still warns about unreadable pytest-cache directories in the docs worktree; this is not a clean Windows-test-environment claim. The successful fresh-clone test execution above was in WSL.

## What this project is

Raphael investigates deployment failures, reproduces them in a sandbox, and proposes a small Git change or an honest refusal.

[Raphael](https://github.com/AWaleed-Ahmed/Raphael) is the private Python core: ingestion, diagnosis, patching, dispatch, and publishing.

[Ignis](https://github.com/AWaleed-Ahmed/Ignis) is the public Rust executor: controller, outbound connector, and isolated sandbox operations.

The versioned public sandbox schemas, including connector-v1 envelopes, are the only runtime seam; neither repo imports the other's implementation.

Delivery is human-controlled: dry-run by default, approved live delivery as a draft PR, never auto-merge or production-cluster access from Ignis.

## Architecture, processes, and historical pins

```text
GitHub / workload webhook
  -> ingest -> same-process bridge -> dispatch -> diagnosis / patch / publish
                                      ^   |
                           POST result|   |GET tenant jobs/next
                                      |   v
                            Ignis embedded connector
                                      |
                              local controller
                                      |
                        sandbox deploy / observe / validate
                                      |
                 validated result -> Raphael -> draft PR (human review)
```

- **Process 1:** [run.py](run.py) combines agent routes and dispatch routes around ONE orchestrator. The dispatch lifespan is explicitly attached: rehydration runs before traffic, and the automatic lease reaper runs afterward. Enable the ingest bridge explicitly.
- **Process 2:** Ignis's `raphael-sandbox-controller` binary contains the controller AND connector. There is no separate connector binary. Requests are outbound HTTP; no customer inbound dispatch connection is needed.
- External producers submit to `POST /v1/tenants/{tenant_id}/jobs`; connectors poll `GET /v1/tenants/{tenant_id}/jobs/next` and submit `POST /v1/results`. Tokens have a tenant and producer/connector role; results require authentication unconditionally. The bridge uses an internal Python call, not a public-envelope extension or an internal bearer token.
- **Runtime pin:** workflow defaults use annotated Ignis `contracts-v1.3.0`, peeled commit `176a13e1a580f4699eba17800bfd2932e5fcaf1c`. Ignis-originated mock runs test the exact pushed SHA; kind uses the release pin.
- **Schema snapshot:** [CONTRACTS_VERSION](CONTRACTS_VERSION) pins `contracts-v1.3.0`, including bounded reference-level Secret coverage. Sync/check with [tools/sync-sandbox-contracts.ps1](tools/sync-sandbox-contracts.ps1).
- **Single-instance recovery, not horizontal scaling:** valid persisted pending actions resume unchanged; stale leases fail immediately. Before patch generation, missing ephemeral manifests are re-fetched in the same sandbox. After generated patch bytes are lost, dispatch fails closed with `patch_context_lost_on_restart`; failed re-fetch uses `patch_input_unavailable`. See [dispatch/README.md](dispatch/README.md).

## Historical baseline proof (before #30/#33/#34/#37)

The fresh [cross-repo run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403) passed all mock scenarios, seven real-hook evals, and four kind cases. [Core CI 37185648453](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648453) passed agent (259, four existing skips), dispatch (72), and contract checks; evaluator unit tests passed 9/9 in the cross-repo job.

| Capability | Proof | Caveat |
|---|---|---|
| Probe repair reaches `fix_finalized` | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): `probe_misconfiguration` | Real agent hooks/processes, **mock cluster**; not real-Kubernetes remediation proof. |
| Bad-image repair is gated; no current positive E2E proof | [Run 38631691054](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/38631691054): mock and no-provenance cases refuse correctly; the positive kind case also refuses on Ignis `contracts-v1.3.0` because the required runtime fields are absent | The earlier mock `fix_finalized` result in run 37185648403 predates PR #47 and is historical only. Positive proof is retained as a manual-dispatch-only pending case tied to [Raphael #49](https://github.com/AWaleed-Ahmed/Raphael/issues/49) and [Ignis #19](https://github.com/AWaleed-Ahmed/Ignis/pull/19); it returns to required checks in the Raphael consumer PR after reviewed runtime evidence is released and pinned. |
| Missing-config is a proven refusal | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): `invalid_missing_config` -> `escalated / patch_value_unavailable`, no patch | Not a third safe automated fix. D-20260930-01 supersedes D-20260918-02's earlier safe-fix claim. |
| Exact second-of-two Deployment repair | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): `probe_second_deployment`; [PR #36](https://github.com/AWaleed-Ahmed/Raphael/pull/36) | Old code spent three attempts on empty-marker patches then exhausted budget; current code changes only the second probe's two lines. Not all multi-resource manifests. |
| Three of four negative scenarios are proven | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): `secret_required_escalation`, `prompt_injection_probe`, `unreproducible_failure` | Secret dependency is **textual**, not structural. Injection compares exact classification, confidence, terminal outcome, paths, and patch delta for one inert comment with external LLM off; not whole-file equality or universal injection resistance. Refusal reasons are explicit. Fourth scenario remains gated. |
| Evidence/patch-store boundary | [Core run 37185648453](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648453): JSON/SQLite regression tests; [PR #27](https://github.com/AWaleed-Ahmed/Raphael/pull/27), [PR #29](https://github.com/AWaleed-Ahmed/Raphael/pull/29) | Raw manifests/patch bodies stay ephemeral and patch-only; diagnosis receives bounded redacted evidence. Seeded secret-value absence is checked across persisted records. This does not prove arbitrary logs/raw webhook archives never contain secrets. |
| Blocked decisions immutable to models | [Core run 37185648453](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648453): 22 safety regressions; [PR #39](https://github.com/AWaleed-Ahmed/Raphael/pull/39) | Non-abstaining stubs carry the proof; zero classifier/LLM/proposal calls on blocked paths. Seven flag-on/off evals prove current **fallback**, not trained inference; #40 tracks missing runtime plumbing. |
| Whole-Ignis restart recovery and terminal cleanup | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): mock wire Scenarios 1-3 | Connector receipts/job mapping and mock namespaces persist; Scenario 3 reuses the same sandbox. Not every crash window or general real-cluster qualification. |
| Automatic lease reaping and startup restore | [Core run 37185648453](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648453): combined-app lifecycle test; [PR #19](https://github.com/AWaleed-Ahmed/Raphael/pull/19) | One process only; patch-content restart limits above remain deliberate. |
| Kind proof covers only secret-fixture consumption and digest resolution | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): four covered/uncovered cases, each with one/two images | Covered workload Ready with synthetic value; uncovered workload fails startup. Partial coverage names only unresolved images. Not structural detection or general backend qualification. Remediation/safety fixture evals still use mock. |

**Separate historical proof:** [raphael-live-target#1](https://github.com/AmazingDude/raphael-live-target/pull/1) and D-20260906-01 record one real draft publication against a disposable target. No hosted live-publish run is claimed; CI stays dry-run, and this is not a partner pilot.

**Exists, not a full end-to-end UI proof:** [frontend/src/main.js](frontend/src/main.js) calls run APIs when configured and falls back to demo data. GitHub commands exist and are opt-in ([agent/README.md](agent/README.md)); neither is described here as an unimplemented feature or a proven full user journey.

## Historical open-work snapshot (October 4–5)

**Completed locally:** #33 observed identity, #34 image-provenance enforcement, and #37 image-gap presentation are implemented on this branch. Review fixes now reject image provenance when the run target and observed environments conflict. Latest checks are recorded in the [implementation review](docs/historical/implementation-review-2026-10-04.md); hosted proof passed in run 37217777910; live Supabase baseline ingestion remains outstanding. The bad-image evaluator expects refusal without verified baseline provenance; the earlier hosted demo-image success remains historical proof. #30 is implemented and reviewed; Ignis PR #18 is merged and `contracts-v1.3.0` is released/pinned. Hosted Raphael mock/kind checks passed in run 37217777910; see its separate review note.

**Next planned tasks:** Ignis #11 registry-backed detection and Ignis #13 clone line-ending policy. The [implementation plan](docs/historical/next-three-implementation-plan.md) records scope, sequence, test cases, completion criteria, and coordination with #30. These Ignis tasks are not claimed here.

Claim status as of 2026-10-04. "Not claimed here" is not a claim that nobody elsewhere is working on it; check with the team before starting. Update this table when taking or releasing a task.

| Order / item | In progress | Coordination / conflict |
|---|---|---|
| 1. Raphael #30, Ignis-side Secret coverage first | **Yes — safety follow-up reserved on `fix/secret-coverage-safety`.** Shipped in #18/#42, but audit found real defects and missing proofs. Await bundled-Secret/raw-patch boundary decision before application changes. | Reserve fidelity schema, sandbox fixture inventory, contract version/release, `CONTRACTS_VERSION`, and `IGNIS_REF`. Ignis reviewed merge/tag first, then Raphael consumer/evals. |
| 2. Raphael #33, observed signature identity | Reviewed implementation and hosted mock proof passed; delivery PR #42 | Coordinate diagnosis/signature edits with #30. |
| 3. Bad-image repair proof under the provenance gate | **Not proven; tracked in [Raphael #49](https://github.com/AWaleed-Ahmed/Raphael/issues/49)** | Require a real kind `ErrImagePull` plus approved provenance to reach `fix_finalized`; do not add provenance fields to the mock detector. Raphael #34's broader baseline-ingestion status remains separately open. |
| 4. Raphael #37, gap presentation | Reviewed on this branch; hosted full agent tests pass | Display-only change; no fidelity schema/data changes. |
| 5. Ignis #11, registry detection | Still open and unimplemented on current Ignis main; no local implementation to push | Observe/backend edits may overlap #30; no independent contract bump. |
| 6. Ignis #13, clone policy | Not claimed here | Read-only investigation is parallel-safe; coordinate runtime/render changes. |
| 7. Ignis #17, deploy duration | Still open and unimplemented on current Ignis main; no local implementation to push | Service/deploy changes overlap #30; coordinate before edits. |
| 8. Raphael #40, model plumbing | Not claimed here | Read-only audit is parallel-safe; graph/safety changes require separate review. |
| 9. Drift detection | Parked, no implementation claim | Waiting on authorized production-spec source; no Ignis production access. |
| 10. Forbidden-patch scenario | Gated, no implementation claim | PRD §17.8 precondition; not an instruction to invent an unsafe generator. |
| 11. Graph storage failure handling | Open, no implementation claim | `_persist_graph_outcome()` retains broad best-effort exception handling after #44; design error handling without logging payloads or silently losing outcomes. Separate from report validation and whole-run schema projection. |
| 12. Whole-run schema projection | Open, no implementation claim | Test-only audit found routing fields, patch shape/content, diagnosis, evidence, trigger/sandbox enums and publish/fix-record mismatches. Do not enforce the whole schema in `save_run()` before a separate reviewed compatibility plan. |
| 13. Main-branch review protection, both repos | Awaiting owner/admin | Require one independent approval and hosted checks, including administrators/no bypass. Current authenticated account cannot change protections. Architectural/safety/contract work needs an approved design note before code. |

1. **[Raphael #30: structural Secret dependency](https://github.com/AWaleed-Ahmed/Raphael/issues/30).** Follow-up implementation is in progress on Ignis `fix/secret-coverage-safety`; Ignis lands first, then a tagged release and Raphael consumer/eval update. The raw patch/application channels remain unchanged: `rendered_files` in the deploy response, the full rendered-manifest artifact, and `SandboxRecord.rendered_yaml`. The no-values guarantee applies outside those named channels; coverage inventories and reports retain names/keys only. Current implementation adds incomplete reporting for unsupported/malformed forms, bundled labelled-Secret inventory, positive-only `dependencies_available`, named required-gap text, and sentinel tests; remaining work includes full verification, preserving coverage through Raphael redaction, precedence/sentinel regression tests, two fast mock evals (uncovered missing key refuses; covered reference plus probe defect fixes), and terminal assertions in covered kind controls. Keep `unresolved_secret_dependency` distinct from textual `production_secret_required`; see D-20261014-01, D-20261005-03 and [the audit](https://github.com/AWaleed-Ahmed/Raphael/pull/42#issuecomment-5992136207).
2. **[Raphael #33: observed signature identity](https://github.com/AWaleed-Ahmed/Raphael/issues/33).** Implemented and tested locally: analyzers preserve exact observed keys and probe attributes; direct and dispatch validation target the observed resource, with missing identity failing closed. Review and hosted mock proof passed; see PR #42.
3. **[Raphael #34: replacement-image provenance](https://github.com/AWaleed-Ahmed/Raphael/issues/34).** The gate requires a scoped verified last-known-good container image with trace ID and full commit SHA; absent/ambiguous provenance refuses the patch. Placeholder SHAs are rejected and malformed baseline rows are ignored. PR #32's real-kind repair predates the merged diagnosis gate and does not prove a current bad-image repair; live per-container baseline ingestion remains unverified. The current-gate kind proof is tracked separately in [#49](https://github.com/AWaleed-Ahmed/Raphael/issues/49).
4. **[Raphael #37: readable image-gap presentation](https://github.com/AWaleed-Ahmed/Raphael/issues/37).** One prefix with an image list in the PR body; preserve per-image evidence and `full_validation = false` when any gap remains.
5. **[Ignis #11: registry-backed detection](https://github.com/AWaleed-Ahmed/Ignis/issues/11).** Keep mock string-pattern claims narrow; real pull-failure detection needs its own proof.
6. **[Ignis #13: clone line-ending policy](https://github.com/AWaleed-Ahmed/Ignis/issues/13).** Decide blob-byte versus normalized-worktree fidelity, including repository attributes. Render-boundary CRLF normalization is already fixed; do not alter global Git configuration.
7. **[Ignis #17: deploy duration and local HTTP timeout](https://github.com/AWaleed-Ahmed/Ignis/issues/17).** Apply plus digest polling can take about 120 seconds; connector->controller has no explicit overall request timeout. Dispatch waits for the posted result while the lease clock keeps running. Coordinate timeout/lease bounds, not just one client setting.
8. **[Raphael #40: model plumbing](https://github.com/AWaleed-Ahmed/Raphael/issues/40).** Local inference is explicitly deferred and disabled by default: all five artifact bundles are tracked, but the prediction runtime is under ignored `raphael/model/` and is absent from a clean checkout/package. See [the resolution record](docs/local-inference-resolution-2026-10-20.md).
9. **Drift detection: parked.** First decide an authorized source for production specs that does not give Ignis production access; see [PRD §10](prd.md#10-sandbox-and-environment-replication) and [§26](prd.md#26-open-product-decisions). No assigned implementation issue yet.
10. **Forbidden-patch negative scenario: gated.** [PRD §17.8](prd.md#178-llm-role-and-learning-loop-gate) requires it before a generative patch path ships. Do not fabricate an unsafe generator solely to close scenario count; no separate active implementation issue yet.

Other product gates are still open: measured confidence calibration, localization with real Supabase credentials/prove-or-cut results, learning-effectiveness evidence, general real-backend qualification, and the five-authorized-failures partner pilot. Existing code/scaffolding is not proof of these milestones; see [PRD §17](prd.md#17-evaluation-plan) and [pilot runbook](docs/pilot-week-runbook.md).

### Historical #30 implementation plan and results (superseded by the current checkpoint)

The details below record the implementation as it stood during PR #42. They are not a current safety sign-off. Use D-20261005-03, the reserved row above, and the linked audit for the remaining requirements.

### Shipped components (historical PR #42 notes)

1. **Fixture selection remains explicit.** [sandbox_config.py](agent/raphael_agent/sandbox_config.py) reads `RAPHAEL_SECRET_FIXTURE_SET`; unset means none. Dispatch snapshots that selection at intake. Never infer fixture authorization from a Secret name.
2. **Ignis inventory/evaluator:** PR #18 is merged and `contracts-v1.3.0` is pinned. The implementation stores applied fixture names and keys and evaluates supported references. The audit found unsupported forms that still require conservative handling and bundled manifest fixtures that are not inventoried.
3. **Raphael integration:** PR #42 is merged. The gate blocks on complete reports with a required missing object/key. The audit found a missing combined-precedence test and that generic redaction removes the `secret_coverage` field.
4. **Kind proof:** run 37217777910 established the covered/uncovered fixture consumption controls and missing-key behavior. Covered cases recorded no terminal outcome; the run does not prove a covered Secret plus a probe defect reaches `fix_finalized`.

Do not weaken redaction, restore raw manifests to durable run state, read production Secret payloads, or change unrelated image-provenance/model-policy work to finish this task. Coordinate any fidelity schema, release, or `IGNIS_REF` edit with this owner.

### What can run in parallel?

| Task | Safe independent work | Coordinate before editing |
|---|---|---|
| #37 PR-body cleanup | Rendering-only changes/tests | Preserve raw fidelity evidence; don't bundle contract edits. |
| Frontend work | UI layout and client tests | Agree run API/auth changes separately; demo data is not live proof. |
| #13 clone-policy investigation | Read-only attribute/byte experiments | Runtime clone changes affect fidelity and fixture artifacts. |
| #30, #33, #34 | Design/audit can proceed independently | Diagnosis, evidence, signatures, patch templates and eval expectations overlap; assign one owner per shared path. |
| #11 and #17 | Separate diagnosis/duration investigations | Changes to Ignis service/observe/deploy paths can overlap #30's coverage work. |
| #40 model work | Audit artifacts and propose wire-or-cut | Graph/model behavior overlaps safety and §17.8 gates; do not change blocked-decision rules. |
| Any release/contract change | Prepare docs/tests independently | One coordinated Ignis merge -> annotated tag -> Raphael snapshot/pin -> hosted proof sequence. |

## Run locally

Use the [canonical pilot installation](docs/pilot-install.md). It owns the
release pair, clone/build commands, explicit shell profile, combined `python
run.py` startup, Ignis embedded connector, auth, optional console proxy and
cleanup. See [local verification](docs/pilot-local-preflight.md) for exactly
which commands were executed and [acceptance](docs/pilot-acceptance.md) for
unmet partner gates. The earlier pin and proof tables above are historical.

## Current work, in order

Follow [release milestones 1–8](docs/release-milestones-2026-10-18.md): reconcile
#49's mock wording with shipped behavior; retain the merged #58/#59 safety controls; select the
pilot cut for BYOK, localization and healthy-baseline ingestion; qualify an
authorized staging installation; then collect at least five real dry-run
failures and human approval before enabling any live draft class.

## Working rules and decisions

The complete historical log remains in [decision.md](decision.md); this handoff is the current-state map, not a replacement. Start with these entries when continuing:

| Decision | What it governs now |
|---|---|
| D-20261003-01 | Immutable deterministic safety blocks; model fallback versus trained inference. |
| D-20261001-01 / D-20260930-01 | Second-resource targeting and evidence-backed patch values. The earlier D-20260918-02 safe ConfigMap repair claim is superseded; missing config is now a proven refusal. |
| D-20260927-03 | Explicit fixture selection and narrow real-cluster consumption proof, not structural detection. |
| D-20260927-02 / D-20260927-01 | Precisely scoped negative-scenario proof and bounded/redacted diagnosis evidence. |
| D-20260926-01 / D-20260924-01 | Ephemeral raw patch inputs, whole-record secret absence, and fail-closed patch restart limits. |
| D-20260926-02 | LF normalization at render output; clone policy remains separate. |
| D-20260920-01 | A real forbidden-patch eval is required before a generative patch path ships. |
| D-20260918-01 | Restart XFAIL closed by immutable-release CI proof; the earlier D-20260906-04 failure is history, not an open restart task. |

This docs update changes only three existing decision **status lines** to identify their merged PRs/proof. Their historical bodies remain intact. New findings or changed choices need a new dated entry, not a rewrite of an old result.

- Before claims/edits: `git status`, `git log --oneline -5`, `git branch --show-current`; update clean main with `git pull --ff-only origin main`. Preserve others' dirty work and use a separate branch/worktree.
- Branch -> reviewed PR -> main; no direct implementation commits to main/prod, no force-push to those branches. Never merge your own PR without explicit review/approval. See [branching rules](docs/BRANCHING.md) and [CONTRIBUTING.md](CONTRIBUTING.md).
- Public contract change: Ignis first, reviewed merge, annotated immutable release tag, Raphael snapshot/pin, fresh hosted proof. Implementation-only tags need not change `CONTRACTS_VERSION`; check contract bytes rather than assuming.
- One claim per proof: every scenario/PR must state backend, fixture SHA, flags, publication mode, and limits. A refusal can pass; a blocked/skipped case is not a pass. Do not expand a milestone because mocks or stubs returned success.
- Deterministic blocked decisions cannot be overridden/refined by probabilistic components. Raw manifests stay patch-only; keep the whole-record secret regression, not merely an absent-key check.
- Never put private Raphael implementation, harnesses, credentials, or env configuration into public Ignis. No production Kubernetes access from Ignis, arbitrary command API, secret-payload reads, or auto-merge.
- Ask before destructive or privileged actions, including deleting a cluster, removing material files, or using `sudo`. Stop/report real application bugs found by a harness rather than fixing them inline outside scope.
- Live publication requires explicit human approval, a disposable/authorized target, narrow allowlist, and the reviewed confirmation-gate script. Historical `e2e/run_live_publish_v2.py` remains an **untracked local script**, not a clean-clone command; do not replace that gate with casual env toggles. CI stays dry-run with no publish credentials.
- [decision.md](decision.md) is the durable decision log. Add newest-first `D-YYYYMMDD-NN` entries for meaningful choices, recording scope/proof/alternatives. Preserve historical results; mark incorrect claims superseded and link the replacement ID (as D-20260930-01 does), not an unqualified new claim beside them.

### Review delivery checkpoint — 2026-10-04

Reviewed #30 plus prior #33/#34/#37 integration and corrected schema/completeness, direct-entry gate, duplicate-fixture, and current-main integration issues. Results: **291 agent passed (4 skipped), 75 dispatch passed, 62 Ignis controller passed, 18 Ignis contract passed, 10 evaluator unit passed, 7 outcome evals passed, 3 wire scenarios passed, real-hooks smoke passed**. Local integration uses mock, not Kubernetes. See [#30 implementation review](docs/historical/implementation-review-2026-10-04-issue-30.md) for commands, evidence and limitations. [Core CI 37217777993](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37217777993) and [cross-repo 37217777910](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37217777910) passed. Six kind controls verify covered, required-missing-object/key, optional-key, and image-digest behavior; required cases persist structural refusal with no patch. Delivery is in [PR #42](https://github.com/AWaleed-Ahmed/Raphael/pull/42).

Ignis #11 and #17 remain open/unimplemented. PR #15 was closed as superseded: PR #14 already fixed its contract problem; relabeling generic kubectl as kind was not a correct remaining change.

### BYOK delivery checkpoint — 2026-10-06

[PR #23](https://github.com/AWaleed-Ahmed/Raphael/pull/23) merged at `9b31e52` and implements environment-based Gemini/OpenAI/compatible-gateway calls for external diagnosis and patching. Per user instruction, an unspecified model is discovered and randomly selected for the configured key; HTTP 429 rotates to another candidate within eight attempts and a shared deadline. Explicit models remain pinned. Credentials stay outside durable run state. The shared structural Secret gate also stops external refinement before a provider call.

Local results: 386 agent passed (4 existing skips), 77 dispatch passed, 58 focused BYOK passed, 10 evaluator passed. See [BYOK implementation review](docs/historical/byok-implementation-review-2026-10-06.md) for cases, limits and sources. Final hosted core CI 37440594134 (plus push audit 37440587490) and cross-repo run 37440594100 passed; live Gemini connectivity is unverified because no key is configured. Native Anthropic/Azure and tenant key management remain outside this delivery. Local classifier #40 remains open. Real-kind remediation PR #32 will be reconciled separately.

### BYOK qualification checkpoint — 2026-10-20

Qualified the current local BYOK code with deterministic HTTPX mocks and setup documentation. OpenAI, Gemini through Google's OpenAI-compatible endpoint, and `custom_openai` remain the only implemented identifiers; custom endpoints require individual qualification. Fixed OpenAI automatic mode rotating on every 429: it now rotates only for documented rate-limit responses and stops for billing/account-quota or unrecognized 429s. Added regression coverage for discovery 429 stopping before completion, catalog deduplication, and empty output. BYOK-focused result: 64 passed. The combined BYOK/safety-boundary run had 85 passes and one unrelated model-gateway test failure (`classify_failure({})` returned an abstained prediction instead of `None`). Live provider checks are blocked: no BYOK key, custom endpoint, explicit model, or approved endpoint budget was configured; live request count is zero. The opt-in smoke correctly stopped with `llm_key_not_configured`. The broader agent suite stalled at `test_alertmanager_http_endpoint` after seven passes and was interrupted, so it has no completion result. See [BYOK live qualification](docs/byok-live-qualification-2026-10-20.md) for the provider matrix, official protocol cross-check, simulated cases, and exact missing inputs. No commit, push, or PR was made.

**Authorized Gemini follow-up (supersedes the no-key blocker above):** The user supplied a key and requested minimal requests/tokens. Network-enabled Linux execution completed one authenticated discovery GET (63 entries, no next page) and two POST attempts, each capped at 128 output tokens with no rotation. Automatic smoke selected `antigravity-preview-09-2026` and failed safely with HTTP 400. A pinned `gemini-3.1-flash-lite` call through the actual patch helper returned the exact synthetic one-line readiness port change, passed schema/policy, matched the provider-returned model, and used 255 prompt + 98 completion tokens in 1.979 seconds. The proposal was never applied or deployed. Gemini's filter now excludes unrelated/specialized generation families; replay reduced 31 candidates to 17, with a regression. Corrected automatic mode was not rerun live to preserve the two-attempt cap. Restricted sandbox networking failed before any completion; the success required network-enabled Linux execution. Latest focused tests: 65 BYOK passed; 117 relevant BYOK/diagnosis/patch tests passed. Quota remains SIMULATED, diagnosis and deployment repair remain unverified live, and OpenAI/custom remain blocked. Sanitized observations and the secret-free reproduction harness are linked in the qualification record. No key was saved to repository files; no commit, push, or PR was made.

### Real-kind remediation checkpoint — 2026-10-06

PR #32 is reconciled with current main: obsolete rollout/backend fixes and shared mock-fixture edits are discarded. A hosted disposable proof now checks probe repair, no-provenance image refusal and image repair with a scoped catalog fixture verified from an actually Ready baseline Pod. Production AgentHooks remain in use. Local assertion/cleanup/backend tests pass (14), evaluator tests pass (10); hosted implementation proof passed in run 37442412528, with final-head checks required before merge. See [kind implementation review](docs/historical/kind-remediation-review-2026-10-06.md). This does not prove live Supabase ingestion or resolve Ignis #11/#17.

### Verified kind delivery evidence

[Core 37442412446](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37442412446) and [cross-repo 37442412528](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37442412528) passed on the corrected implementation. Three new real-kind controls establish probe repair, no-provenance image refusal and seeded-provenance image repair; existing mock and six Secret-kind controls also passed. The review records fixture/baseline SHAs, expected/actual outcomes, the initial fixture correction and retained artifact names. Live BYOK calls and real Supabase ingestion remain unverified; Ignis #11/#17 and local classifier #40 remain open.

### Supabase localization prove-or-defer — 2026-10-20

**Deferred from pilot claims:** live healthy ingestion/retrieval, live tenant isolation,
Supabase-backed approved-image sandbox validation, and measured production localization
benefit. The local `.env` has Supabase configuration, but disposable-project authorization,
migration permission, scoped test JWTs, an authorized executor/workload and independent
healthy deployment observations were not supplied. No live database request, migration
or sandbox mutation occurred. There is no production healthy-baseline writer: existing
methods and fake scripts perform direct backend writes only.

Catalog assistance now defaults off and opt-in binds company/client to backend configuration.
The adapter and graph recheck scope before consuming baseline fields; image resolution and
templates recheck tenant/release/runtime provenance. Opaque Supabase secret headers,
bounded/sanitized REST errors, structured-span comparison and false divergence bonuses
were corrected. A new client-PK/client-scoped RLS migration is prepared but not applied.
A runnable credential-gated fixture/RLS harness and exact-row cleanup procedure are in
[the qualification record](docs/supabase-localization-qualification-2026-10-20.md).
The 20-case synthetic paired replay reports 4 wins / 15 ties / 1 outage regression,
Top-1 16/20 → 19/20, MRR .85 → .95, and zero unsafe image approvals; this is not a
real incident/repair study. The full local run had 437 passes, 4 skips and one pre-existing
local-inference escalation-reason scanner failure; relevant safety tests pass. Unrelated
worktree edits were preserved. No issues were closed, and no commit/push/PR was made for
this task.
