"""Bounded JSON calls with key-scoped discovery and quota rotation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import random
import time
from typing import Any

import httpx

from .models import BYOKConfig, LLMProvider

MAX_REQUEST_BYTES = 65_536
MAX_RESPONSE_BYTES = 1_048_576
MAX_CONTENT_BYTES = 65_536
MAX_MODEL_ATTEMPTS = 8


class BYOKError(RuntimeError):
    """Only sanitized codes are exposed to logging callers."""


class AllQuotasExhaustedError(BYOKError):
    """All attempted automatic candidates reported quota/rate limits."""


@dataclass(frozen=True)
class LLMResponse:
    parsed_json: dict[str, Any]
    model: str
    token_usage: dict[str, int]


def _request(client: httpx.Client, config: BYOKConfig, method: str, url: str,
             deadline: float, *, body: dict[str, Any] | None = None,
             headers: dict[str, str] | None = None) -> dict[str, Any]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BYOKError("provider_deadline_exceeded")
    encoded = json.dumps(body).encode("utf-8") if body is not None else None
    if encoded is not None and len(encoded) > MAX_REQUEST_BYTES:
        raise BYOKError("request_too_large")
    auth = headers or {"Authorization": f"Bearer {config.api_key}"}
    with client.stream(method, url, headers={**auth, "Content-Type": "application/json"},
                       content=encoded, timeout=min(remaining, config.timeout_seconds)) as response:
        if response.status_code == 429:
            raise BYOKError("provider_quota_or_rate_limit")
        if response.status_code != 200:
            raise BYOKError(f"provider_http_{response.status_code}")
        raw = bytearray()
        for chunk in response.iter_bytes():
            if time.monotonic() >= deadline:
                raise BYOKError("provider_deadline_exceeded")
            raw.extend(chunk)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise BYOKError("response_too_large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise BYOKError("invalid_provider_response")
    return data


def _text_model(name: str, provider: LLMProvider) -> bool:
    excluded = ("embedding", "image", "audio", "tts", "realtime", "live", "transcribe", "search", "codex")
    if any(part in name.lower() for part in excluded):
        return False
    if provider == LLMProvider.OPENAI:
        return name.startswith(("gpt-", "chatgpt-", "o1", "o3", "o4")) and "-pro" not in name
    return True


def discover_models(client: httpx.Client, config: BYOKConfig, deadline: float) -> list[str]:
    """One short catalog request, scoped to the selected key; no persistent cache."""
    if config.provider == LLMProvider.GEMINI:
        data = _request(client, config, "GET", "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                        min(deadline, time.monotonic() + 10), headers={"x-goog-api-key": config.api_key})
        entries = data.get("models")
        candidates = [item.get("name", "").removeprefix("models/") for item in entries
                      if isinstance(item, dict) and "generateContent" in (item.get("supportedGenerationMethods") or [])] if isinstance(entries, list) else []
    else:
        data = _request(client, config, "GET", f"{config.base_url}/models", min(deadline, time.monotonic() + 10))
        entries = data.get("data")
        candidates = [item.get("id") for item in entries if isinstance(item, dict)] if isinstance(entries, list) else []
    models = sorted({name for name in candidates if isinstance(name, str) and name and _text_model(name, config.provider)})
    if not models:
        raise BYOKError("no_compatible_models_available")
    random.SystemRandom().shuffle(models)
    return models


def complete_json(config: BYOKConfig, *, system: str, payload: dict[str, Any]) -> LLMResponse:
    # Reject large inputs before discovery as well as before completion.
    if len(json.dumps(payload).encode("utf-8")) + len(system.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise BYOKError("request_too_large")
    deadline = time.monotonic() + config.timeout_seconds
    try:
        with httpx.Client(timeout=config.timeout_seconds, follow_redirects=False) as client:
            models = [config.model] if config.model else discover_models(client, config, deadline)
            for model in models[:MAX_MODEL_ATTEMPTS]:
                body = {
                    "model": model,
                    ("max_completion_tokens" if config.provider == LLMProvider.OPENAI else "max_tokens"): config.max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": json.dumps(payload)}],
                }
                # Reasoning models can reject temperature; omit rather than alter model identity.
                try:
                    data = _request(client, config, "POST", f"{config.base_url}/chat/completions", deadline, body=body)
                except BYOKError as exc:
                    if not config.model and str(exc) == "provider_quota_or_rate_limit":
                        continue
                    raise
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
                    raise BYOKError("invalid_content")
                if config.api_key in content:
                    raise BYOKError("credential_in_output")
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise BYOKError("json_object_required")
                usage = data.get("usage") or {}
                normalized_usage = {
                    name: usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")
                    if isinstance(usage, dict) and isinstance(usage.get(name), int)
                    and not isinstance(usage[name], bool) and usage[name] >= 0
                }
                return LLMResponse(parsed, model, normalized_usage)
            raise AllQuotasExhaustedError("automatic_model_quota_attempts_exhausted")
    except BYOKError:
        raise
    except httpx.TimeoutException:
        raise BYOKError("provider_timeout") from None
    except httpx.HTTPError:
        raise BYOKError("provider_transport_error") from None
    except (ValueError, KeyError, IndexError, TypeError):
        raise BYOKError("invalid_provider_response") from None
