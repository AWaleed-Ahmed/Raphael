# BYOK qualification — 2026-10-20

## Scope and environment

Integration note: this live evidence applies to the recorded `8601763` snapshot. The PR is integrated onto `0dc46c4`, whose newer provider adapters (including native Anthropic and additional compatible endpoints) are preserved. Statements about implemented/unsupported providers below describe the tested snapshot, not the newer main branch. No live qualification of those newer adapters is claimed.

- Tested commit: `86017638001c62c0710deacb2eb7bd675d094cff` (`feature/byok-module`, nine commits ahead of `origin/feature/byok-module`).
- Environment: Linux 7.0.0-38-generic x86_64 / glibc 2.39, Python 3.12.3, repository `.venv`. Initially no BYOK configuration was present. The user subsequently supplied an authorized Gemini key; it was entered through a hidden terminal prompt and existed only in the qualification process memory/environment, not repository files or printed output.
- Existing worktree changes were preserved. This qualification changed only the BYOK transport, BYOK tests, setup documentation, handoff, and evidence records. Additional local-inference changes appeared in the shared worktree and were left untouched. No commit, push, PR, GitHub publication, production mutation, deployment, or Ignis sandbox execution occurred. The synthetic model patch was inspected in memory and never applied to a repository.
- Authorized follow-up: the user requested Gemini qualification with as few requests/tokens as possible and a very small synthetic fix. The harness enforced **two completion attempts total**, no live rotation, and **128 maximum output tokens per attempt**. No further live requests were made after the second completion attempt.
- Provider request count: **one authenticated discovery GET + two completion POSTs**. One earlier sandbox-restricted discovery connection failed before a provider response; it made zero completion calls. Network-enabled Linux execution was required. This proves Linux execution with authorized outbound connectivity, not connectivity from the default restricted sandbox or from an Ignis deployment.

## Supported-provider matrix

All entries are provider-specific. `custom_openai` is qualified only per configured endpoint and model. There is no frontend provider selector in the inspected frontend sources.

| Provider/endpoint | Discovery | Automatic selection | Explicit selection | JSON completion | Quota handling | Safe failure | Overall verdict |
|---|---|---|---|---|---|---|---|
| `openai` — `api.openai.com` | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE) |
| `gemini` — `generativelanguage.googleapis.com` | PASS (LIVE) | FAIL (LIVE before fix); PASS (SIMULATED fix); NOT RUN (LIVE after fix) | PASS (LIVE) | PASS (LIVE pinned patch) | NOT RUN (LIVE); PASS (SIMULATED) | PASS (LIVE HTTP 400 refusal); PASS (SIMULATED broader cases) | FAIL (LIVE automatic); pinned patch scope PASS (LIVE) |
| `custom_openai` — no endpoint configured | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE); PASS (SIMULATED) | BLOCKED (LIVE) |

The simulated results are existing and newly extended HTTPX mock-transport/configuration tests, not live provider evidence. Anthropic and Azure are unsupported identifiers and are rejected; they are not provider rows representing implemented support. No gateway or compatible endpoint has been individually live-qualified.

## Live checks — authorized Gemini follow-up

| Case | Expected | Actual |
|---|---|---|
| Restricted Linux sandbox | Reach Google without exposing credentials | Discovery failed with sanitized `provider_transport_error`; zero completions; retried with authorized network-enabled execution |
| Authenticated Gemini discovery | Use native `/v1beta/models?pageSize=1000` and `x-goog-api-key` | PASS: 63 catalog entries, 31 original filtered candidates, no `nextPageToken`, 1.049 seconds |
| Automatic existing `byok_smoke --live` / `complete_json` | Select a discovered model and parse `{"ok": true}` | FAIL: selected discovered `antigravity-preview-09-2026`; compatibility endpoint returned HTTP 400 in 0.854 seconds; sanitized failure, no substitution or rotation. Provider error body/reason was not retained, so the precise reason for rejection is unknown |
| Explicit `try_llm_patch` through real `complete_json` | Bypass discovery; pin an account-listed general-purpose model; produce one tiny policy-valid patch | PASS: requested and returned `gemini-3.1-flash-lite`; no discovery; exactly one POST; 1.979 seconds |
| Patch content / schema / policy | Change only synthetic `deploy/probe.yaml` port `8081` to `8080` | PASS: exact expected one-line content, action `modify`, one file, schema valid, `policy_status=allowed`, no violations; no file applied or code executed |
| Provider usage / completion | Small valid JSON object and complete output | PASS: `finish_reason=stop`; provider reported 255 prompt, 98 completion, 353 total tokens. The failed POST had no reported usage; no account billing total is inferred |
| Live quota semantics | Observe only naturally occurring authorized quota responses | NOT RUN: no 429 observed; quota tests remain SIMULATED |

The smoke used its existing tiny JSON instruction and `{"synthetic": true}` payload. The second POST used the actual patch helper's normal safety instruction and bounded payload; the custom synthetic issue requested only `readinessProbe: {httpGet: {path: /, port: 8080}}`. No repository source, deployment data, or secrets were included in prompts.

