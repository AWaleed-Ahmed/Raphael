# Open PR review and implementation plan — 2026-10-06

## Checkpoint and assumptions

Latest Raphael main was pulled with `git pull --ff-only origin main` into the existing `docs/contributor-handoff` checkout: `78c5e0e`. The checkout remains on the development branch. Existing untracked `AGENTS.md` and `GEMINI.md` were preserved.

GitHub reports two open Raphael PRs and no open Ignis PRs. This request is investigation and planning; no PR was merged, implementation changed, tests executed, or live provider called.

Recommended first delivery: environment-configured BYOK for the existing optional external diagnosis and patch paths, starting with Gemini and the existing OpenAI-compatible protocol. This is separate from the local classifier gateway tracked by #40. Request-scoped/multi-tenant keys, a settings UI, automatic model discovery, and quota-based rotation need their own explicit scope; the PR currently supplies fields for some of them without implementations.

## Open proposals

| PR | Intended change | Actual state | Merge assessment |
|---|---|---|---|
| [#23 — BYOK module](https://github.com/AWaleed-Ahmed/Raphael/pull/23) | Bring customer keys/models/providers into Raphael; description proposes Gemini testing | Head `d333c71`; one added file, `agent/raphael_agent/byok/models.py`, 218 lines. Defines config, provider enum, messages, requests, responses, validation result, and quota-related fields/error. No transport, key validation service, diagnosis/patch integration, or BYOK tests | GitHub reports clean/mergeable. Existing September checks passed, but do not establish BYOK functionality. Complete and test it before calling it a working module |
| [#32 — real-kind closed-loop remediation](https://github.com/AWaleed-Ahmed/Raphael/pull/32) | Run real agent hooks, Ignis and real Kubernetes through repair/validation | Head `c326cd4`; seven changed files: cluster helpers, runner, backend configuration, fixtures, rollout targeting and decision entry | GitHub reports conflicts. Preserve current targeting/provenance/safety behavior; adapt the useful real-cluster proof rather than accepting obsolete hunks |

## BYOK review findings

- Main's external LLM paths still obtain keys through `diagnosis/config.py` and send OpenAI-style `/chat/completions` requests directly from `diagnosis/llm.py` and `patch/llm.py`. The PR's models are not wired to either path.
- The provider enum lists OpenAI, Anthropic, Gemini, Azure and custom OpenAI, but naming a provider does not implement its request/authentication/response protocol.
- The PR's Gemini default URL is the native API root. It cannot be plugged directly into today's chat-completions transport. Google documents an OpenAI-compatible endpoint at `https://generativelanguage.googleapis.com/v1beta/openai/`: [official compatibility documentation](https://ai.google.dev/gemini-api/docs/openai). Using it is the smallest first integration with the current transport shape; model/structured-output compatibility still needs testing.
- `__post_init__` turns an unspecified model into `random`; `DEFAULT_MODELS` is unused and there is no discovery/selection implementation. Select an explicit model for reproducibility; do not send `random` to the provider.
- Invalid explicit providers silently become custom OpenAI. Substring-based URL detection can misclassify endpoints. Prefer explicit provider selection and parsed-host validation for inferred defaults.
- `from_env` can select Gemini/Anthropic and then fall back to an unrelated OpenAI key. Resolve credentials within the selected provider, with a clearly documented generic-key override.
- `from_dict` accepts nonpositive/nonfinite timeouts, weakly typed keys/URLs/headers and temperatures without proper validation. A whitespace-only environment key also becomes an empty configured key.
- Masked `repr` is useful, but serializing the dataclass still includes the key and headers. Keep credentials outside RunState, durable stores, telemetry, HTTP traces and public envelopes. Avoid logging provider errors that echo credentials or prompts.
- Rotation/quota state and `AllQuotasExhaustedError` are declarations, not a tested quota-handling implementation.

## BYOK: next three implementation steps

### 1. Reconcile the PR and make configuration deterministic

Update `feature/byok-module` with current main. Review its model types individually and retain only those needed by the chosen first delivery. Reuse existing `httpx`; an additional provider SDK is not required for the compatible protocol.

Implement validated provider/model/key/base-URL/timeout configuration. Preserve documented legacy OpenAI environment names. Reject unknown providers, blank keys, malformed URLs, invalid numeric options and unsupported provider/protocol combinations. Keep keys private to configuration/transport. Require an explicit Gemini model verified against the account's available models; preserve the existing OpenAI model behavior unless deliberately changed. Make missing configuration preserve today's disabled/deterministic behavior.

**Verify later:** environment precedence, each retained provider mapping, whitespace keys, invalid providers, URL parsing, positive finite timeouts, masked formatting, and no unrelated-provider key fallback. Import/package the new module from a clean install. No configuration validation should make a provider request.

### 2. Implement a small shared provider transport and integrate both callers

Build one bounded JSON-chat request function for the existing OpenAI-compatible path and Gemini's compatible endpoint. Normalize content and usage; keep schema validation in diagnosis/patch callers. Add explicit adapters for native Anthropic/Azure only if those providers remain in this delivery's advertised support; otherwise reject them clearly until implemented.

Replace duplicated HTTP request handling in the external diagnosis and patch modules with the transport. Preserve the existing enable flags, evidence-redaction boundary, deterministic blocked decisions, structural Secret gate, patch policy, writable path restrictions, budgets and fail-closed behavior. Keep credentials out of the local `ModelGateway` and Ignis's public contract.

Use finite request/output limits and sanitized error codes. Invalid keys, quota/rate limits, network failures or malformed provider JSON must preserve deterministic diagnosis or refuse a model patch. Do not silently change providers or models after failure. If rotation is retained for a later delivery, it needs an explicit ordered model list, a bounded attempt/deadline budget and separate tests; the current random/rotation fields alone are insufficient.

**Verify later:** mock transport tests for request URL/auth/body, valid JSON responses, schema rejection, 401/403/429/5xx, timeout, malformed/empty output, token-usage mapping and credential absence from logs/records. Blocked diagnosis and patch paths must make zero provider calls. Existing provenance and Secret-coverage regressions must continue to pass.

### 3. Prove the integration and document supported behavior

Add integration tests showing a Gemini-configured diagnosis and permitted patch reach the shared transport, while disabled/no-key/blocked paths do not. Use stubbed HTTP responses for routine CI; include full agent, dispatch, evaluator and contract checks. Add an opt-in synthetic live Gemini smoke using a supplied key and explicit model, with external publication disabled. A successful connection alone does not prove correct diagnosis or patch policy.

Record test cases, expected/actual results, flags, provider/model, tested SHA, skips and sanitized artifacts in a dedicated BYOK implementation review. Update setup instructions and the handoff with supported providers, configuration precedence and remaining features. Review the updated PR and require current-head CI before merge.

**Done when:** BYOK actually serves both existing external-LLM call paths, failures stay safe, keys are absent from inspected durable/logging surfaces, and provider claims match tested adapters. Local classifier #40 remains a separate task.

## PR #32 review findings

- Current main already uses the shared `rollout_resource(signature)` helper and refuses missing target identity. The PR's fallback to `deployment/target` would weaken that behavior. Its targeting hunk is superseded.
- The old generic-kubectl schema/backend-name problem described in its decision entry is already resolved in Ignis. Do not reintroduce the misleading backend relabeling from superseded Ignis PR #15.
- Main's bad-image scenario now expects `escalated / patch_value_unavailable` without verified healthy-image provenance. PR #32's claim that both scenarios should automatically finalize cannot be reused unchanged.
- Its proposed decision ID `D-20260930-01` already exists on main. Add a new dated proof entry rather than duplicating or replacing historical decisions.
- `ensure_docker_running` attempts to start a system service. The runner also reuses a default cluster and deletes namespaces by broad prefix before/after testing. Use a dedicated disposable cluster with tracked ownership and exact cleanup; do not sweep an existing development cluster.
- Preload failures are logged and ignored; lifecycle cleanup is not protected by `finally`. Required image preparation must fail clearly and cleanup must run on failed/aborted scenarios.
- The two fixture changes affect the shared mock scenario set. Prefer separate immutable kind fixtures/manifests so existing mock/injection-equivalence proofs remain reproducible.
- Existing hosted kind work proves narrow Secret consumption/digest controls, not the general repair loop proposed here. The remaining loop proof is useful, but it needs fresh evidence against today's pinned release and policies.

## PR #32: next three implementation steps

1. **Reconcile with main and retain the useful delta.** Preserve current rollout identity, image provenance, schema/runtime pins and safety gates. Retain backend/context parameterization and a simplified kind runner; drop superseded targeting/backend fixes and duplicate decision claims. Keep current mock fixtures and use separate versioned kind scenario definitions. Verify later: unchanged mock/evaluator expectations and explicit fixture identity for each kind case.
2. **Make cluster ownership and scenarios precise.** Use an isolated disposable hosted cluster, explicit context, required image preloads, tracked test resources and `finally` cleanup. Prove probe failure -> minimal target-only patch -> actual Ready rollout -> `fix_finalized`. For bad image, first prove no-provenance refusal with no patch; a success control requires seeded, explicitly verified/scoped healthy baseline metadata and an independently available replacement image. Verify later: actual Kubernetes failure/readiness observations, exact patch scope, signature clearance, terminal reason, cleanup, and no publication.
3. **Add the hosted gate and record fresh proof.** Run current pinned Ignis with real hooks and dry-run publication; retain fixture SHAs, Pod/events snapshots, patch/validation outcomes and traces as artifacts. Run existing mock/core/Secret-kind regressions too. Document exactly which cases passed, add a new decision entry and update the handoff. Merge only after review and current-head checks; historical local claims do not substitute for the updated proof.

## Recommended order

Finish #23 first, in its own updated feature branch, with explicit Gemini support and repeatable transport tests. Then modernize #32 as a separate proof PR. Neither needs an Ignis contract change for the scope described here. Keep #40 local inference runtime and Ignis #11/#17 outside these PRs unless separately assigned.

## Accepted steering during implementation

The user superseded explicit-model-only selection: automatic mode must discover models available to the key, select randomly and rotate on quota/rate limits; an explicitly chosen model stays pinned. The user confirmed Gemini, OpenAI and compatible gateways first. The implemented behavior and proof limits are recorded in `docs/byok-implementation-review-2026-10-06.md`. The original proposal above remains the investigation checkpoint, not the final selection requirement.
