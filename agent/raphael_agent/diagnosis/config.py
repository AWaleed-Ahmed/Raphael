"""Diagnosis configuration (env-driven)."""

from __future__ import annotations

import os


def confidence_threshold() -> float:
    raw = os.environ.get("RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD", "0.7")
    try:
        value = float(raw)
    except ValueError:
        return 0.7
    return max(0.0, min(1.0, value))


def llm_diagnosis_enabled() -> bool:
    return os.environ.get("RAPHAEL_LLM_DIAGNOSIS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def llm_api_key() -> str | None:
    return (
        os.environ.get("RAPHAEL_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or None
    )


def llm_base_url() -> str:
    return os.environ.get(
        "RAPHAEL_LLM_BASE_URL", "https://api.openai.com/v1"
    ).rstrip("/")


def llm_model() -> str:
    return os.environ.get("RAPHAEL_LLM_MODEL", "gpt-4o-mini")
