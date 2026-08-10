"""Route B — labeled GitHub Issues trigger configuration."""

from __future__ import annotations

import os
import re


DEFAULT_ISSUE_TRIGGER_LABEL = "raphael:fix"
_SHA_RE = re.compile(
    r"(?im)^\s*raphael-sha:\s*([0-9a-f]{7,40})\s*$"
)


def issue_trigger_label() -> str:
    return (
        os.environ.get("RAPHAEL_ISSUE_TRIGGER_LABEL", DEFAULT_ISSUE_TRIGGER_LABEL).strip()
        or DEFAULT_ISSUE_TRIGGER_LABEL
    )


def parse_raphael_sha(body: str | None) -> str | None:
    if not body:
        return None
    match = _SHA_RE.search(body)
    if not match:
        return None
    return match.group(1)


def default_commit_sha_fallback() -> str | None:
    raw = os.environ.get("RAPHAEL_DEFAULT_COMMIT_SHA", "").strip()
    return raw or None


def extract_failure_class_hint(body: str | None) -> str | None:
    """Optional ``raphael-failure-class:`` line for template-compatible Issue runs."""
    if not body:
        return None
    match = re.search(r"(?im)^\s*raphael-failure-class:\s*([a-z0-9_\-]+)\s*$", body)
    if not match:
        return None
    return match.group(1).strip()
