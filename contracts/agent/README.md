# Agent contracts

Frozen JSON Schema documents for the Raphael agent track (Engineer B).

Change these **before** changing Python Pydantic / TypedDict models or graph fixtures.

These shapes are **compatible with** [`contracts/sandbox/`](../sandbox/): when an agent field holds a sandbox type, it `$ref`s the sandbox schema (or documents the same wire shape).

## Schemas

| Schema | Purpose |
|---|---|
| `run_record.json` | Durable / inspectable run state (LangGraph state object) |
| `evidence_item.json` | Single evidence item with provenance + redaction flags |
| `diagnosis_result.json` | Ranked hypotheses, confidence, structured classification |
| `patch_proposal.json` | Constrained file/path change candidate |
| `escalation_report.json` | Safe stop: why no PR, what was tried, next checks |

## Compatibility notes

- `failure_signature` → [`../sandbox/failure_signature.json`](../sandbox/failure_signature.json)
- `validation_results` → [`../sandbox/validation_results.json`](../sandbox/validation_results.json)
- `result_id` / frozen record → [`../sandbox/validated_fix_record.json`](../sandbox/validated_fix_record.json)
- Sandbox lifecycle remains six verbs (+ health / GET result); agent never gets raw kubectl.

## Phase 0 terminal statuses

Stub graph terminals (may be refined toward PRD §9.3 names in later phases):

- `success_draft_pr_ready` — validated `result_id` present; publish is still a no-op placeholder
- `escalated` — insufficient confidence / unreproducible / policy / budget
- `failed_closed` — mandatory check unavailable or system error
