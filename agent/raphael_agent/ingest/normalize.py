"""Normalize fixture and GitHub webhook payloads into run seed fields (FR-004)."""

from __future__ import annotations

import os
import uuid
from typing import Any

from raphael_agent.timeutil import utc_now
from raphael_agent.ingest.fingerprint import build_fingerprint, provisional_failure_key
from raphael_agent.ingest.issue_config import (
    default_commit_sha_fallback,
    extract_failure_class_hint,
    issue_trigger_label,
    parse_raphael_sha,
)
from raphael_agent.ingest.k8s_watcher import normalize_k8s_workload


def _tenant_id(explicit: str | None = None) -> str:
    return explicit or os.environ.get("RAPHAEL_AGENT_TENANT_ID", "local-dev")


def _repo_from_github(repository: dict[str, Any]) -> dict[str, Any]:
    owner_obj = repository.get("owner") or {}
    owner = owner_obj.get("login") or owner_obj.get("name") or repository.get("owner")
    if isinstance(owner, dict):
        owner = owner.get("login") or owner.get("name")
    name = repository.get("name")
    if not owner or not name:
        raise ValueError("GitHub payload missing repository.owner/name")
    out: dict[str, Any] = {"owner": str(owner), "name": str(name)}
    clone_url = repository.get("clone_url") or repository.get("git_url")
    if clone_url:
        out["clone_url"] = str(clone_url)
    return out


