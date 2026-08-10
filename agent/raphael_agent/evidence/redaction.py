"""Secret-like redaction for evidence excerpts (FR-013)."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    ),
    (
        "bearer_token",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*"),
    ),
    (
        "generic_api_key",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*\S+"),
    ),
    (
        "private_key_block",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
]


def redact_text(text: str) -> tuple[str, list[str]]:
    """Return redacted text + note labels for matched classes."""
    notes: list[str] = []
    out = text
    for label, pattern in _PATTERNS:
        if pattern.search(out):
            notes.append(label)
            out = pattern.sub(f"[REDACTED:{label}]", out)
    return out, notes


def redact_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    updated = dict(item)
    notes = list(updated.get("redaction_notes") or [])
    for field in ("content_excerpt", "summary"):
        value = updated.get(field)
        if isinstance(value, str) and value:
            redacted, found = redact_text(value)
            updated[field] = redacted
            for note in found:
                if note not in notes:
                    notes.append(note)
            if found:
                updated["redacted"] = True
    if notes:
        updated["redaction_notes"] = notes
    if "redacted" not in updated:
        updated["redacted"] = bool(notes)
    return updated