Raw sanitized observations are retained in [gemini-linux.json](evidence/byok-2026-10-20/gemini-linux.json). The exact secret-free harness is [qualify_gemini.py](evidence/byok-2026-10-20/qualify_gemini.py); run it with `PYTHONPATH=agent ./.venv/bin/python docs/evidence/byok-2026-10-20/qualify_gemini.py` from the repository and enter a key at the hidden prompt. It invokes existing smoke/transport/patch helpers, caps automatic attempts to one within the harness only, then asks for one discovered explicit model. Production's eight-attempt limit is unchanged. Random selection and future catalogs can change reproduction results.

## Live-discovered candidate defect and minimal correction

`generateContent` metadata and the prior name exclusions admitted unrelated/specialized generation models, including Antigravity, Lyria/music, Nano Banana/image, Omni/video, robotics, and computer-use entries. The live automatic selection failed on one such entry; the provider reason for its HTTP 400 is unknown. Google's [current model guide](https://ai.google.dev/gemini-api/docs/models) distinguishes these specialized families from general text models.

The Gemini-only candidate filter now requires the `gemini-` family and excludes the observed specialized family names, retaining existing nontext exclusions. This changes the observed catalog's candidate count from 31 to 17 when replayed offline. A regression using observed names verifies that specialized entries cannot be selected. No model-version allowlist or cross-provider fallback was added. This reduces demonstrated bad candidates; it does not guarantee every remaining candidate supports JSON mode. The corrected automatic path was **not rerun live**, to honor the two-attempt request limit. Pin the demonstrated model for reproducible use; automatic success remains unqualified.

## Official protocol cross-check

