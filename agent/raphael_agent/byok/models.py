"""Private environment configuration for optional external LLM calls."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import os
from urllib.parse import urlsplit


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    TOGETHER = "together"
    MISTRAL = "mistral"
    DEEPSEEK = "deepseek"
    XAI = "xai"
    CUSTOM_OPENAI = "custom_openai"


@dataclass(frozen=True)
class ProviderSettings:
    """Provider differences; transport and callers remain shared."""

    base_url: str
    key_names: tuple[str, ...]


PROVIDERS = {
    LLMProvider.OPENAI: ProviderSettings("https://api.openai.com/v1", ("OPENAI_API_KEY",)),
    LLMProvider.GEMINI: ProviderSettings(
        "https://generativelanguage.googleapis.com/v1beta/openai",
        ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    ),
    LLMProvider.ANTHROPIC: ProviderSettings("https://api.anthropic.com/v1", ("ANTHROPIC_API_KEY",)),
    LLMProvider.GROQ: ProviderSettings("https://api.groq.com/openai/v1", ("GROQ_API_KEY",)),
    LLMProvider.OPENROUTER: ProviderSettings("https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",)),
    LLMProvider.TOGETHER: ProviderSettings("https://api.together.ai/v1", ("TOGETHER_API_KEY",)),
    LLMProvider.MISTRAL: ProviderSettings("https://api.mistral.ai/v1", ("MISTRAL_API_KEY",)),
    LLMProvider.DEEPSEEK: ProviderSettings("https://api.deepseek.com/v1", ("DEEPSEEK_API_KEY",)),
    LLMProvider.XAI: ProviderSettings("https://api.x.ai/v1", ("XAI_API_KEY",)),
}


@dataclass(frozen=True)
class BYOKConfig:
    api_key: str = field(repr=False)
    provider: LLMProvider = LLMProvider.OPENAI
    base_url: str | None = None
    model: str | None = None
    timeout_seconds: float = 45.0
    max_tokens: int = 2048

    def __post_init__(self) -> None:
        try:
            provider = LLMProvider(self.provider)
        except ValueError:
            raise ValueError("unsupported_llm_provider") from None
        object.__setattr__(self, "provider", provider)
        if not isinstance(self.api_key, str) or not self.api_key.strip() or any(c.isspace() for c in self.api_key.strip()):
            raise ValueError("invalid_llm_key")
        object.__setattr__(self, "api_key", self.api_key.strip())
        if self.model is not None and not isinstance(self.model, str):
            raise ValueError("invalid_llm_model")
        model = self.model.strip() if isinstance(self.model, str) else None
        if not model or model.lower() in {"auto", "random"}:
            model = None
        object.__setattr__(self, "model", model)
        settings = PROVIDERS.get(provider)
        base_url = self.base_url or (settings.base_url if settings else None)
        if not isinstance(base_url, str):
            raise ValueError("llm_base_url_required")
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except ValueError:
            raise ValueError("invalid_llm_base_url") from None
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or any(c.isspace() for c in base_url)
                or (parsed.scheme != "https" and not (
                    provider in {LLMProvider.OPENAI, LLMProvider.CUSTOM_OPENAI} and parsed.scheme == "http"
                    and parsed.hostname in {"localhost", "127.0.0.1", "::1"}))):
            raise ValueError("invalid_llm_base_url")
        if provider == LLMProvider.GEMINI and (parsed.hostname != "generativelanguage.googleapis.com"
                or parsed.path.rstrip("/") != "/v1beta/openai" or port not in {None, 443}):
            raise ValueError("invalid_gemini_compatible_endpoint")
        object.__setattr__(self, "base_url", base_url.rstrip("/"))
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, (int, float))
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 60):
            raise ValueError("invalid_llm_timeout")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or not 1 <= self.max_tokens <= 8192:
            raise ValueError("invalid_llm_token_limit")

    @classmethod
    def from_env(cls) -> BYOKConfig | None:
        try:
            provider = LLMProvider(os.environ.get("RAPHAEL_LLM_PROVIDER", "openai").strip().lower())
        except ValueError:
            raise ValueError("unsupported_llm_provider") from None
        settings = PROVIDERS.get(provider)
        names = (f"RAPHAEL_{provider.value.upper()}_API_KEY", *(settings.key_names if settings else ()))
        key = next((os.environ[n] for n in ("RAPHAEL_LLM_API_KEY", *names) if os.environ.get(n)), None)
        if key is None:
            return None
        model = os.environ.get("RAPHAEL_LLM_MODEL")
        try:
            timeout = float(os.environ.get("RAPHAEL_LLM_TIMEOUT_SECONDS", "45"))
            tokens = int(os.environ.get("RAPHAEL_LLM_MAX_TOKENS", "2048"))
        except ValueError:
            raise ValueError("invalid_llm_numeric_configuration") from None
        return cls(api_key=key, provider=provider, base_url=os.environ.get("RAPHAEL_LLM_BASE_URL"),
                   model=model, timeout_seconds=timeout, max_tokens=tokens)
