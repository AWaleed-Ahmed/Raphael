"""Bounded, redacted copies for diagnosis; never mutate patch inputs."""
from __future__ import annotations

import re
from typing import Any

import yaml

from .redaction import redact_text

MAX_ITEMS = 8
MAX_EXCERPT = 16_000
MAX_TOTAL = 64_000
_SENSITIVE = re.compile(r"secret|password|token|api[_-]?key|authorization", re.I)


def redact_value(value: Any) -> Any:
    """Redact structured observations before serializing string leaves."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SENSITIVE.search(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    return redact_text(value)[0] if isinstance(value, str) else value


def redact_manifest(text: str) -> str:
    """Preserve source comments, but remove YAML secret/env values before clipping.

    Regex-only redaction misses `name: API_SECRET` followed by `value: ...`.
    Parsing identifies these values; replacement preserves the original source
    layout (including adversarial comments) for evidence. Malformed YAML is not
    exposed as a best-effort raw excerpt.
    """
    if len(text) > 256_000:
        return "[REDACTED: manifest exceeds diagnosis input limit]"
    secrets: set[str] = set()
    visited: set[tuple[int, bool]] = set()

    def collect(value: Any, sensitive: bool = False) -> None:
        if isinstance(value, (dict, list)):
            marker = (id(value), sensitive)
            if marker in visited:
                return
            visited.add(marker)
        if isinstance(value, dict):
            secret_document = value.get("kind") == "Secret"
            secret_env = bool(_SENSITIVE.search(str(value.get("name", ""))))
            for key, item in value.items():
                collect(item, sensitive or bool(_SENSITIVE.search(str(key)))
                        or (secret_document and key in {"data", "stringData"})
                        or (secret_env and key == "value"))
        elif isinstance(value, list):
            for item in value:
                collect(item, sensitive)
        elif sensitive and value is not None:
            secrets.add(str(value))

    try:
        for document in yaml.safe_load_all(text):
            collect(document)
    except (yaml.YAMLError, RecursionError):
        return "[REDACTED: unparseable manifest]"
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            if secret not in text:
                # Encoded scalar representation is not safely splicable.
                # Omit the excerpt rather than expose its unredacted source.
                return "[REDACTED: encoded secret scalar]"
            text = text.replace(secret, "[REDACTED]")
    return redact_text(text)[0]


def bounded_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Limit text and count after redaction, including metadata fields."""
    result = []
    remaining = MAX_TOTAL
    for item in items[:MAX_ITEMS]:
        clean = redact_value(item)
        changed = clean != item
        for field in ("summary", "content_excerpt"):
            if isinstance(clean.get(field), str):
                clean[field] = clean[field][:min(MAX_EXCERPT, remaining)]
                remaining -= len(clean[field])
        for field in ("source", "provenance"):
            clean[field] = {str(k)[:128]: str(v)[:512] for k, v in (clean.get(field) or {}).items()}
        clean["evidence_id"] = str(clean.get("evidence_id", ""))[:256]
        clean["redacted"] = bool(item.get("redacted")) or changed
        result.append(clean)
        if remaining <= 0:
            break
    return result
