# Agent contracts

Frozen JSON Schema documents for the Raphael agent track (Engineer B).

Change these **before** changing Python Pydantic / TypedDict models or graph fixtures.

These shapes are **compatible with** [`contracts/sandbox/`](../sandbox/): when an agent field holds a sandbox type, it `$ref`s the sandbox schema (or documents the same wire shape).

## Schemas

| Schema | Purpose |
|---|---|
| `run_record.json` | Durable / inspectable run state (LangGraph state object) |
| `ingest_decision.json` | Webhook/event accept outcome (dedupe / cooldown / concurrency) |
| `evidence_item.json` | Single evidence item with provenance + redaction flags |
| `diagnosis_result.json` | Ranked hypotheses, confidence, structured classification |
| `patch_proposal.json` | Constrained file/path change candidate |
| `publish_result.json` | Draft PR publication outcome (`result_id`, branch, dry_run/live) |
| `budget_snapshot.json` | Wall/attempt/cost caps captured at run start |
| `feedback_event.json` | FR-065 human/PR outcome audit event (jsonl) |
| `learning_snapshot.json` | Offline priors from feedback (Post-MVP learning loop) |
| `escalation_report.json` | Safe stop: why no PR, what was tried, next checks |
| `fix_rules.json` | Preset/derived Route B writable-path + must/must-not constraints |

## Compatibility notes

- `failure_signature` → [`../sandbox/failure_signature.json`](../sandbox/failure_signature.json)
- `validation_results` → [`../sandbox/validation_results.json`](../sandbox/validation_results.json)
- `result_id` / frozen record → [`../sandbox/validated_fix_record.json`](../sandbox/validated_fix_record.json)
- Sandbox lifecycle remains six verbs (+ health / GET result); agent never gets raw kubectl.
- `run_record.failure_fingerprint` + `correlation` support FR-003/004 ingest.
- Publish is **draft-only** on Route A; Route B delivers an **issue fix snippet** (human opens the PR).
- `RAPHAEL_PUBLISH_MODE=dry_run` (default) never mutates GitHub.

## Terminal statuses

Graph terminals:

- `success_draft_pr_ready` — validated `result_id` + draft PR publish attempted (dry-run or live)
- `success_fix_proposed` — Route B fix snippet prepared/posted; developer opens the PR
- `escalated` — insufficient confidence / unreproducible / policy / budget / model required
- `failed_closed` — mandatory check unavailable or system error

Ingest-only decisions (see `ingest_decision.json`) do not always create a run.
