# BYOK implementation review — 2026-10-06

Branch: `feature/byok-module`, updating [PR #23](https://github.com/AWaleed-Ahmed/Raphael/pull/23). Current main `78c5e0e` was merged into the existing branch before implementation.

## Scope and user steering

The user requested multiple-model support: discover models available to the selected key, select randomly when no model is chosen, rotate after quota/rate-limit exhaustion, and preserve an explicitly chosen model. The user confirmed Gemini, OpenAI and compatible gateways first. This supersedes the initial plan's explicit-model-only/no-rotation recommendation.

Implemented environment-based configuration and shared external diagnosis/patch transport. No keys are added to RunState, public contracts, Ignis or the local classifier gateway (#40). Native Anthropic/Azure adapters, request-scoped tenant keys and UI remain outside this delivery.

## Behavior

- Selected-provider key resolution: generic `RAPHAEL_LLM_API_KEY` override, then that provider's named environment variables. No unrelated-provider fallback. Legacy OpenAI names are retained.
- Missing/blank/`auto`/`random` model uses automatic mode. An explicit model makes one completion request and never rotates or silently substitutes a different model.
- Automatic mode makes one authenticated catalog request scoped to that key, shuffles filtered text candidates and attempts each candidate at most once. Gemini reads `supportedGenerationMethods` from its native models endpoint; OpenAI/compatible gateways use `/models`.
- Only HTTP 429 triggers rotation. Authentication, malformed output, schema failure, network errors and non-quota HTTP failures fail closed. Discovery errors do not provoke completion calls.
- Maximum eight completion attempts, cooperative shared deadline from the configured timeout (maximum 60 seconds), maximum ten-second catalog timeout. HTTPX phase timeouts also remain finite. Catalog lookup is one page, not an exhaustive unlimited crawl. No cross-key cache or durable key hashes.
- Requests, provider responses and parsed content have byte limits; response redirects are disabled. Configured keys echoed in content are rejected. Provider error bodies and raw provider responses are not persisted/logged.
- Successful diagnosis telemetry names the actual selected model and normalized usage. Patch schema validation, path policy, existing redaction and deterministic safety gates are preserved.

Catalog listing establishes discoverable candidates, not a guarantee of remaining quota, JSON/chat compatibility, or successful inference. Filtering is conservative: Gemini generation capability plus nontext name exclusions; OpenAI chat-family prefixes and exclusions; compatible gateways use text-name exclusions. An explicit model can be used for models outside those discovery filters. Shared account/project limits may exhaust every candidate; rotation fails closed rather than guaranteeing recovery.

Sources: [Google model listing](https://ai.google.dev/api/models), [Google OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [OpenAI model listing](https://developers.openai.com/api/reference/resources/models/methods/list), [OpenAI rate limits](https://developers.openai.com/api/docs/guides/rate-limits). Endpoint/availability semantics were checked against official documentation on this date.

## Review finding corrected

The pre-existing #30 graph gate ran after `diagnose`, whose optional external refinement could already have sent evidence. The authoritative bounded coverage check is now shared by the graph and external diagnosis/patch helpers. Known required Secret gaps stop provider calls; deterministic textual blocks retain priority. Direct helper calls on blocked/escalated/failed-closed runs also stop before key lookup/network work.

## Test cases and results

| Cases | Expected / actual |
|---|---|
| Provider-specific/generic key precedence; two different keys | Correct key used for each catalog/completion, no cross-key state — passed |
| Unknown/native unsupported provider; malformed URL/key/timeout/token limit | Explicit sanitized configuration rejection — passed |
| Legacy key names and loopback compatible endpoint | Existing OpenAI environment support preserved — passed |
| Gemini catalog includes text, embedding and image models | Only supported text candidates selected — passed |
| Automatic model A returns 429; model B succeeds | One discovery, A then B, actual B reported — passed |
| Explicit model returns 429 | No discovery or substitution; one failure — passed |
| Twenty quota-limited candidates | At most eight distinct completion attempts; exhaustion error — passed |
| Deadline expires after a limited candidate | No next model request — passed |
| Empty/malformed/unsupported catalog | No completion request — passed |
| 301/401/403/429/500, timeout/connection error | Sanitized errors; no credential/provider-body echo — passed |
| Invalid/empty/nonobject JSON; request/response/content limits; key echo | Reject output/input safely — passed |
| Gemini-configured diagnosis and patch | Shared transport reached; schema and writable-path policy enforced — passed |
| Disabled/no-key/invalid config/textual block/structural gap | Zero provider completion calls — passed |
| Saved run + diagnosis telemetry with seeded key | Key and its SHA-256 absent from inspected JSON/JSONL files — passed |

Commands/results:

- `./.venv/bin/python -m pytest agent/tests/test_byok.py -q`: **58 passed**.
- `./.venv/bin/python -m pytest agent/tests -q`: **386 passed, 4 existing optional-integration skips**.
- `(cd dispatch && ../.venv/bin/python -m pytest tests -q)`: **77 passed**.
- `./.venv/bin/python -m pytest evals/test_run_evals.py -q`: **10 passed**.
- `git diff --check`: clean before commit.

Development failures were fixed before the passing runs: reused fake HTTP clients and a disabled-flag test setup, plus the JSON import needed by the recorded-response loader after extracting the coverage helper. Tests use HTTPX MockTransport, not live provider calls. Existing Starlette/jsonschema deprecation warnings remain.

## Remaining verification / delivery

No live Gemini key is configured in this process, so the opt-in live smoke was not run. `python -m raphael_agent.scripts.byok_smoke --live` sends only a synthetic connectivity request and reports the actual selected model. It must not be described as a successful real diagnosis or repair proof. Native provider adapters and tenant-key management remain unimplemented.

Hosted core, contract and cross-repo gates are required on the updated PR head before merge. Their status/results will be linked in the delivery record. The separate real-kind remediation PR #32 is the next workstream; BYOK does not replace that proof or claim #40 is complete.

## Hosted verification of implementation `fa3d024`

All checks passed: [core CI 37438867760](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37438867760) (Python and exact contract snapshot) and [cross-repo 37438867823](https://github.com/AWaleed-Ahmed/Raphael/actions/runs/37438867823) (three wire scenarios, real-hook smoke, seven scored outcomes, six Secret-kind controls). A second core run also passed. External-provider success remains a mocked-transport claim; these hosted integrations keep external models disabled. No live Gemini smoke is claimed. The documentation delivery commit records this evidence before merge and its exact-head checks are also required.

## Final CI follow-up

The documentation head's push-only audit job exposed a pre-existing save/read race in the test audit wrapper during automatic lease reaping (run 37439979212). The PR merge check passed, but the failed push check was investigated rather than ignored. The audit now holds each store's existing reentrant lock across its save/read pair. Runtime persistence behavior is unchanged. A regression checks lock ownership and schema-path-only output. Audit-enabled reruns: **386 agent passed / 4 skipped, 77 dispatch passed**. Fresh checks are required for this correction.
