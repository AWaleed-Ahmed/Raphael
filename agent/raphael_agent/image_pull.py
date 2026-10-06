"""Authoritative image-pull repair checks shared by diagnosis and patching."""
from __future__ import annotations

from typing import Any


def image_pull_repair_allowed(signature: dict[str, Any], sandbox_backend: str | None = None) -> bool:
    normalized = signature.get("normalized") or {}
    attributes = normalized.get("attributes") or {}
    source = attributes.get("evidence_source")
    return (
        signature.get("class") == "bad_image_reference"
        and attributes.get("image_pull_cause") == "not_found"
        and attributes.get("owner_verified") is True
        and attributes.get("container_type") == "regular"
        and normalized.get("resource_kind") == "Deployment"
        and all(isinstance(value, str) and value and value.lower() != "unknown" for value in (
            normalized.get("resource_name"), normalized.get("container"), attributes.get("image")
        ))
        and (source == "runtime" or (source == "mock_fixture" and sandbox_backend == "mock"))
    )


def image_pull_block_reason(run: dict[str, Any]) -> str | None:
    signature = run.get("failure_signature") or {}
    normalized = signature.get("normalized") or {}
    attributes = normalized.get("attributes") or {}
    is_pull = (
        signature.get("class") == "bad_image_reference"
        or normalized.get("reason") in {"ImagePullBackOff", "ErrImagePull"}
        or "image_pull_cause" in attributes
    )
    if not is_pull or image_pull_repair_allowed(signature, run.get("sandbox_backend")):
        return None
    cause = attributes.get("image_pull_cause")
    if cause in {"auth", "network", "rate_limited"}:
        return f"image_pull_{cause}"
    return "image_pull_evidence_unverified"
