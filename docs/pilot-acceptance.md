# Pilot / MVP acceptance checklist

Updated 2026-10-20. [PRD §23](../prd.md#23-mvp-acceptance-criteria) remains the
product target. Implementation, fixture proof and partner acceptance are distinct.
Use the [release milestones](release-milestones-2026-10-18.md) for linked evidence.

## Implementation and qualified scope

| Capability | Current status | Acceptance limit |
| --- | --- | --- |
| Combined agent/dispatch, webhook ingest, dedupe, audit and feedback | Implemented; local startup/HTTP checks and hosted regression evidence | Not a complete partner webhook/UI journey. |
| Kubernetes event intake | Opt-in webhook/file watcher adapters implemented | A deployed production watcher and customer observer permissions are unqualified. |
| Probe and image repairs | Scoped deterministic fixture proofs; Linux kind genuine missing-image repair with independent Ready check | No arbitrary registry/Kubernetes coverage; no ≥5-class claim. Missing config refuses. |
| Structural Secret and image provenance gates | #30/#33/#34/#37 completed; Linux controls and scoped policy evidence | No plaintext production Secret access; live Supabase ingestion remains unqualified. |
| Draft publication and commands | Implemented; default dry-run, commands/comments/Checks opt-in | Earlier disposable live draft is not partner approval. `cancel`, `diagnose`, `fix` exist with gates. |
| Persistence and leases | Single-instance JSON/SQLite and separate Ignis journal/recovery | Executable patch bytes remain ephemeral; some restarts fail closed. No horizontal scaling qualification. |
| Local model | Runtime absent in a clean checkout; pilot explicitly disables | #40 open; default-off deferral delivered by merged #59, not runtime implementation. |
| External models | Ten adapter identifiers on main; external calls off by default | Narrow earlier pinned Gemini helper success only; PR #58 merged, corrected auto selection not rerun live. |
| Localization and learning | Catalog/localization, feedback and offline prior tooling implemented | Live baseline ingestion and measured benefit unqualified; learning remains off. |
| GitHub App auth | Backend implementation exists | Customer App provisioning/token permissions require qualification. |
| Cleanup/safety | Scoped mock/kind cleanup, negative cases and deterministic gates tested | No universal isolation/leak/prompt-injection guarantee or customer SA certification. |

## Local installation

- [x] Fresh package installation, locked executor build, frontend build, combined startup, health/auth and recorded smoke: [execution record](pilot-local-preflight.md).
- [ ] Full browser workflow against authenticated deployment.
- [ ] Customer-specific source access and webhook reachability/HMAC.

## Real partner gates (pending)

- [ ] Follow [canonical installation](pilot-install.md) and review [permissions](permission-matrix.md).
- [ ] Record authorized repositories, immutable revisions, staging scope and operator signoff.
- [ ] Confirm observer cannot mutate production or read Secret payloads; Ignis receives only sandbox access.
- [ ] Keep partner/publish dry-run, empty live allowlist, model/learning and GitHub mutations off during basic qualification.
- [ ] Review at least five real eligible dry-run failures with evidence, terminal result and human judgments.
- [ ] Measure ≥5 benchmark reproductions, ≥4/5 correct minimal patches and three timed full demos separately; a recorded stub does not satisfy these PRD targets.
- [ ] Qualify any selected Supabase/BYOK path and wrong-scope/refusal controls before claiming it in the pilot cut.
- [ ] Review false positives, policy blocks and cleanup; record go/no-go with the partner.
- [ ] Separately authorize one live draft class, scoped GitHub credentials and human review before publication; never auto-merge.

Follow the [milestone runbook](pilot-week-runbook.md). No calendar commitment
or completed customer-pilot result is implied.

## Deferred or outside scope

Horizontal SaaS scaling, other CI hosts and generalized failure-class coverage
remain future work. Local inference is deferred by merged #59; #40 remains open. Learning is off
pending measured benefit. Production mutation and automatic merge remain prohibited.

## Supabase localization cut — 2026-10-20

Defer live healthy ingestion, real-JWT tenant access, approved-image sandbox repair
and measured production localization benefit. The authorized
[database migration checks](supabase-migration-validation-2026-10-20.md) passed
31 assertions under SQL roles with simulated claims; fixture cleanup was verified. Catalog assistance defaults
off (`RAPHAEL_HEALTHY_CATALOG_ENABLED=0`); credentials alone do not enable it.
The 20-case synthetic replay had 4 wins, 15 ties and 1 regression, with zero unsafe
image approvals; it is not live ingestion or deployment evidence. Opt-in requires
an authorized test project plus fixed backend company/client scope. Missing or
wrong-scope baselines must continue to refuse image repair. See the
[qualification record](supabase-localization-qualification-2026-10-20.md) for verdicts,
controls, outstanding inputs and the runnable live procedure.
