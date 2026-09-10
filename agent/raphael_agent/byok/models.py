"""Generic data models and configuration for BYOK (Bring Your Own Key)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LLMProvider(str, Enum):
    """Supported LLM providers and gateway protocols."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    AZURE = "azure"
    CUSTOM_OPENAI = "custom_openai"


DEFAULT_MODELS: dict[LLMProvider, str] = {
    LLMProvider.OPENAI: "gpt-4o-mini",
    LLMProvider.ANTHROPIC: "claude-3-5-haiku-latest",
    LLMProvider.GEMINI: "gemini-3.6-flash",
    LLMProvider.AZURE: "gpt-4o-mini",
    LLMProvider.CUSTOM_OPENAI: "default",
}

DEFAULT_BASE_URLS: dict[LLMProvider, str] = {
    LLMProvider.OPENAI: "https://api.openai.com/v1",
    LLMProvider.ANTHROPIC: "https://api.anthropic.com/v1",
    LLMProvider.GEMINI: "https://generativelanguage.googleapis.com",
    LLMProvider.AZURE: "",
    LLMProvider.CUSTOM_OPENAI: "http://localhost:8000/v1",
}


def mask_key(key: str | None) -> str:
    """Return a masked representation of a secret key (never expose plaintext)."""
    if not key:
        return "<empty>"
    clean = str(key).strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:4]}...{clean[-4:]}"


def detect_provider(
    provider_name: str | None = None, base_url: str | None = None
) -> LLMProvider:
    """Resolve provider from explicit user configuration or base URL, defaulting to OpenAI.

    Does NOT inspect API key strings or enforce prefix heuristics so users have full control.
    """
    if provider_name:
        try:
            return LLMProvider(str(provider_name).strip().lower())
        except ValueError:
            return LLMProvider.CUSTOM_OPENAI

    if base_url:
        lowered_url = base_url.lower()
        if "anthropic" in lowered_url:
            return LLMProvider.ANTHROPIC
        if "generativelanguage.googleapis.com" in lowered_url:
            return LLMProvider.GEMINI
        if "azure" in lowered_url or "openai.azure.com" in lowered_url:
            return LLMProvider.AZURE
        if "api.openai.com" not in lowered_url:
            return LLMProvider.CUSTOM_OPENAI

    return LLMProvider.OPENAI


class AllQuotasExhaustedError(RuntimeError):
    """Raised when all candidate models for a provider/key have hit quota or rate limits."""


@dataclass
class BYOKConfig:
    """Unified, provider-agnostic configuration for model calls."""

    api_key: str
    provider: LLMProvider = LLMProvider.OPENAI
    base_url: str | None = None
    model: str | None = None  # None or "random" triggers dynamic model selection
    temperature: float = 0.0
    timeout_seconds: float = 45.0
    max_tokens: int | None = None
    available_models: list[str] = field(default_factory=list)
    exhausted_models: list[str] = field(default_factory=list)
    auto_rotate_on_quota: bool = True
    extra_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.provider, str) and not isinstance(self.provider, LLMProvider):
            try:
                self.provider = LLMProvider(self.provider.lower())
            except ValueError:
                self.provider = LLMProvider.CUSTOM_OPENAI

        # If model is unspecified or empty string, default to "random" for dynamic discovery
        if not self.model or str(self.model).strip().lower() in ("", "random", "auto"):
            self.model = "random"

        if not self.base_url:
            self.base_url = DEFAULT_BASE_URLS.get(self.provider, "https://api.openai.com/v1")
        self.base_url = self.base_url.rstrip("/")

    def __repr__(self) -> str:
        return (
            f"BYOKConfig(provider={self.provider.value}, model={self.model}, "
            f"base_url={self.base_url}, api_key={mask_key(self.api_key)})"
        )

    def __str__(self) -> str:
        return self.__repr__()

    @classmethod
    def from_env(cls) -> BYOKConfig | None:
        """Create BYOKConfig from environment variables (Level 2: Environment/Gateway mode)."""
        provider_name = os.environ.get("RAPHAEL_LLM_PROVIDER")
        custom_base_url = os.environ.get("RAPHAEL_LLM_BASE_URL")
        custom_model = os.environ.get("RAPHAEL_LLM_MODEL")

        detected = detect_provider(provider_name, custom_base_url)

        provider_env = detected.value.upper()
        key = (
            os.environ.get("RAPHAEL_LLM_API_KEY")
            or os.environ.get(f"{provider_env}_API_KEY")
            or os.environ.get(f"RAPHAEL_{provider_env}_API_KEY")
            or os.environ.get("RAPHAEL_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("LLM_API_KEY")
        )
        if not key:
            return None

        return cls(
            api_key=key.strip(),
            provider=detected,
            base_url=custom_base_url,
            model=custom_model,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BYOKConfig | None:
        """Create BYOKConfig from a dictionary (e.g., from request body or headers)."""
        key = data.get("api_key") or data.get("key")
        if not key or not str(key).strip():
            return None

        raw_provider = data.get("provider")
        base_url = data.get("base_url")
        detected = detect_provider(raw_provider, base_url)

        try:
            timeout = float(data.get("timeout_seconds") or 45.0)
        except (ValueError, TypeError):
            timeout = 45.0

        try:
            temperature = float(data.get("temperature") or 0.0)
        except (ValueError, TypeError):
            temperature = 0.0

        return cls(
            api_key=str(key).strip(),
            provider=detected,
            base_url=base_url,
            model=data.get("model"),
            temperature=temperature,
            timeout_seconds=timeout,
            extra_headers=dict(data.get("extra_headers") or {}),
        )


@dataclass
class LLMMessage:
    """Normalized chat message."""

    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class LLMRequest:
    """Generic model request envelope."""

    messages: list[LLMMessage]
    json_mode: bool = True
    temperature: float = 0.0
    max_tokens: int | None = None


@dataclass
class LLMResponse:
    """Normalized model response output."""

    content: str
    parsed_json: dict[str, Any] | None = None
    model: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Health check outcome for an API key / gateway endpoint."""

    valid: bool
    provider: str
    model: str
    available_models: list[str] = field(default_factory=list)
    selected_model: str = ""
    error: str | None = None
    latency_ms: float = 0.0
