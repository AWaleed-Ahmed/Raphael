"""LangGraph run state helpers matching contracts/agent/run_record.json."""

from __future__ import annotations

from typing import Any, TypedDict

from raphael_agent.budgets import build_budget_snapshot
from raphael_agent.timeutil import utc_now


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
    pull_request_branch: str | None
    publish: dict[str, Any]
    budget_snapshot: dict[str, Any]
    terminal_reason: str | None
    errors: list[dict[str, Any]]
    audit_events: list[dict[str, Any]]
    failure_fingerprint: str
    correlation: dict[str, Any]
    delivery_mode: str
    issue_number: int
    issue_labels: list[str]
    issue_title: str | None
    issue_body: str | None
    issue_comment_url: str | None
    failure_class_hint: str | None
    fix_rules: dict[str, Any]
    # Ephemeral graph routing flag (stripped before run_record schema validation)
    validation_retryable: bool


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
    trigger_kind = trigger.get("kind")
    delivery = seed.get("delivery_mode")
    if not delivery:
        delivery = "issue_snippet" if trigger_kind == "github_issue" else "draft_pr"
    state = RunState(
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
        failure_fingerprint=seed.get("failure_fingerprint"),
        correlation=seed.get("correlation"),
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
        budget_snapshot=build_budget_snapshot(),
        pull_request_url=None,
        terminal_reason=None,
        errors=[],
        audit_events=[],
        delivery_mode=delivery,
    )
    if seed.get("issue_number") is not None:
        state["issue_number"] = seed["issue_number"]
    if seed.get("issue_labels") is not None:
        state["issue_labels"] = list(seed["issue_labels"])
    if seed.get("issue_title") is not None:
        state["issue_title"] = seed["issue_title"]
    if seed.get("issue_body") is not None:
        state["issue_body"] = seed["issue_body"]
    if seed.get("failure_class_hint") is not None:
        state["failure_class_hint"] = seed["failure_class_hint"]
    if seed.get("fix_rules") is not None:
        state["fix_rules"] = seed["fix_rules"]
    if seed.get("parent_run_id") is not None:
        state["parent_run_id"] = seed["parent_run_id"]
    if seed.get("pull_request_number") is not None:
        state["pull_request_number"] = seed["pull_request_number"]
    return state
