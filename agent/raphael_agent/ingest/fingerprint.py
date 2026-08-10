"""Failure fingerprint helpers for FR-003 deduplication."""

from __future__ import annotations

from typing import Any


def provisional_failure_key(seed: dict[str, Any]) -> str:
    """Build a provisional failure key before sandbox observe (CI conclusion + job name)."""
    correlation = seed.get("correlation") or {}
    if correlation.get("provisional_failure_key"):
        return str(correlation["provisional_failure_key"])
    parts = [
        str(seed.get("trigger", {}).get("kind") or "unknown"),
        str(correlation.get("workflow_name") or correlation.get("check_name") or "job"),
        str(correlation.get("workload") or "workload"),
    ]
    return "|".join(parts)


def build_fingerprint(seed: dict[str, Any]) -> str:
    """tenant|owner/name|commit|environment|provisional_failure_key"""
    repo = seed.get("repository") or {}
    owner = repo.get("owner", "")
    name = repo.get("name", "")
    env = seed.get("target_environment") or "default"
    key = provisional_failure_key(seed)
    tenant = seed.get("tenant_id") or "local-dev"
    commit = seed.get("commit_sha") or ""
    return f"{tenant}|{owner}/{name}|{commit}|{env}|{key}"