- OpenAI model discovery is `GET /v1/models` with Bearer authentication. The listing provides identifiers and basic availability; it does not establish that a model supports this exact chat/JSON request. OpenAI documents Chat Completions JSON mode using `response_format: {"type":"json_object"}` and requires JSON instructions in the messages. Sources: [model list](https://developers.openai.com/api/reference/resources/models/methods/list), [authentication](https://developers.openai.com/api/reference/overview), [JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat).
- Gemini's configured completion base is the documented OpenAI-compatible `https://generativelanguage.googleapis.com/v1beta/openai/`, using Bearer API-key authentication for `/chat/completions`. Its native model-list endpoint uses `x-goog-api-key`, reports `supportedGenerationMethods`, and supports `pageToken`; the implementation requests at most 1,000 results on one page and does not follow `nextPageToken`. A listed `generateContent` method does not itself prove that the compatibility endpoint supports this exact JSON request. Sources: [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [model list and pagination](https://ai.google.dev/api/models), [Gemini API authentication](https://ai.google.dev/api).
- OpenAI `/models` is a listing, not a chat capability check. Its pagination/coverage for this qualification is limited to the one response returned by the implementation; no exhaustive multi-page catalog was demonstrated.
- OpenAI reports both temporary rate limiting and non-retryable billing/account quota conditions as HTTP 429. Its docs distinguish rate limit errors (`rate_limit_error`, `rate_limit_exceeded`, `slow_down`) from quota/spend errors which require account action. Qualification found and corrected the implementation's prior unconditional OpenAI-429 rotation: automatic OpenAI selection now rotates only for the documented rate-limit identifiers; other/malformed 429s fail with sanitized `provider_http_429`. Sources: [OpenAI rate limits](https://developers.openai.com/api/docs/guides/rate-limits), [OpenAI error codes](https://developers.openai.com/api/docs/guides/error-codes).
- Gemini documents 429 `RESOURCE_EXHAUSTED` for rate/spend limits and recommends bounded backoff for transient 429/503; the current automatic mode instead makes bounded candidate rotation on 429 and does not retry 503. Sources: [Gemini rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [Gemini troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting). This is not live-verified. Custom endpoint quota behavior remains vendor-specific and unqualified.
- `custom_openai` uses Bearer auth and OpenAI-shaped `/models` and `/chat/completions` requests. No endpoint-specific official documentation or configuration was provided, so no custom provider behavior is asserted. Each deployment needs a hostname, documented authentication, catalog behavior, supported model, and successful JSON smoke.
- No native Anthropic Messages API or Azure-specific endpoint/version/auth protocol is implemented. No universal compatibility claim is made for gateways.

## SIMULATED cases and outcomes

Expectations below are exercised by `agent/tests/test_byok.py` and use synthetic credentials/data with `httpx.MockTransport`.

| Case | Expected | Actual |
|---|---|---|
| Provider key precedence / isolation | Selected provider key only; no unrelated provider key fallback | PASS: selected-provider precedence and provider-scoped auth headers |
| Candidate filtering, duplicate entries, empty catalog | Keep supported text candidates, dedupe, and stop on empty/incompatible catalog | PASS: filters and deduplicates; no completion after empty catalog |
| Automatic selection | Chosen candidate comes from discovered set; deterministic ordering tested offline | PASS: mocked order; production order remains randomized |
| First automatic candidate 429 | Rotate once to a distinct discovered candidate | PASS: next model succeeds |
| All attempted candidates 429 | Stop after no more than eight distinct attempts | PASS: `MAX_MODEL_ATTEMPTS == 8`; no repeated candidate |
| Explicit model 429 | One completion attempt; no discovery or substitution | PASS |
| Discovery 429 | Fail without any completion request | PASS: regression asserts only `GET` |
| Shared deadline/attempt bound | No further request after deadline | PASS |
| Authentication, ordinary HTTP errors, timeout, transport error | Sanitized failure; only 429 rotates | PASS |
| OpenAI rate-limit 429 vs account-quota 429 | Rotate to next distinct candidate for documented rate-limit codes; fail immediately for account quota or unrecognized 429 | PASS: rate-limit case rotates; `insufficient_quota` stops after first completion |
| Malformed/empty/non-object JSON and content limit | Fail closed | PASS |
| Oversized request/response and echoed synthetic key | Reject before/while bounded transfer or reject echoed key | PASS |
| Diagnosis and patch caller behavior | Diagnosis returns deterministic fallback; patch returns no unusable proposal; policy gate remains authoritative | PASS: caller and schema/policy tests |
| Unsupported provider / invalid endpoint | Reject configuration before transport | PASS |
| Credential-safe telemetry/run persistence | No configured synthetic key or its hash in tested records | PASS |

The transport returns the selected/requested model in `LLMResponse`; the existing smoke does not expose the provider response's optional `model` field. The qualification harness captured that metadata from the real response without changing request contents: the successful pinned request and returned model matched exactly. No alias was observed or inferred.

## Commands and results

PR integration on current main: the same focused BYOK/diagnosis/patch command below passed **159 tests**. Main's newer adapters were preserved; its shared-provider test fixtures now use Gemini-family model names and documented OpenAI rate-limit error fields. No additional live requests were made.

- Latest `./.venv/bin/python -m pytest agent/tests/test_byok.py -q`: **65 passed**.
- Latest relevant caller suite: `./.venv/bin/python -m pytest agent/tests/test_byok.py agent/tests/test_diagnosis.py agent/tests/test_patch.py agent/tests/test_phase6_issues.py -q`: **117 passed**. These tests use fixtures/mocks; they add no live provider requests.
- `./.venv/bin/python -m pytest agent/tests/test_byok.py agent/tests/test_blocked_model_boundary.py -q`: **85 passed, 1 failed**. The unrelated model-gateway test expected `classify_failure({})` to return `None` when the model script is unavailable, but it returned a schema-shaped abstained prediction. `model_gateway.py`, `graph/nodes.py`, and `test_blocked_model_boundary.py` had local changes during this qualification and were preserved; this is outside BYOK scope.
- `cd agent && ../.venv/bin/python -m raphael_agent.scripts.byok_smoke --live`: **expected safe failure**, exit 1, `llm_key_not_configured`; zero network calls.
- `./.venv/bin/python -m pytest agent/tests -vv -x`: collection found 392 tests, then execution stalled at `agent/tests/test_apm_evidence.py::test_alertmanager_http_endpoint` after seven passes; interrupted without a result. The broader suite is therefore NOT RUN to completion.
- Fixed OpenAI unconditional 429 rotation in the initial offline pass, and tightened Gemini's overbroad generation-candidate filter after the live failure. Regression tests cover both changes plus discovery 429/no completion, catalog deduplication, and empty content. `git diff --check` passes.
- Live timing/usage observations appear above and in the sanitized JSON evidence. Mocked usage normalization checks `prompt_tokens`, `completion_tokens`, and `total_tokens`; unknown usage fields are ignored.

## Remaining blockers and limits

Gemini's key and a small request budget were supplied for the follow-up and used for the recorded run. Its pinned synthetic patch path passes. No more live requests were made after the two-attempt cap. Diagnosis was not called live, corrected automatic mode was not rerun live, and quota/authentication-negative cases remain simulated. Standard sandbox outbound networking needs separate configuration; network-enabled Linux execution passed. A real deployment/repair was not attempted.

For the still-blocked OpenAI/custom providers, supply separately:

1. An authorized key in the documented provider-specific environment variable (or `RAPHAEL_LLM_API_KEY`).
2. For `custom_openai`, the exact base URL/hostname and its vendor's official docs for authentication, model listing, JSON/chat compatibility, and quota errors.
3. An account-approved request budget. The run will stay sequential and use no more than five completion attempts per configured endpoint, stopping earlier when the approved budget requires.
4. An account-available explicit model for one pinned smoke, if explicit-mode live verification is required; unset/`auto` can be used for automatic mode.

OpenAI/custom live discovery and completion remain unverified. No live revoked-key or quota response was induced for Gemini. The Gemini patch pass demonstrates one synthetic one-line proposal through the real helper and its schema/policy gates; it does not establish broad patch quality, diagnosis quality, successful deployment repair, or compatibility of every model in the catalog.
