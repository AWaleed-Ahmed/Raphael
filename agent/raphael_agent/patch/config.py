"""Patch generation configuration."""

from __future__ import annotations

import os


def max_patch_attempts() -> int:
    raw = os.environ.get("RAPHAEL_MAX_PATCH_ATTEMPTS", "3")
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(10, value))


# Default allowlisted path prefixes (repo-relative, posix).
DEFAULT_ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "deploy/",
    "k8s/",
    "kubernetes/",
    "manifests/",
    "charts/",
    "helm/",
    "overlays/",
    ".github/workflows/",
)


def allowlist_prefixes() -> tuple[str, ...]:
    raw = os.environ.get("RAPHAEL_PATCH_ALLOWLIST")
    if not raw:
        return DEFAULT_ALLOWLIST_PREFIXES
    parts = tuple(p.strip().replace("\\", "/").rstrip("/") + "/" for p in raw.split(",") if p.strip())
    return parts or DEFAULT_ALLOWLIST_PREFIXES
