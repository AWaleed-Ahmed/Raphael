"""Patch policy — allowlisted paths, secret-like strings, privilege escapes (FR-040/042)."""

from __future__ import annotations

import re
from typing import Any

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.patch.config import allowlist_prefixes

_PRIVILEGE_RE = re.compile(
    r"^\s*(privileged|hostNetwork|hostPID)\s*:\s*true\b|^\s*hostPath\s*:",
    re.I | re.M,
)


def path_allowed(path: str, prefixes: tuple[str, ...] | None = None) -> bool:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    allowed = prefixes or allowlist_prefixes()
    return any(normalized.startswith(prefix) for prefix in allowed)


def check_patch_policy(proposal: dict[str, Any]) -> list[dict[str, str]]:
    """Return policy violations (empty ⇒ allowed)."""
    violations: list[dict[str, str]] = []
    prefixes = allowlist_prefixes()
    for file_entry in proposal.get("files") or []:
        path = str(file_entry.get("path") or "")
        if not path_allowed(path, prefixes):
            violations.append(
                {
                    "rule": "path_allowlist",
                    "message": f"path not in allowlist: {path}",
                    "path": path,
                }
            )
        content = file_entry.get("content")
        if not isinstance(content, str):
            continue
        _, secret_notes = redact_text(content)
        # redact_text only flags when patterns match; treat those as rejects for patches
        if secret_notes:
            violations.append(
                {
                    "rule": "secret_like_content",
                    "message": f"secret-like tokens: {', '.join(secret_notes)}",
                    "path": path,
                }
            )
        if _PRIVILEGE_RE.search(content):
            violations.append(
                {
                    "rule": "privilege_escape",
                    "message": "patch introduces privileged/host access",
                    "path": path,
                }
            )
        lowered = content.lower()
        if "disable" in lowered and any(
            token in lowered for token in ("tls", "authentication", "readinessprobe", "livenessprobe")
        ):
            # Heuristic: weakening security/probes
            if re.search(r"(tls|authentication).{0,40}(false|disable|off)", content, re.I):
                violations.append(
                    {
                        "rule": "weaken_security_control",
                        "message": "patch appears to disable TLS/auth",
                        "path": path,
                    }
                )
    return violations


def apply_policy(proposal: dict[str, Any]) -> dict[str, Any]:
    updated = dict(proposal)
    violations = check_patch_policy(updated)
    updated["policy_violations"] = violations
    if violations:
        updated["policy_status"] = "rejected"
    else:
        updated["policy_status"] = "allowed"
    return updated
