"""LangGraph run state helpers matching contracts/agent/run_record.json."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunState(TypedDict, total=False):
    """Inspectable graph state — fields mirror run_record contract."""

    run_id: str
    tenant_id: str
    audit_id: str
    status: str
    current_node: str | None
    created_at: str
    updated_at: str
    trigger: dict[str, Any]
    repository: dict[str, Any]
    commit_sha: str
    target_environment: str | None
    affected_resources: list[dict[str, Any]]
    workspace_path: str | None
    manifests: dict[str, Any] | None
    evidence: list[dict[str, Any]]
    redaction_report: dict[str, Any] | None
    failure_signature: dict[str, Any]
    diagnosis: dict[str, Any]
    sandbox_id: str | None
    sandbox_mode: str
    reproduction_result: dict[str, Any] | None
    candidate_patches: list[dict[str, Any]]
    active_patch_id: str | None
    validation_results: list[dict[str, Any]]
    result_id: str | None
    validated_fix_record: dict[str, Any]
    policy_decisions: list[dict[str, Any]]
    attempt_count: dict[str, int]
    token_and_cost_usage: dict[str, Any] | None
    escalation_report: dict[str, Any]
    pull_request_url: str | None
    terminal_reason: str | None
    errors: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]


def append_audit(state: RunState, node: str, event: str, detail: str | None = None) -> list[dict[str, Any]]:
    events = list(state.get("audit_events") or [])
    entry: dict[str, Any] = {"at": utc_now(), "node": node, "event": event}
    if detail:
        entry["detail"] = detail
    events.append(entry)
    return events


def initial_run_state(seed: dict[str, Any], *, sandbox_mode: str = "skipped") -> RunState:
    now = utc_now()
    run_id = seed["run_id"]
    trigger = dict(seed["trigger"])
    if not trigger.get("received_at"):
        trigger["received_at"] = now
    return RunState(
        run_id=run_id,
        tenant_id=seed["tenant_id"],
        audit_id=seed.get("audit_id", run_id),
        status="pending",
        current_node=None,
        created_at=now,
        updated_at=now,
        trigger=trigger,
        repository=seed["repository"],
        commit_sha=seed["commit_sha"],
        target_environment=seed.get("target_environment"),
        affected_resources=list(seed.get("affected_resources") or []),
        workspace_path=seed.get("workspace_path"),
        manifests=seed.get("manifests"),
        evidence=[],
        redaction_report=None,
        sandbox_id=None,
        sandbox_mode=sandbox_mode,
        reproduction_result=None,
        candidate_patches=[],
        active_patch_id=None,
        validation_results=[],
        result_id=None,
        policy_decisions=[],
        attempt_count={"diagnosis": 0, "patch": 0},
        token_and_cost_usage={"model_tokens": 0, "estimated_cost_usd": 0.0},
        pull_request_url=None,
        terminal_reason=None,
        errors=[],
        audit_events=[],
    )
