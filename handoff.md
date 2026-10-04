# Raphael contributor map

Verified against Raphael main `60c03cf` and Ignis main `ece2029` on 2026-10-04.
This page describes current implementation and proof; [prd.md](prd.md) defines the product, not completed work.

## Start here: where we stopped

The core dispatch -> connector -> sandbox -> diagnosis -> patch -> validation chain works and is continuously tested. This is operational hardening and coverage work, not an architecture rebuild. The remaining limits below are deliberate claims about what has actually been tested.

**Latest completed work:** Raphael [PR #39](https://github.com/AWaleed-Ahmed/Raphael/pull/39) merged at `60c03cf`. Deterministic safety blocks now survive every model-refinement/patch entry point. [Issue #40](https://github.com/AWaleed-Ahmed/Raphael/issues/40) separately tracks the missing local inference runtime; a flag-on fallback must not be described as trained-model proof. Both post-merge hosted runs linked in the proof table are green.

**Current task:** structural Secret-dependency detection, [Raphael #30](https://github.com/AWaleed-Ahmed/Raphael/issues/30), beginning with Ignis's reference-coverage reporting. Prompt B's preliminary investigation is complete and reported; implementation has **not** started. Review the findings below before coding. Prompt A was the safety prerequisite and is already merged; do not redo it.

**Documentation checkpoint:** this contributor-map update is in [PR #41](https://github.com/AWaleed-Ahmed/Raphael/pull/41), branch `docs/project-handoff`. It includes `handoff.md`, `CONTRIBUTING.md`, the PRD status note, and three decision-log status corrections. Until it is merged, a teammate must fetch and check out this branch to read the updates; pulling main alone is not sufficient. The earlier `docs/contributor-handoff` remote branch received separate code changes from another author and is intentionally excluded from this docs-only PR.

### Working locations on this machine

| Location | Purpose / caution |
|---|---|
| `C:\dev\raphael-pr27` | Current docs worktree, `docs/project-handoff`, based on `60c03cf`. The directory's historical name does not mean PR #27 is still open. |
| `C:\dev\ignis` | Ignis main checkout, verified at `ece2029`. |
| `~/src/raphael` in WSL | Fresh Linux-native main clone used to execute the setup and tests below. |
| `~/src/ignis` in WSL | Fresh Linux-native checkout at `contracts-v1.2.1`; release binary is `~/src/ignis/controller/target/release/raphael-sandbox-controller`. |
| `~/venvs/raphael-dispatch` in WSL | Tested Python environment, editable agent/dispatch installs point at the Linux-native Raphael clone. |

Do not resume from the old Desktop checkout. `C:\dev\raphael` has separate local docs/history-script changes: preserve them, rather than assuming that checkout is clean or replacing them. These are local conveniences, not paths the CI runner requires.

### Latest literal setup verification

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

## Architecture, processes, and pins

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
- **Runtime pin:** workflow defaults use annotated Ignis `contracts-v1.2.1`, peeled commit `ece202986b9d3195c7d776cbb45b83a956b8c4e2`. Ignis-originated mock runs test the exact pushed SHA; kind uses the release pin.
- **Schema snapshot:** [CONTRACTS_VERSION](CONTRACTS_VERSION) stays at `contracts-v1.2.0`. The v1.2.1 release changed implementation, not contract bytes. Sync/check with [tools/sync-sandbox-contracts.ps1](tools/sync-sandbox-contracts.ps1).
- **Single-instance recovery, not horizontal scaling:** valid persisted pending actions resume unchanged; stale leases fail immediately. Before patch generation, missing ephemeral manifests are re-fetched in the same sandbox. After generated patch bytes are lost, dispatch fails closed with `patch_context_lost_on_restart`; failed re-fetch uses `patch_input_unavailable`. See [dispatch/README.md](dispatch/README.md).

## Proven today, with limits

The fresh [cross-repo run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403) passed all mock scenarios, seven real-hook evals, and four kind cases. [Core CI 37185648453](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648453) passed agent (259, four existing skips), dispatch (72), and contract checks; evaluator unit tests passed 9/9 in the cross-repo job.

| Capability | Proof | Caveat |
|---|---|---|
| Two classes reach `fix_finalized` (probe, bad image) | [Run 37185648403](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37185648403): `probe_misconfiguration`, `bad_image_reference` | Real agent hooks and real processes, **mock cluster**. Image detection recognizes known-bad strings, not arbitrary registry failures; replacement-image provenance is open (#34). |
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

## Open work, in order

Claim status as of 2026-10-04. "Not claimed here" is not a claim that nobody elsewhere is working on it; check with the team before starting. Update this table when taking or releasing a task.

| Order / item | In progress | Coordination / conflict |
|---|---|---|
| 1. Raphael #30, Ignis-side Secret coverage first | **Yes — Codex, Prompt B claimed.** Step 0 investigation complete; findings reported before coding, implementation awaiting review. No coverage release exists yet. | Reserve fidelity schema, sandbox fixture inventory, contract version/release, `CONTRACTS_VERSION`, and `IGNIS_REF`. Coordinate all overlapping changes. |
| 2. Raphael #33, observed signature identity | Not claimed here | Coordinate diagnosis/signature edits with #30. |
| 3. Raphael #34, replacement-image provenance | Not claimed here | Coordinate patch/diagnosis/eval changes; don't bundle into #30. |
| 4. Raphael #37, gap presentation | Not claimed here | Display-only is parallel-safe; changing fidelity data/schema conflicts with #30. |
| 5. Ignis #11, registry detection | Not claimed here | Observe/backend edits may overlap #30; no independent contract bump. |
| 6. Ignis #13, clone policy | Not claimed here | Read-only investigation is parallel-safe; coordinate runtime/render changes. |
| 7. Ignis #17, deploy duration | Not claimed here | Service/deploy changes overlap #30; coordinate before edits. |
| 8. Raphael #40, model plumbing | Not claimed here | Read-only audit is parallel-safe; graph/safety changes require separate review. |
| 9. Drift detection | Parked, no implementation claim | Waiting on authorized production-spec source; no Ignis production access. |
| 10. Forbidden-patch scenario | Gated, no implementation claim | PRD §17.8 precondition; not an instruction to invent an unsafe generator. |

1. **[Raphael #30: structural Secret dependency](https://github.com/AWaleed-Ahmed/Raphael/issues/30).** Claimed workstream, Ignis side first. Ignis must report reference-level fixture coverage (names/keys, never values); optional references must not become missing requirements. Carry it through a versioned contract, then pin Raphael. Outcome evals use mock; kind cross-checks predicted coverage against actual Pod behavior, including a missing-key control. New `unresolved_secret_dependency` stays distinct from textual `production_secret_required`. The prerequisite safety fix is merged; the private escalation-schema/save validation gap is a step-0 design prerequisite, not silently solved by #39. No structural implementation is shipped yet.
2. **[Raphael #33: observed signature identity](https://github.com/AWaleed-Ahmed/Raphael/issues/33).** Replace hardcoded `payments-api` expected keys with observed identity. Strict templates already target `failure_signature`; this is the remaining analyzer/validation identity issue.
3. **[Raphael #34: replacement-image provenance](https://github.com/AWaleed-Ahmed/Raphael/issues/34).** Decide which trusted source authorizes a known-good image. The current placeholder image is not proof of an appropriate application repair.
4. **[Raphael #37: readable image-gap presentation](https://github.com/AWaleed-Ahmed/Raphael/issues/37).** One prefix with an image list in the PR body; preserve per-image evidence and `full_validation = false` when any gap remains.
5. **[Ignis #11: registry-backed detection](https://github.com/AWaleed-Ahmed/Ignis/issues/11).** Keep mock string-pattern claims narrow; real pull-failure detection needs its own proof.
6. **[Ignis #13: clone line-ending policy](https://github.com/AWaleed-Ahmed/Ignis/issues/13).** Decide blob-byte versus normalized-worktree fidelity, including repository attributes. Render-boundary CRLF normalization is already fixed; do not alter global Git configuration.
7. **[Ignis #17: deploy duration and local HTTP timeout](https://github.com/AWaleed-Ahmed/Ignis/issues/17).** Apply plus digest polling can take about 120 seconds; connector->controller has no explicit overall request timeout. Dispatch waits for the posted result while the lease clock keeps running. Coordinate timeout/lease bounds, not just one client setting.
8. **[Raphael #40: model plumbing](https://github.com/AWaleed-Ahmed/Raphael/issues/40).** Five artifacts exist and the local-model flag defaults on, but the required inference script is absent. Decide wire-or-cut and the flag default before claiming trained inference.
9. **Drift detection: parked.** First decide an authorized source for production specs that does not give Ignis production access; see [PRD §10](prd.md#10-sandbox-and-environment-replication) and [§26](prd.md#26-open-product-decisions). No assigned implementation issue yet.
10. **Forbidden-patch negative scenario: gated.** [PRD §17.8](prd.md#178-llm-role-and-learning-loop-gate) requires it before a generative patch path ships. Do not fabricate an unsafe generator solely to close scenario count; no separate active implementation issue yet.

Other product gates are still open: measured confidence calibration, localization with real Supabase credentials/prove-or-cut results, learning-effectiveness evidence, general real-backend qualification, and the five-authorized-failures partner pilot. Existing code/scaffolding is not proof of these milestones; see [PRD §17](prd.md#17-evaluation-plan) and [pilot runbook](docs/pilot-week-runbook.md).

### Next task checkpoint: Secret coverage (Prompt B)

Read this before implementing #30; these are investigation findings, not shipped features:

1. **Fixture selection already works.** [sandbox_config.py](agent/raphael_agent/sandbox_config.py) reads explicit `RAPHAEL_SECRET_FIXTURE_SET`; unset means none. [orchestrator.py](dispatch/raphael_dispatch/orchestrator.py) snapshots that selection at intake and passes the saved choice in `_create_args()`, including after restart. Ignis applies the named synthetic fixture set. Do not restore an automatic/default fixture or infer authorization from a Secret name.
2. **Applied coverage does not exist yet.** Ignis records the selected fixture set, but has no durable inventory of the names/keys actually applied. Its current `dependencies_available` flag is not proof of per-reference coverage. Compute coverage from final rendered references and successfully applied fixture metadata, never Secret values or value hashes.
3. **Private report validation has a separate gap.** [escalation_report.json](contracts/agent/escalation_report.json) does not allow `production_secret_required` or `privileged_or_host_access`, although current graph code emits them. The diagnosis-only output also emits unlisted `diagnosis_only` and attempt status `completed`. `RunStore.save_run()` serializes records without validating this report schema. Thus passing runtime safety tests is not proof that every persisted report conforms. Review and explicitly scope this correction; it was not fixed by #39 or by this docs update.

The continuation procedure is:

1. Review the preliminary findings and agree the scope of the private report-schema/validation correction. Keep it visible; do not silently widen a schema just to make tests green.
2. Implement the Ignis half on its own reviewed branch: reference-level coverage for `secretKeyRef`, `envFrom.secretRef`, and Secret volumes, including init containers and optional references. Persist only the applied names/key inventory so restart does not recompute history from a changed fixture file.
3. Carry bounded coverage as optional structured fidelity data. Distinguish covered, missing object, missing key and unknown. Unsupported references or truncation make coverage incomplete; missing/old data is unknown, not evidence of coverage or a reason to block. Optional references must never cause escalation.
4. Test positive and negative controls, restart persistence, redaction, and absence of secret values. Kind must compare coverage against actual workload behavior, including a Secret that exists but lacks the required key. Static coverage/outcome evals can use mock; kind supplies the consumption cross-check.
5. Report the Ignis diff and hosted results **before merge or tagging**. The proposed public addition needs a reviewed `contracts-v1.3.0` release, not a silent schema edit or a patch-only tag.
6. Only after the approved Ignis release: update Raphael's snapshot/runtime pins and implement the separate analyzer integration. Required uncovered references produce `unresolved_secret_dependency`; keep it distinct from the existing textual `production_secret_required`, which retains precedence. A covered-reference control must proceed rather than blanket-escalating on all Secret references.

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

Use WSL2/Linux with Python 3.12+, Rust/Cargo, Git, and access to the private Raphael repo.
On this Windows machine, native pytest temp ACLs and the MSVC linker were unreliable; WSL2 is the proven path. Prefer a Linux-native clone/venv. Existing Windows checkouts can be used from WSL with `TMPDIR=/tmp`; Windows-created Git worktrees may need explicit Git directory mapping.

The setup assumes `~/src/raphael` and `~/src/ignis` do not already exist. If they do, use your existing clean checkout or choose new paths consistently; never delete someone's checkout to make these commands work. Private clone access must be configured for **Git inside WSL**, not just a Windows CLI login (this machine already has a working Windows Git Credential Manager helper).

```bash
mkdir -p ~/src ~/venvs
cd ~/src
git clone https://github.com/AWaleed-Ahmed/Raphael.git raphael
git clone https://github.com/AWaleed-Ahmed/Ignis.git ignis
python3.12 -m venv ~/venvs/raphael-dispatch
source ~/venvs/raphael-dispatch/bin/activate
cd ~/src/raphael
python -m pip install -e agent -e dispatch
git -C ~/src/ignis checkout contracts-v1.2.1
cargo build --release --locked --manifest-path ~/src/ignis/controller/Cargo.toml
```

If prerequisites are missing, ask before installing with elevated privileges. Use fresh main branches for development; the tag checkout above is for reproducing the pinned binary.

**Terminal 1: combined Raphael** (local mock development, not a public deployment):

```bash
source ~/venvs/raphael-dispatch/bin/activate
cd ~/src/raphael
unset GITHUB_TOKEN RAPHAEL_GITHUB_TOKEN RAPHAEL_GITHUB_APP_ID RAPHAEL_GITHUB_INSTALLATION_ID RAPHAEL_GITHUB_APP_PRIVATE_KEY RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH
export RAPHAEL_PARTNER_MODE=dry_run RAPHAEL_PUBLISH_MODE=dry_run
export RAPHAEL_LLM_DIAGNOSIS=0 RAPHAEL_LLM_PATCH=0 RAPHAEL_LEARNING=0
export RAPHAEL_AGENT_LISTEN=127.0.0.1:8091 RAPHAEL_DISPATCH_BRIDGE_ENABLED=1
export RAPHAEL_AGENT_DATA_DIR="$HOME/.local/share/raphael-dev"
export RAPHAEL_DISPATCH_TOKENS='{"dev-producer":{"tenant_id":"local-dev","role":"producer"},"dev-connector":{"tenant_id":"local-dev","role":"connector"}}'
TMPDIR=/tmp python run.py
```

**Terminal 2: Ignis** (these token strings are local examples, never production credentials):

```bash
cd ~/src/ignis
export RAPHAEL_CLUSTER_BACKEND=mock RAPHAEL_LISTEN=127.0.0.1:8090
export RAPHAEL_DATA_DIR="$HOME/.local/share/ignis-dev"
export RAPHAEL_CONNECTOR_DISPATCH_URL=http://127.0.0.1:8091
export RAPHAEL_CONNECTOR_CONTROLLER_URL=http://127.0.0.1:8090
export RAPHAEL_CONNECTOR_TENANT_ID=local-dev RAPHAEL_CONNECTOR_TOKEN=dev-connector
./controller/target/release/raphael-sandbox-controller
```

Check `curl http://127.0.0.1:8091/health` and `curl http://127.0.0.1:8090/health`.
A health response is not a submitted job. For verified fixture jobs, stop both manually started services with Ctrl+C in their terminals, then use the owned-process harness below; don't kill unrelated processes to free a port. Webhook setup/auth details are in [agent/README.md](agent/README.md).

### Tests and hosted kind proof

```bash
source ~/venvs/raphael-dispatch/bin/activate
cd ~/src/raphael
(cd agent && TMPDIR=/tmp python -m pytest -q)
(cd dispatch && TMPDIR=/tmp python -m pytest -q)
python -m unittest evals.test_run_evals
export E2E_IGNIS_BIN="$HOME/src/ignis/controller/target/release/raphael-sandbox-controller"
unset GITHUB_TOKEN RAPHAEL_GITHUB_TOKEN RAPHAEL_GITHUB_APP_ID RAPHAEL_GITHUB_INSTALLATION_ID RAPHAEL_GITHUB_APP_PRIVATE_KEY RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH
export RAPHAEL_PARTNER_MODE=dry_run RAPHAEL_PUBLISH_MODE=dry_run
TMPDIR=/tmp python -u e2e/run_e2e.py
TMPDIR=/tmp python -u e2e/run_real_job.py
TMPDIR=/tmp python -u evals/run_evals.py
cd ~/src/ignis/controller
cargo fmt --check
cargo check --locked
cargo test --locked
```

The wire harness uses mock AgentHooks; smoke/evals use real hooks. All three launch/own their processes and clean them up. Reports include real traces/logs; eval output is `evals/out/eval-results.json`. Do not upload private or live-secret traces.

The separate contract drift script requires PowerShell 7 (`pwsh`), not ordinary Bash. It is installed in the hosted `core-ci / contracts` job; if absent in WSL, run `pwsh -File tools/sync-sandbox-contracts.ps1 -Check` from a Windows-native Raphael checkout in PowerShell 7, or use that hosted check. The literal review found `pwsh: command not found` in WSL and an unsigned-script policy rejection against the WSL UNC checkout; the same command passed in a fresh Windows-native worktree. Do not weaken execution policy or install with elevated privileges merely to get past that.

For the real-cluster proof, open **Actions -> Cross-repository E2E -> Run workflow** on the reviewed branch/main. The kind job creates its own disposable cluster and runs four controls; artifacts are `secret-fixture-kind-<run-id>` and `cross-repo-e2e-<run-id>`. It runs on Raphael pushes/PRs, nightly, and repository-dispatch events. The manual `ignis_ref` override affects the mock job; **kind's pin is separately set in YAML**. Never point the job at a customer cluster. Ask before running local cluster creation/deletion or `sudo`.

### Correct environment names

| Variable | Owner / default | Purpose |
|---|---|---|
| `RAPHAEL_AGENT_LISTEN` | Raphael / `127.0.0.1:8091` | Combined server bind address. |
| `RAPHAEL_AGENT_DATA_DIR` | Raphael / `.raphael-agent-data` in cwd | Run records/evidence; do not confuse with Ignis storage. |
| `RAPHAEL_DISPATCH_BRIDGE_ENABLED` | Raphael / `0` | Same-process webhook-to-dispatch bridge. |
| `RAPHAEL_DISPATCH_TOKENS` | Raphael / unset | JSON token -> tenant/role mapping; producer and connector tokens differ. |
| `RAPHAEL_LEASE_REAP_INTERVAL_SECONDS` | Raphael / `10` | Automatic lease-reaper cadence. |
| `RAPHAEL_LISTEN` | Ignis / `127.0.0.1:8090` | Controller bind address. |
| `RAPHAEL_DATA_DIR` | Ignis / `.raphael-data` in cwd | Sandbox/connector/mock recovery records. |
| `RAPHAEL_CLUSTER_BACKEND` | Ignis / `mock` | `mock`, `kind`, `kubectl`, `kubeconfig`; real backends require an approved sandbox-only kubeconfig/context. |
| `RAPHAEL_CONNECTOR_DISPATCH_URL` | Ignis / unset | Enables embedded outbound connector. |
| `RAPHAEL_CONNECTOR_CONTROLLER_URL` | Ignis / `http://127.0.0.1:8090` | Local executor HTTP target. |
| `RAPHAEL_CONNECTOR_TOKEN` / `RAPHAEL_CONNECTOR_TENANT_ID` | Ignis / token required, tenant `connector` | Must match dispatch's connector-role mapping. |
| `RAPHAEL_CONNECTOR_POLL_INTERVAL_MS` / `RAPHAEL_CONNECTOR_HTTP_TIMEOUT_SECONDS` | Ignis / `1000`, `30` | Poll cadence and **dispatch** request timeout; not local deploy timeout (#17). |
| `RAPHAEL_SECRET_FIXTURE_SET` / `RAPHAEL_FIXTURES_DIR` | Raphael selection unset; Ignis fixture path defaults to its bundled fixtures | Explicit synthetic fixture selection; no selection means no fixtures, not automatic coverage. |
| `RAPHAEL_PARTNER_MODE` / `RAPHAEL_PUBLISH_MODE` | Raphael / `dry_run` | Keep both dry-run in automated tests. |
| `RAPHAEL_LLM_DIAGNOSIS` / `RAPHAEL_LLM_PATCH` / `RAPHAEL_LEARNING` | Raphael / `0` | Optional external-model/learning paths; existing code is not proof of effective behavior. |
| `RAPHAEL_MODEL_ENABLED` | Raphael / `1` | Local model gateway; currently unavailable-script fallback (#40). |
| `E2E_IGNIS_BIN` | Harness / required absolute path | Explicit built external binary, never rely on ambient executable resolution. |

Common wrong names: `RAPHAEL_STORAGE_DIR` and `RAPHAEL_BIND_ADDR` do **not** configure Ignis; use `RAPHAEL_DATA_DIR` and `RAPHAEL_LISTEN`. Runtime tokens, webhook signature secrets, interface tokens, and GitHub publishing credentials are different settings.

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
