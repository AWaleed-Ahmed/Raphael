"""Kubernetes workload-health event ingest (FR-002).

Accepts structured workload-failure events from:
- ``POST /v1/webhooks/k8s`` (push from an in-cluster sidecar / operator)
- ``RAPHAEL_K8S_WATCH_FILE`` JSONL / JSON array for local demos

Does **not** require a live kubeconfig in unit tests. Production watchers should
forward only read-derived signals (no Secret payloads).
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from raphael_agent.timeutil import utc_now
from raphael_agent.ingest.fingerprint import build_fingerprint


def k8s_watcher_enabled() -> bool:
    return os.environ.get("RAPHAEL_K8S_WATCHER", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def normalize_k8s_workload(
    payload: dict[str, Any],
    *,
    raw_ref: str,
    received_at: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Normalize a workload-health failure into a run seed (trigger kind k8s_workload)."""
    # Accept nested {"event": {...}} or flat payload.
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload

    reason = str(event.get("reason") or event.get("type") or "").strip()
    phase = str(event.get("phase") or event.get("status") or "").strip().lower()
    # Actionable failure signals only.
    failing_phases = {"failed", "error", "crashloopbackoff", "unhealthy", "degraded"}
    failing_reasons = {
        "backofflimitexceeded",
        "unhealthy",
        "failed",
        "crashloopbackoff",
        "progressdeadlineexceeded",
        "replicafailure",
    }
    if phase and phase not in failing_phases and reason.lower() not in failing_reasons:
        # Still allow explicit force flag for demos.
        if not event.get("force") and str(event.get("severity") or "").lower() != "failure":
            raise ValueError(
                f"k8s workload event not a failure: phase={phase or 'none'} reason={reason or 'none'}"
            )

    repo = event.get("repository") or payload.get("repository") or {}
    owner = repo.get("owner")
    name = repo.get("name")
    if not owner or not name:
        # Allow mapping via env for in-cluster installs.
        owner = os.environ.get("RAPHAEL_DEFAULT_REPO_OWNER")
        name = os.environ.get("RAPHAEL_DEFAULT_REPO_NAME")
    if not owner or not name:
        raise ValueError("k8s workload event missing repository.owner/name")

    commit_sha = (
        event.get("commit_sha")
        or event.get("revision")
        or payload.get("commit_sha")
        or os.environ.get("RAPHAEL_DEFAULT_COMMIT_SHA")
    )
    if not commit_sha or len(str(commit_sha)) < 7:
        raise ValueError(
            "k8s workload event missing commit_sha/revision "
            "(set on event or RAPHAEL_DEFAULT_COMMIT_SHA)"
        )

    workload = event.get("workload") or event.get("name") or "workload"
    kind = event.get("kind") or event.get("resource_kind") or "Deployment"
    namespace = event.get("namespace") or event.get("ns") or "default"
    event_id = str(
        event.get("event_id")
        or event.get("uid")
        or f"k8s-{namespace}-{workload}-{uuid.uuid4().hex[:8]}"
    )

    correlation = {
        "deployment_config_path": event.get("deployment_config_path"),
        "namespace": str(namespace),
        "workload": str(workload),
        "workflow_name": None,
        "check_name": None,
        "provisional_failure_key": (
            f"k8s_workload|{kind}|{namespace}|{workload}|{reason or phase or 'failed'}"
        ),
    }
    seed: dict[str, Any] = {
        "run_id": f"k8s-{uuid.uuid4().hex[:12]}",
        "tenant_id": tenant_id
        or os.environ.get("RAPHAEL_AGENT_TENANT_ID", "local-dev"),
        "trigger": {
            "kind": "k8s_workload",
            "event_id": event_id,
            "received_at": received_at or utc_now(),
            "raw_ref": raw_ref,
        },
        "repository": {
            "owner": str(owner),
            "name": str(name),
            **(
                {"clone_url": repo["clone_url"]}
                if isinstance(repo, dict) and repo.get("clone_url")
                else {}
            ),
        },
        "commit_sha": str(commit_sha),
        "target_environment": event.get("environment")
        or os.environ.get("RAPHAEL_DEFAULT_ENVIRONMENT"),
        "affected_resources": [
            {
                "kind": str(kind),
                "name": str(workload),
                "namespace": str(namespace),
            }
        ],
        "workspace_path": event.get("workspace_path"),
        "manifests": event.get("manifests"),
        "runtime_observation": {
            "reason": reason or phase or "failed",
            "k8s_event_reason": reason or phase or "failed",
            **{key: event[key] for key in (
                "exit_code", "signal", "exception_type", "stack_trace",
                "span_sequence", "status_code", "http_body", "log_window",
                "invariant", "slo",
            ) if key in event},
        },
        "correlation": correlation,
        "delivery_mode": "draft_pr",
    }
    seed["failure_fingerprint"] = build_fingerprint(seed)
    return seed


def load_watch_file_events(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load events from RAPHAEL_K8S_WATCH_FILE (JSON array or JSONL)."""
    raw_path = path or os.environ.get("RAPHAEL_K8S_WATCH_FILE")
    if not raw_path:
        return []
    file_path = Path(raw_path)
    if not file_path.is_file():
        return []
    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [x for x in data if isinstance(x, dict)]
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events
