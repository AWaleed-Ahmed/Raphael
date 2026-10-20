"""Resolve image replacements from explicitly verified healthy baselines."""

from __future__ import annotations

from typing import Any
import re


def image_repository(image: str) -> str:
    reference = image.split("@", 1)[0]
    last_component = reference.rsplit("/", 1)[-1]
    if ":" in last_component:
        reference = reference[: -(len(last_component) - last_component.rfind(":"))]
    return reference


def resolve_approved_image_replacement(
    signature: dict[str, Any],
    baselines: list[dict[str, Any]],
    *,
    company_id: str,
    client_id: str,
    repository: str,
    service_name: str,
    environment: str,
    sandbox_backend: str | None = None,
) -> dict[str, Any] | None:
    """Return an exact container image from one verified last-known-good release."""
    from raphael_agent.image_pull import image_pull_repair_allowed
    if not image_pull_repair_allowed(signature, sandbox_backend):
        return None
    normalized = signature.get("normalized")
    if not isinstance(normalized, dict):
        return None
    attributes = normalized.get("attributes")
    if not isinstance(attributes, dict):
        return None
    resource_name = normalized.get("resource_name")
    container_name = normalized.get("container")
    failed_image = attributes.get("image")
    if (
        signature.get("class") != "bad_image_reference"
        or not all(isinstance(value, str) and value for value in (
            resource_name, container_name, failed_image, repository, service_name, environment,
            company_id, client_id,
        ))
        or any(value.strip().lower() == "unknown" for value in (
            resource_name, container_name, failed_image, repository, service_name, environment,
            company_id, client_id,
        ))
    ):
        return None
    if normalized.get("resource_kind") != "Deployment":
        return None

    candidates = []
    for baseline in baselines:
        if not isinstance(baseline, dict):
            continue
        identity = baseline.get("runtime_identity")
        if not isinstance(identity, dict):
            continue
        images = identity.get("container_images") or {}
        image = images.get(container_name) if isinstance(images, dict) else None
        if isinstance(image, dict):
            image = image.get("image")
        if (
            baseline.get("verified_healthy") is not True
            or baseline.get("company_id") != company_id
            or baseline.get("client_id") != client_id
            or baseline.get("is_last_known_good") is not True
            or baseline.get("repository") != repository
            or baseline.get("service_name") != service_name
            or baseline.get("environment") != environment
            or identity.get("resource_kind") != "Deployment"
            or identity.get("resource_name") != resource_name
            or not isinstance(image, str)
            or not image
            or image == failed_image
            or any(identity.get(field) != normalized.get(field)
                   for field in ("namespace", "cluster")
                   if identity.get(field) is not None or normalized.get(field) is not None)
            or image_repository(image) != image_repository(failed_image)
            or not isinstance(baseline.get("healthy_trace_id"), str)
            or not baseline.get("healthy_trace_id", "").strip()
            or any(value is not None and (not isinstance(value, str) or not value.strip())
                   for field in ("namespace", "cluster")
                   for value in (identity.get(field), normalized.get(field)))
            or not isinstance(baseline.get("source_commit_sha"), str)
            or re.fullmatch(r"[0-9a-fA-F]{40}", baseline["source_commit_sha"]) is None
            or (baseline.get("git_sha") is not None and baseline.get("git_sha") != "unknown"
                and baseline.get("git_sha") != baseline.get("source_commit_sha"))
        ):
            continue
        candidates.append({
            "image": image,
            "resource_name": resource_name,
            "container_name": container_name,
            "source": {
                "kind": "verified_healthy_trace",
                "company_id": company_id,
                "client_id": client_id,
                "namespace": identity.get("namespace"),
                "cluster": identity.get("cluster"),
                "healthy_trace_id": baseline["healthy_trace_id"],
                "source_commit_sha": baseline["source_commit_sha"],
                "repository": repository,
                "service_name": service_name,
                "environment": environment,
            },
        })

    images = {(candidate["image"], candidate["source"]["source_commit_sha"]) for candidate in candidates}
    return candidates[0] if len(images) == 1 and candidates else None
