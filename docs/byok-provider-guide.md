# Live BYOK provider guide

Updated 2026-10-18. Implementation branch: `feature/byok-provider-support`.

## Shared implementation

Diagnosis and patch generation both call
`raphael_agent.byok.client.complete_json(config, system=..., payload=...)`.
Provider defaults and key names live in one `PROVIDERS` registry. One bounded
HTTP request function handles authentication, response limits and sanitized
errors. One orchestration loop performs discovery, selection and quota rotation;
only wire request/response translation differs for Anthropic Messages versus
OpenAI-compatible Chat Completions. No new provider SDK dependency is needed.

The adapter makes actual HTTP requests when enabled and configured. This
implementation claim is distinct from live qualification with every provider.
No provider is guaranteed to work with every model in its catalog.

## Named providers

| Provider setting | Standard key variable | Default API base | Protocol |
| --- | --- | --- | --- |
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1` | Chat Completions + JSON object |
| `gemini` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` | Compatible Chat Completions + native discovery |
| `anthropic` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | Native Messages; prompt JSON + strict local parse |
| `groq` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` | Compatible Chat Completions |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | Compatible Chat Completions |
| `together` | `TOGETHER_API_KEY` | `https://api.together.ai/v1` | Compatible Chat Completions |
| `mistral` | `MISTRAL_API_KEY` | `https://api.mistral.ai/v1` | Compatible Chat Completions |
| `deepseek` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` | Compatible Chat Completions |
| `xai` | `XAI_API_KEY` | `https://api.x.ai/v1` | Compatible Chat Completions |
| `custom_openai` | `RAPHAEL_LLM_API_KEY` | Set `RAPHAEL_LLM_BASE_URL` | Compatible gateway/self-hosted endpoint |

Compatible providers/models must accept `response_format={"type":"json_object"}`
and text chat messages. Tool-only, image/audio generation, embedding and
Responses-only models are not supported through this adapter. Anthropic uses
`x-api-key` and `anthropic-version` instead of a Bearer header; its system prompt
is top-level. No OpenAI response-format parameter is sent to Anthropic.
Azure deployments, Bedrock SigV4, Vertex service-account authentication and
provider-specific non-compatible APIs need separate adapters. Fireworks,
Cerebras, NVIDIA, Ollama, vLLM and LiteLLM endpoints can be configured through
`custom_openai` when the selected endpoint/model implements this protocol;
they are not separately live-qualified presets in this change.

## Key selection and model behavior

Key precedence: `RAPHAEL_LLM_API_KEY`, then
`RAPHAEL_<SELECTED_PROVIDER>_API_KEY`, then the table's standard variable(s).
There is no fallback to another provider's key. Supply configuration through
the deployment environment or secret manager; the application does not load
an arbitrary `.env` file automatically. Keys are excluded from config repr,
run persistence and model-call telemetry. Do not commit keys or post them in
chat. If a key has been exposed, revoke it and use a replacement.

- Set `RAPHAEL_LLM_MODEL` to pin a model. It skips discovery and never rotates.
- Unset it, or use `auto`/`random`, for one catalog request, conservative text
  filtering, randomized selection and up to eight distinct completion attempts.
- HTTP429 rotates only in automatic mode, inside the shared configured time
  budget. Authentication failures, malformed output and other errors stop;
  the adapter does not rotate provider credentials or silently downgrade policy.
- Discovery uses the selected key but some catalogs are public/global. Listing
  does not establish entitlement, quota or JSON/chat support. Advertised
  capabilities are filtered where available; otherwise compatibility must be
  established with a smoke or an explicit known-compatible model.
- Discovery examines only the first page (up to1000 for Gemini/Anthropic),
  with a10-second catalog timeout. There is no persistent cross-key cache.
- Anthropic input/output token counters are normalized to the shared telemetry
  fields; total is their sum, not an invoice including cache-specific charges.
- Truncated, filtered, non-JSON, non-object and key-echoing responses fail
  closed. Existing diagnosis schema validation and patch policy still apply.

## Local Gemini setup and synthetic live smoke

Use the project Python environment with agent dependencies installed. From the
repository root, set configuration in the same terminal used to launch Raphael:

```bash
export RAPHAEL_LLM_PROVIDER=gemini
read -rsp 'Gemini API key: ' GEMINI_API_KEY
export GEMINI_API_KEY
printf '\n'
# Leave RAPHAEL_LLM_MODEL unset for discovery/random selection.
PYTHONPATH=agent python -m raphael_agent.scripts.byok_smoke --live
```

The prompt keeps the key out of shell history. The synthetic smoke requests
`{"ok":true}` and prints only provider/model and pass/fail. It is a connectivity
check, not proof of diagnosis quality, successful repair or publication.
An automatic smoke can issue discovery plus several quota-limited completion
attempts; setting a model limits it to one completion attempt.

To enable the existing application paths after qualification:

```bash
export RAPHAEL_LLM_DIAGNOSIS=1
export RAPHAEL_LLM_PATCH=1
```

Restart the application with this environment. Both features remain opt-in;
a failed or unconfigured optional call retains the existing deterministic
behavior. Keys here belong to the deployment operator; this is not a
multi-tenant key-upload/encryption/rotation service.

For another provider, change `RAPHAEL_LLM_PROVIDER` and set its matching key.
For a compatible gateway, additionally set `RAPHAEL_LLM_BASE_URL` to its base
including `/v1` where appropriate. Use HTTPS; explicitly configured loopback
OpenAI/custom gateways may use HTTP. URLs cannot embed credentials or query
parameters, and redirects are disabled.

## Qualification record for this change

Python compilation and diff checks are recorded in the implementation review.
No real-provider success is claimed. No provider key was configured in the
process environment during implementation. A credential was pasted into chat;
it was not copied into source, logs, configuration or provider requests.
Configure a replacement locally before the live smoke. Routine hosted suites
remain independent of provider credentials. Existing unsupported-provider test
expectations were updated for the new Anthropic support; no test suite was run
for this change yet.

## Official protocol references

- [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create) and [model discovery](https://platform.claude.com/docs/en/api/models/list)
- [Groq compatibility](https://console.groq.com/docs/openai)
- [OpenRouter models/capabilities](https://openrouter.ai/docs/api/api-reference/models/list-all-models-and-their-properties)
- [Together compatibility](https://docs.together.ai/docs/inference/openai-compatibility)
- [Mistral chat](https://docs.mistral.ai/api) and [models](https://docs.mistral.ai/api/endpoint/models)
- [DeepSeek JSON output](https://api-docs.deepseek.com/guides/json_mode/)
- [xAI Chat Completions](https://docs.x.ai/developers/rest-api-reference/inference/chat-completions)
