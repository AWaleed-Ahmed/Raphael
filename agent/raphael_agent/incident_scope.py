"""Deployment-owned incident-search authorization, separate from model features."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

from .local_inference.artifacts import ArtifactUnavailable


@dataclass(frozen=True)
class IncidentScope:
    """Exact ownership of one deployment's authorized incident partition."""

    tenant_id: str
    company_id: str
    client_id: str

    def as_dict(self) -> dict[str, str]:
        """Return ownership fields without normalization or wildcard semantics."""
        return {
            "tenant_id": self.tenant_id,
            "company_id": self.company_id,
            "client_id": self.client_id,
        }


def configured_scope() -> IncidentScope:
    """Read explicit operator configuration; payload fields never grant scope."""
    values = [
        os.environ.get(key, "").strip()
        for key in (
            "RAPHAEL_AGENT_TENANT_ID",
            "RAPHAEL_COMPANY_ID",
            "RAPHAEL_CLIENT_ID",
        )
    ]
    if any(not value or value.lower() == "unknown" for value in values):
        raise ArtifactUnavailable("incident_scope_unverified")
    return IncidentScope(*values)


def scope_for_run(state: dict[str, Any]) -> IncidentScope:
    """Bind the authenticated run tenant to this backend's approved ownership."""
    scope = configured_scope()
    if state.get("tenant_id") != scope.tenant_id:
        raise ArtifactUnavailable("incident_scope_mismatch")
    observation = state.get("runtime_observation") or {}
    signature = state.get("failure_signature") or {}
    if not isinstance(signature, dict):
        raise ArtifactUnavailable("incident_scope_unverified")
    normalized = signature.get("normalized") or {}
    if not isinstance(normalized, dict):
        raise ArtifactUnavailable("incident_scope_unverified")
    for record in (state, observation, normalized, normalized.get("attributes") or {}):
        check_scope_hints(record, scope)
    return scope


def require_scope(scope: IncidentScope | None) -> IncidentScope:
    """Reject direct runtime calls that omit or forge the deployment scope."""
    if not isinstance(scope, IncidentScope) or scope != configured_scope():
        raise ArtifactUnavailable("incident_scope_unverified")
    return scope


def check_scope_hints(record: Any, scope: IncidentScope) -> None:
    """Payload identity can conflict with authorization but cannot establish it."""
    if not isinstance(record, dict):
        raise ArtifactUnavailable("incident_scope_unverified")
    if any(
        key in record and record[key] is not None and record[key] != value
        for key, value in scope.as_dict().items()
    ):
        raise ArtifactUnavailable("incident_scope_mismatch")


def incident_similarity_scores(state: dict[str, Any]) -> list[float]:
    """Keep legacy, forged or wrong-owner cached results out of ranker features."""
    try:
        owner = scope_for_run(state).as_dict()
    except ArtifactUnavailable:
        return []
    results = ((state.get("model_results") or {}).get("incident_similarity") or {}).get(
        "results"
    ) or []
    return [
        float(row["similarity"])
        for row in results
        if isinstance(row, dict)
        and all(row.get(key) == value for key, value in owner.items())
        and isinstance(row.get("similarity"), (float, int))
        and not isinstance(row["similarity"], bool)
        and math.isfinite(row["similarity"])
        and 0 <= row["similarity"] <= 1.000001
    ]
