# BYOK provider expansion — implementation record

Date: 2026-10-18. Branch: `feature/byok-provider-support`.
Base includes the completion-checklist preservation checkpoint at `5ab6226`.

## Implemented

- One data registry for nine named providers: OpenAI, Gemini, Anthropic,
  Groq, OpenRouter, Together AI, Mistral, DeepSeek and xAI, plus the existing
  custom-compatible endpoint option. Selected-provider environment resolution
  retains generic/named override precedence and avoids unrelated-key fallback.
- Existing diagnosis and patch integrations continue calling `complete_json`.
  One transport and model-attempt loop are reused for every provider.
- Small native Anthropic wire translation: model list, version/key headers,
  top-level system message, Messages request, text blocks and token usage.
  Other providers share Chat Completions request/response handling.
- Shared JSON-only prompt; strict object parsing and key-echo rejection.
  Known truncated/filtered/tool-only finishes are rejected. Anthropic requires
  a completed text turn; JSON formatting there is prompt-based, not a native
  schema guarantee.
- Discovery filters advertised chat/output/JSON capabilities when present.
  Automatic random selection and429-only rotation remain bounded to eight
  distinct models. Explicit models remain pinned. No provider/key rotation.
- Updated the existing unsupported-provider expectation to reflect Anthropic
  support. No new package dependency, graph, endpoint or tenant-key store.

## Checks performed

| Check | Result |
| --- | --- |
| Python compileall for BYOK and existing smoke CLI | Passed |
| `git diff --check` | Passed |
| Manual source inspection against official API docs | Completed; Together default uses current `.ai` endpoint because redirects are disabled |
| mypy / ruff | Not installed in the project environment; no type/lint pass claimed |
| Regression tests / hosted CI | Not run for this implementation; must pass before release |
| Actual live provider smoke | Not run; replacement key must be configured locally |

No provider was live-qualified by mocked results or by compilation. The key
posted in chat was not used or persisted. Credential values must stay outside
repository artifacts; use the hidden terminal prompt in the setup guide.

## Remaining qualification

1. Run existing BYOK, safety, schema and patch-policy regression suites.
2. Add/request coverage for each new preset's key precedence/auth/discovery,
   native Anthropic text/error/usage handling, metadata filtering, quota
   exhaustion, pinned models and malformed/truncated output.
3. Run authorized synthetic live smoke on the providers being advertised as
   live-verified, with fresh locally configured keys; record provider/model,
   timestamp and outcome without raw credentials/responses.
4. Exercise actual diagnosis/patch integration with sanitized fixtures; a
   JSON connectivity success is not successful remediation proof.
5. Review current-head CI before merge/release. Azure/Bedrock/Vertex native
   auth and request-scoped multi-tenant credential management remain excluded.

See [setup and official references](byok-provider-guide.md) and the
[eight release milestones](release-milestones-2026-10-18.md).
