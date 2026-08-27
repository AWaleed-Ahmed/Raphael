# Raphael

Raphael is a self-healing deployment agent for Kubernetes teams. It detects deployment failures, investigates evidence, proposes a narrow change, validates that change through an isolated sandbox, and opens a reviewable pull request. Production remains read-only by default.

## Repository boundary

This repository contains the private-core agent, orchestration contracts, telemetry integration, and the validation-only `dispatch/` service. The sandbox executor is maintained separately in [Ignis](https://github.com/AWaleed-Ahmed/Ignis).

The core repository vendors only the public sandbox contract snapshot under `contracts/sandbox/`. Its exact source is recorded in `CONTRACTS_VERSION` and must be refreshed only with `tools/sync-sandbox-contracts.ps1`. Run the script with `-Check` to fail if the committed snapshot drifts from the pinned Ignis tag.

The agent communicates with a sandbox through the typed HTTP client in `agent/raphael_agent/sandbox_client/` and a configured `RAPHAEL_SANDBOX_URL`. It must not import or execute a local sandbox controller, harness, kind bootstrap, shell command, or arbitrary kubectl action.

## Layout

```text
agent/       Private Python/LangGraph agent and its tests
dispatch/    Private Starlette protocol-validation scaffold
contracts/   Versioned JSON Schema snapshots and agent contracts
tools/       Contract synchronization and verification tools
docs/        Private operating, permission, and pilot documentation
frontend/    Operator-facing frontend
supabase/    Telemetry migrations and integration documentation
```

## Quick start

Install the agent and dispatch dependencies in their respective package directories, then configure the agent to use an authorized sandbox URL. The existing test suites can be run independently with `pytest -q` from `agent/` and `dispatch/`.

To verify the contract snapshot:

```powershell
powershell -ExecutionPolicy Bypass -File tools/sync-sandbox-contracts.ps1 -Check
```

To run the agent HTTP service locally:

```powershell
cd agent
python -m uvicorn raphael_agent.http_api.app:app --host 127.0.0.1 --port 8091
```

The dispatch scaffold listens on port `8092` when started through its package entry point. It validates connector-v1 envelopes and exposes a fixed placeholder action only; it is intentionally not a reasoning, retry, budget, or terminal-selection loop.

## Safety principles

- Evidence precedes action, and uncertainty is visible.
- The sandbox boundary is typed, outbound-only, and limited to the six approved verbs: `create_sandbox`, `deploy_revision`, `observe_failure`, `run_validation`, `finalize_result`, and `destroy_sandbox`.
- Credentials, model keys, prompts, ranking, patch generation, GitHub integrations, and Supabase integrations remain in the core deployment and are never part of Ignis or the public contract schemas.
- Delivery is human-controlled through pull requests; automatic merge, production mutation, secret reads, and arbitrary shell or kubectl actions are prohibited.

Rules for contributors are in [`CODING_RULE.md`](CODING_RULE.md). Project decisions are recorded in [`decision.md`](decision.md).
