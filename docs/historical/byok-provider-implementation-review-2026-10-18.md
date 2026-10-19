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
| BYOK focused regression | **100 passed**, including all nine presets, discovery/quota rotation and Anthropic error/output handling |
| Full agent regression | **438 passed, 4 skipped** |
| Full dispatch regression | **77 passed** |
| Evaluator + kind-proof assertion tests | **27 passed**; these do not create a real kind cluster |
| Contract snapshot | **26 files identical** to annotated `contracts-v1.3.0` / `176a13e1a580f4699eba17800bfd2932e5fcaf1c`; Git/SHA-256 check used because PowerShell is unavailable |
| Hosted CI | Pending the push to main; local results are not hosted results |
| Actual live provider smoke | Not run; replacement key must be configured locally |

No provider was live-qualified by mocked results or by compilation. The key
posted in chat was not used or persisted. Credential values must stay outside
repository artifacts; use the hidden terminal prompt in the setup guide.

## Remaining qualification

1. Preserve the passing BYOK, safety, schema and patch-policy suites. New
   coverage checks every named preset's key precedence/auth/discovery and
   quota rotation, pinned models, Anthropic text/error/usage handling, catalog
   metadata filtering and malformed/truncated output. Existing exhaustion and
   deadline tests also pass.
2. Expand provider-specific cases if actual live qualification exposes a gap.
3. Run authorized synthetic live smoke on the providers being advertised as
   live-verified, with fresh locally configured keys; record provider/model,
   timestamp and outcome without raw credentials/responses.
4. Exercise actual diagnosis/patch integration with sanitized fixtures; a
   JSON connectivity success is not successful remediation proof.
5. Review current-head CI before merge/release. Azure/Bedrock/Vertex native
   auth and request-scoped multi-tenant credential management remain excluded.

See [setup and official references](byok-provider-guide.md) and the
[eight release milestones](release-milestones-2026-10-18.md).

## Regression execution and push readiness

User authorized committing and pushing to main on 2026-10-18 conditional on
regression results. Code/test head `2a969bc` passed the checks above. Commands:

```bash
PYTHONPATH=agent:dispatch python -m pytest agent/tests/test_byok.py -q
PYTHONPATH=agent:dispatch python -m pytest agent/tests -q
PYTHONPATH=dispatch:agent python -m pytest dispatch/tests -q
PYTHONPATH=agent:dispatch python -m unittest evals.test_run_evals e2e.test_kind_verification
```

The first combined agent+dispatch invocation stopped at collection because
both use `tests.conftest`; independent suite invocations above passed. That
collection failure was not masked or counted as a pass. Deprecation warnings
remain for Starlette/AnyIO and `jsonschema.RefResolver`. No model-provider
request, real-kind job or live publication was performed in these tests.

Manual diff review confirmed no deployment/workflow/contract changes, existing
safety gates retained, provider errors sanitized, and a fast-forward path from
main `4951de9`. The positive bad-image kind case is still tracked as pending
in the existing workflow; generic green CI does not close #11/#13/#17.