def normalize_fixture_event(event: dict[str, Any]) -> dict[str, Any]:
    """Map Phase 0 fixture / manual seed into run_record seed fields."""
    repo = event.get("repository") or {}
    repository: dict[str, Any] = {
        "owner": repo["owner"],
        "name": repo["name"],
    }
    if repo.get("clone_url"):
        repository["clone_url"] = repo["clone_url"]

    resources = list(event.get("affected_resources") or [])
    workload = resources[0]["name"] if resources else None
    namespace = resources[0].get("namespace") if resources else None
    manifests = event.get("manifests")
    deployment_config_path = None
    if isinstance(manifests, dict):
        deployment_config_path = (
            manifests.get("path")
            or manifests.get("overlay")
            or manifests.get("chart")
        )

    correlation = {
        "deployment_config_path": deployment_config_path,
        "namespace": namespace,
        "workload": workload,
        "workflow_name": event.get("workflow_name"),
        "check_name": event.get("check_name"),
        "provisional_failure_key": event.get("provisional_failure_key")
        or f"fixture|{workload or 'workload'}",
    }

    seed: dict[str, Any] = {
        "run_id": event.get("run_id") or f"run-{uuid.uuid4().hex[:12]}",
        "tenant_id": _tenant_id(event.get("tenant_id")),
        "trigger": {
            "kind": event.get("trigger_kind", "fixture"),
            "event_id": event.get("event_id", event.get("run_id", "fixture")),
            "received_at": event.get("received_at") or utc_now(),
            "raw_ref": event.get("raw_ref", f"fixture:{event.get('run_id', 'unknown')}"),
        },
        "repository": repository,
        "commit_sha": event["commit_sha"],
        "target_environment": event.get("target_environment"),
        "affected_resources": resources,
        "workspace_path": event.get("workspace_path"),
        "manifests": manifests,
        "runtime_observation": dict(event.get("runtime_observation") or {}),
        "correlation": correlation,
    }
    if event.get("delivery_mode"):
        seed["delivery_mode"] = event["delivery_mode"]
    if event.get("diagnosis_only"):
        seed["diagnosis_only"] = True
    if event.get("issue_number") is not None:
        seed["issue_number"] = event["issue_number"]
    if event.get("issue_labels") is not None:
        seed["issue_labels"] = list(event["issue_labels"])
    if event.get("issue_title") is not None:
        seed["issue_title"] = event["issue_title"]
    if event.get("issue_body") is not None:
        seed["issue_body"] = event["issue_body"]
    if event.get("failure_class_hint") is not None:
        seed["failure_class_hint"] = event["failure_class_hint"]
    if event.get("fix_rules") is not None:
        seed["fix_rules"] = event["fix_rules"]
    if event.get("parent_run_id") is not None:
        seed["parent_run_id"] = event["parent_run_id"]
    if event.get("pull_request_number") is not None:
        seed["pull_request_number"] = event["pull_request_number"]
    seed["failure_fingerprint"] = build_fingerprint(seed)
    # ensure provisional key stable on seed
    seed["correlation"]["provisional_failure_key"] = provisional_failure_key(seed)
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_github_workflow_run(
    payload: dict[str, Any],
    *,
    raw_ref: str,
    received_at: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    workflow = payload.get("workflow_run") or {}
    conclusion = (workflow.get("conclusion") or "").lower()
    action = (payload.get("action") or "").lower()
    if action and action != "completed":
        raise ValueError(f"workflow_run action ignored: {action}")
    if conclusion not in {"failure", "timed_out"}:
        raise ValueError(f"workflow_run conclusion not a failure: {conclusion or 'none'}")

    repository = _repo_from_github(payload.get("repository") or {})
    head_sha = workflow.get("head_sha") or workflow.get("head_commit", {}).get("id")
    if not head_sha:
        raise ValueError("workflow_run missing head_sha")

    workflow_id = workflow.get("id")
    event_id = f"workflow_run:{workflow_id}"
    name = workflow.get("name") or workflow.get("display_title") or "workflow"
    env = (
        (workflow.get("referenced_workflows") and None)
        or payload.get("target_environment")
        or os.environ.get("RAPHAEL_DEFAULT_ENVIRONMENT")
    )

    correlation = {
        "deployment_config_path": None,
        "namespace": None,
        "workload": None,
        "workflow_name": str(name),
        "check_name": None,
        "provisional_failure_key": f"github_workflow_run|{name}|{conclusion}",
    }
    seed: dict[str, Any] = {
        "run_id": f"ghw-{workflow_id}",
        "tenant_id": _tenant_id(tenant_id),
        "trigger": {
            "kind": "github_workflow_run",
            "event_id": event_id,
            "received_at": received_at or utc_now(),
            "raw_ref": raw_ref,
        },
        "repository": repository,
        "commit_sha": str(head_sha),
        "target_environment": env,
        "affected_resources": [],
        "workspace_path": None,
        "manifests": None,
        "correlation": correlation,
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_github_check_run(
    payload: dict[str, Any],
    *,
    raw_ref: str,
    received_at: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    check = payload.get("check_run") or {}
    conclusion = (check.get("conclusion") or "").lower()
    action = (payload.get("action") or "").lower()
    if action and action not in {"completed", "rerequested"}:
        raise ValueError(f"check_run action ignored: {action}")
    if conclusion not in {"failure", "timed_out", "cancelled"}:
        raise ValueError(f"check_run conclusion not a failure: {conclusion or 'none'}")

    repository = _repo_from_github(payload.get("repository") or {})
    head_sha = check.get("head_sha")
    if not head_sha:
        raise ValueError("check_run missing head_sha")

    check_id = check.get("id")
    event_id = f"check_run:{check_id}"
    name = check.get("name") or "check"
    correlation = {
        "deployment_config_path": None,
        "namespace": None,
        "workload": None,
        "workflow_name": None,
        "check_name": str(name),
        "provisional_failure_key": f"github_check_run|{name}|{conclusion}",
    }
    seed: dict[str, Any] = {
        "run_id": f"ghc-{check_id}",
        "tenant_id": _tenant_id(tenant_id),
        "trigger": {
            "kind": "github_check_run",
            "event_id": event_id,
            "received_at": received_at or utc_now(),
            "raw_ref": raw_ref,
        },
        "repository": repository,
        "commit_sha": str(head_sha),
        "target_environment": os.environ.get("RAPHAEL_DEFAULT_ENVIRONMENT"),
        "affected_resources": [],
        "workspace_path": None,
        "manifests": None,
        "correlation": correlation,
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_github_deployment_status(
    payload: dict[str, Any],
    *,
    raw_ref: str,
    received_at: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    dep_status = payload.get("deployment_status") or {}
    state = (dep_status.get("state") or "").lower()
    if state not in {"failure", "error"}:
        raise ValueError(f"deployment_status state not a failure: {state or 'none'}")

    deployment = payload.get("deployment") or {}
    repository = _repo_from_github(payload.get("repository") or {})
    sha = deployment.get("sha") or dep_status.get("sha")
    if not sha:
        raise ValueError("deployment_status missing sha")

    status_id = dep_status.get("id") or deployment.get("id") or uuid.uuid4().hex[:10]
    env = deployment.get("environment") or dep_status.get("environment")
    correlation = {
        "deployment_config_path": None,
        "namespace": None,
        "workload": None,
        "workflow_name": None,
        "check_name": None,
        "provisional_failure_key": f"github_deployment_status|{env or 'env'}|{state}",
    }
    seed: dict[str, Any] = {
        "run_id": f"ghd-{status_id}",
        "tenant_id": _tenant_id(tenant_id),
        "trigger": {
            "kind": "github_deployment_status",
            "event_id": f"deployment_status:{status_id}",
            "received_at": received_at or utc_now(),
            "raw_ref": raw_ref,
        },
        "repository": repository,
        "commit_sha": str(sha),
        "target_environment": env,
        "affected_resources": [],
        "workspace_path": None,
        "manifests": None,
        "correlation": correlation,
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_github_issue(
    payload: dict[str, Any],
    *,
    raw_ref: str,
    received_at: str | None = None,
    tenant_id: str | None = None,
    trigger_label: str | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    """Normalize a labeled GitHub Issues webhook into a Route B run seed."""
    action = (payload.get("action") or "").lower()
    if action not in {"opened", "labeled", "reopened"}:
        raise ValueError(f"issues action ignored: {action or 'none'}")

    issue = payload.get("issue") or {}
    if issue.get("pull_request"):
        raise ValueError("issues event is a pull request; ignored")
    if issue.get("state") and str(issue.get("state")).lower() != "open":
        raise ValueError("issue is not open")

    required = trigger_label or issue_trigger_label()
    labels = []
    for entry in issue.get("labels") or []:
        if isinstance(entry, dict):
            name = entry.get("name")
        else:
            name = str(entry)
        if name:
            labels.append(str(name))

    if action == "labeled":
        labeled = payload.get("label") or {}
        labeled_name = labeled.get("name") if isinstance(labeled, dict) else None
        if labeled_name and str(labeled_name) != required and required not in labels:
            raise ValueError(f"label event is not trigger label: {labeled_name}")
        if labeled_name and str(labeled_name) == required and required not in labels:
            labels.append(required)

    if required not in labels:
        raise ValueError(f"issue missing trigger label: {required}")

    repository = _repo_from_github(payload.get("repository") or {})
    body = issue.get("body") or ""
    if not isinstance(body, str):
        body = str(body)
    # Bound body stored on the seed / run.
    body_bound = body[:8000]

    sha = commit_sha or parse_raphael_sha(body) or default_commit_sha_fallback()
    if not sha:
        # Placeholder resolved later via GitHub API when token available.
        sha = "pending0"
    if len(str(sha)) < 7:
        raise ValueError("commit sha too short")

    issue_number = issue.get("number")
    if not issue_number:
        raise ValueError("issue missing number")

    failure_hint = extract_failure_class_hint(body)
    provisional = f"github_issue|{required}|{issue_number}"
    if failure_hint:
        provisional = f"github_issue|{required}|{issue_number}|{failure_hint}"

    correlation = {
        "deployment_config_path": None,
        "namespace": None,
        "workload": None,
        "workflow_name": None,
        "check_name": None,
        "provisional_failure_key": provisional,
    }
    seed: dict[str, Any] = {
        "run_id": f"ghi-{issue_number}",
        "tenant_id": _tenant_id(tenant_id),
        "trigger": {
            "kind": "github_issue",
            "event_id": f"issues:{issue_number}:{action}",
            "received_at": received_at or utc_now(),
            "raw_ref": raw_ref,
        },
        "repository": repository,
        "commit_sha": str(sha),
        "target_environment": os.environ.get("RAPHAEL_DEFAULT_ENVIRONMENT"),
        "affected_resources": [],
        "workspace_path": None,
        "manifests": None,
        "correlation": correlation,
        "delivery_mode": "issue_snippet",
        "issue_number": int(issue_number),
        "issue_labels": labels,
        "issue_title": issue.get("title"),
        "issue_body": body_bound,
        "failure_class_hint": failure_hint,
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def normalize_failed_run_event(event: dict[str, Any]) -> dict[str, Any]:
    """Unified entry: fixture seed or already-normalized GitHub seed dict.

    GitHub paths should call the specific normalizers; this keeps the Phase 0
    ``normalize_failed_run_event → initial_run_state → run_stub_graph`` shape.
    """
    if event.get("workflow_run"):
        return normalize_github_workflow_run(
            event,
            raw_ref=event.get("raw_ref") or "inline:workflow_run",
            received_at=event.get("received_at"),
            tenant_id=event.get("tenant_id"),
        )
    if event.get("check_run"):
        return normalize_github_check_run(
            event,
            raw_ref=event.get("raw_ref") or "inline:check_run",
            received_at=event.get("received_at"),
            tenant_id=event.get("tenant_id"),
        )
    if event.get("deployment_status"):
        return normalize_github_deployment_status(
            event,
            raw_ref=event.get("raw_ref") or "inline:deployment_status",
            received_at=event.get("received_at"),
            tenant_id=event.get("tenant_id"),
        )
    if event.get("issue") and event.get("action"):
        return normalize_github_issue(
            event,
            raw_ref=event.get("raw_ref") or "inline:issues",
            received_at=event.get("received_at"),
            tenant_id=event.get("tenant_id"),
        )
    if (
        event.get("kind") in {"Deployment", "StatefulSet", "Job", "Pod", "ReplicaSet"}
        or event.get("trigger_kind") == "k8s_workload"
        or event.get("resource_kind")
        or (event.get("namespace") and event.get("workload"))
    ):
        try:
            return normalize_k8s_workload(
                event,
                raw_ref=event.get("raw_ref") or "inline:k8s_workload",
                received_at=event.get("received_at"),
                tenant_id=event.get("tenant_id"),
            )
        except ValueError:
            pass
    return normalize_fixture_event(event)
