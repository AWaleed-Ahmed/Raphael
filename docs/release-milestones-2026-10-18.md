# Raphael release milestones — 2026-10-18

## Release scope and count

**Eight major milestones remain for a limited, controlled pilot release.**
This is a planning grouping of the current handoff and acceptance requirements,
not a count of open GitHub issues, an estimate in days, or eight small commits.
No pilot/production release is declared by this document. A general production
release requires pilot evidence and resolution of the risks it exposes.

The pilot cut should retain dry-run default, human-reviewed draft repairs,
explicit supported failure classes/backends, no automatic merge/production
writes and opt-in external models. Broader trained-model, drift-detection or
cloud-provider claims require their own evidence; do not silently include them.

| # | Milestone | Completion evidence |
| --- | --- | --- |
| 1 | Recover/reimplement lost #13/#17 and paired dispatch fixes | Persistent pushed code, renewed review and fresh tests; previous `/tmp` heads and their test counts cannot substitute. See REC/LSE/CLN tasks in the shared completion checklist. |
| 2 | Finish the outstanding structural-Secret safety follow-up | Resolve bundled-Secret/raw-patch boundary, unsupported-form coverage, redaction, fixture scope and sentinel/covered-remediation controls tracked by the handoff and `fix/secret-coverage-safety`. Reviewed paired contracts and no unsafe repair/provider call on required dependency gaps. |
| 3 | Qualify Ignis #11/#13/#17 against one candidate pair | Image attribution/provenance/refusal controls; fidelity/authenticated clone matrix; finite deadlines, short-lease renewal/denial/restart and cleanup. Clearly distinguish parser/mock fixtures from actual kind observations. |
| 4 | Deliver reviewed contracts and exact runtime alignment | User-approved Ignis merge/release; synced Raphael snapshot and `CONTRACTS_VERSION`; all runtime defaults pinned to the reviewed release; contract sync check passes. No existing tag retargeting. |
| 5 | Finish hosted release-candidate regressions | Current-head core/contract/Ignis checks and all paired mock/kind/Secret controls green; positive verified-image repair restored to required checks, with report audit, CRLF and deadline controls. Review sanitized artifacts and repeat after relevant pin/merge changes. |
| 6 | Qualify live provider and baseline paths included in the cut | BYOK regression verification plus synthetic discovery/completion for each provider advertised as live-verified; actual diagnosis/schema/patch-policy controls. Authorized tenant-scoped Supabase baseline write/read/repair and wrong-scope refusal before claiming live ingestion. If a path is excluded, document that cut and keep it disabled rather than declaring it proven. |
| 7 | Freeze supported behavior and install the staging candidate | Decide #40 wire-or-cut: actual inference/evaluation if included, otherwise explicit disabled/unsupported configuration. Document Linux/native-Windows boundary, failure-class/backend support, known graph-persistence limits and conservative failure behavior. Verify clean install, permissions, webhooks, credential handling, recovery and go/no-go in the partner staging environment. |
| 8 | Run the controlled pilot and approve release | At least five authorized real eligible failures in dry-run; record false positives, human accept/reject feedback and GitHub command smokes. Meet pilot acceptance/go-no-go and patch-safety gates; obtain user approval before any allowlisted live draft publication or release tag. |

## Relationship to other documents

- [Detailed #11/#13/#17 completion checklist](ignis-11-13-17-completion-checklist.md)
- [Current handoff](../handoff.md) and its dated safety follow-ups
- [Pilot acceptance](pilot-acceptance.md)
- [Pilot installation](pilot-install.md)
- [Pilot week runbook](pilot-week-runbook.md)
- [BYOK provider setup and limits](byok-provider-guide.md)

Milestones3–5 include candidate and released-pair evidence; one old green run
is insufficient. Provider configuration implemented on this branch does not
complete milestone6. No real provider call or release was performed while
writing this roadmap. This document does not authorize merges, tags, customer
writes or messages to other people.
