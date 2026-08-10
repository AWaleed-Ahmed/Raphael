"""Ingest stubs — Phase 1 will accept real GitHub / K8s events."""

from __future__ import annotations

from typing import Any


def normalize_failed_run_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map a fixture/raw event into run_record seed fields (stub)."""
    repo = event.get("repository") or {}
    repository: dict[str, Any] = {
        "owner": repo["owner"],
        "name": repo["name"],
    }
    if repo.get("clone_url"):
        repository["clone_url"] = repo["clone_url"]
    return {
        "run_id": event["run_id"],
        "tenant_id": event.get("tenant_id", "local-dev"),
        "trigger": {
            "kind": event.get("trigger_kind", "fixture"),
            "event_id": event.get("event_id", event["run_id"]),
            "received_at": event.get("received_at"),
            "raw_ref": event.get("raw_ref", f"fixture:{event['run_id']}"),
        },
        "repository": repository,
        "commit_sha": event["commit_sha"],
        "target_environment": event.get("target_environment"),
        "affected_resources": event.get("affected_resources") or [],
        "workspace_path": event.get("workspace_path"),
        "manifests": event.get("manifests"),
    }
