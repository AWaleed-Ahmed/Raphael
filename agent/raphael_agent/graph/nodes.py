"""LangGraph nodes: ingest → evidence → diagnose → reproduce → patch → validate → publish."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from raphael_agent.diagnosis import diagnose
from raphael_agent.evidence import collect_evidence
from raphael_agent.graph.state import RunState, append_audit, utc_now
from raphael_agent.patch import max_patch_attempts, propose_patch
from raphael_agent.publish import publish
from raphael_agent.sandbox_client import SandboxApiError, SandboxClient
from raphael_agent.schema_util import for_run_record_validation
from raphael_agent.store import RunStore

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
RECORDED = FIXTURES / "recorded_sandbox_responses.json"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIO = REPO_ROOT / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"

RouteAfterValidate = Literal["publish_or_escalate", "patch", "end_escalated"]


def _load_recorded() -> dict[str, Any]:
    return json.loads(RECORDED.read_text(encoding="utf-8"))


def _touch(state: RunState, node: str) -> dict[str, Any]:
    return {
        "current_node": node,
        "status": "running",
        "updated_at": utc_now(),
        "audit_events": append_audit(state, node, "enter"),
    }


def _escalation(
    state: RunState,
    *,
    reason_code: str,
    summary: str,
    what_happened: str,
    why_no_fix: str,
    attempts: list[dict[str, Any]] | None = None,
    next_checks: list[str] | None = None,
) -> dict[str, Any]:
    diagnosis = state.get("diagnosis") or {}
    return {
        "reason_code": reason_code,
        "summary": summary,
        "what_happened": what_happened,
        "evidence_ids": [e["evidence_id"] for e in state.get("evidence") or []],
        "hypotheses_considered": [
            {
                "hypothesis_id": h["hypothesis_id"],
                "statement": h["statement"],
                "confidence": h["confidence"],
            }
            for h in diagnosis.get("hypotheses") or []
        ],
        "attempts": attempts or [],
        "why_no_fix": why_no_fix,
        "recommended_next_checks": next_checks
        or [
            "Review evidence_ids and hypothesis ranking",
            "Confirm failure class is in the supported set",
        ],
        "sandbox_id": state.get("sandbox_id"),
        "result_id": state.get("result_id"),
        "escalated_at": utc_now(),
    }


def node_ingest(state: RunState) -> dict[str, Any]:
    updates = _touch(state, "ingest")
    detail = (
        f"fingerprint={state.get('failure_fingerprint')}"
        if state.get("failure_fingerprint")
        else "event accepted"
    )
    updates["audit_events"] = append_audit(
        {**state, **updates}, "ingest", "normalized", detail
    )
    return updates


def node_evidence(state: RunState) -> dict[str, Any]:
    updates = _touch(state, "evidence")
    evidence = collect_evidence(state)
    updates["evidence"] = evidence
    updates["redaction_report"] = {
        "items_redacted": sum(1 for e in evidence if e.get("redacted")),
        "notes": ["collect_evidence applies redaction adapters"],
    }
    updates["audit_events"] = append_audit(
        {**state, **updates}, "evidence", "collected", f"n={len(evidence)}"
    )
    return updates


def node_diagnose(state: RunState) -> dict[str, Any]:
    updates = _touch(state, "diagnose")
    diagnosis = diagnose(state)
    attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
    attempts["diagnosis"] = int(attempts.get("diagnosis", 0)) + 1
    updates["diagnosis"] = diagnosis
    updates["attempt_count"] = attempts
    updates["audit_events"] = append_audit(
        {**state, **updates},
        "diagnose",
        "ranked",
        f"selected={diagnosis.get('selected_hypothesis_id')} conf={diagnosis.get('confidence')}",
    )
    classification = diagnosis.get("classification") or {}
    conf = float(diagnosis.get("confidence") or 0)
    threshold = float(diagnosis.get("confidence_threshold") or 0.7)
    if classification.get("category") == "blocked":
        updates["status"] = "escalated"
        updates["terminal_reason"] = "blocked_category"
        updates["escalation_report"] = _escalation(
            {**state, **updates},
            reason_code="blocked_category",
            summary="Diagnosis classified as blocked",
            what_happened=diagnosis.get("notes") or "blocked category",
            why_no_fix="Automatic fix not proposed for blocked failure classes",
            attempts=[{"kind": "other", "status": "blocked", "detail": "blocked_category"}],
        )
    elif diagnosis.get("selected_hypothesis_id") is None or conf < threshold:
        updates["status"] = "escalated"
        updates["terminal_reason"] = "low_confidence"
        updates["escalation_report"] = _escalation(
            {**state, **updates},
            reason_code="low_confidence",
            summary="Diagnosis did not clear confidence gate",
            what_happened=diagnosis.get("notes") or "confidence below threshold",
            why_no_fix="Automatic fix not proposed after diagnosis gate",
            attempts=[{"kind": "other", "status": "blocked", "detail": "low_confidence"}],
        )
    return updates


def node_reproduce(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    updates = _touch(state, "reproduce")
    mode = state.get("sandbox_mode") or "skipped"

    if mode == "recorded_stub":
        recorded = _load_recorded()
        create = recorded["create"]
        observe = recorded["observe_broken"]
        updates["sandbox_id"] = create["sandbox_id"]
        updates["failure_signature"] = observe["signature"]
        updates["reproduction_result"] = {
            "reproduced": observe["signature"]["reproduced"],
            "matched_expected": observe.get("matched_expected"),
            "signature_key": observe["signature"]["key"],
            "artifact_ids": observe.get("artifact_ids") or [],
            "message": "recorded stub observe_failure",
        }
        updates["audit_events"] = append_audit(
            {**state, **updates}, "reproduce", "recorded_stub", create["sandbox_id"]
        )
        return updates

    if mode != "live":
        updates["status"] = "failed_closed"
        updates["terminal_reason"] = "sandbox_mode_unsupported"
        updates["errors"] = list(state.get("errors") or []) + [
            {
                "code": "sandbox_mode_unsupported",
                "message": f"Unknown sandbox_mode={mode}",
                "retryable": False,
                "node": "reproduce",
            }
        ]
        return updates

    client = SandboxClient()
    workspace = state.get("workspace_path") or str(DEFAULT_SCENARIO)
    manifests = state.get("manifests") or {"type": "yaml", "path": "deploy/manifests"}
    try:
        created = client.create_sandbox(
            {
                "run_id": state["run_id"],
                "tenant_id": state["tenant_id"],
                "repository": {
                    "owner": state["repository"]["owner"],
                    "name": state["repository"]["name"],
                },
                "commit_sha": state["commit_sha"],
                "timeout_minutes": 20,
                "secret_fixture_set": "payments-test",
            }
        )
        sandbox_id = created["sandbox_id"]
        updates["sandbox_id"] = sandbox_id
        client.deploy_revision(
            sandbox_id,
            {
                "repository_sha": state["commit_sha"],
                "workspace_path": workspace,
                "manifests": {
                    "type": manifests.get("type", "yaml"),
                    "path": manifests.get("path", "deploy/manifests"),
                },
                "wait_seconds": 5,
            },
        )
        observed = client.observe_failure(sandbox_id, {})
        updates["failure_signature"] = observed["signature"]
        updates["reproduction_result"] = {
            "reproduced": bool(observed["signature"].get("reproduced")),
            "matched_expected": observed.get("matched_expected"),
            "signature_key": observed["signature"].get("key"),
            "artifact_ids": observed.get("artifact_ids") or [],
            "message": "live observe_failure",
        }
        updates["audit_events"] = append_audit(
            {**state, **updates},
            "reproduce",
            "observed",
            observed["signature"].get("key"),
        )
    except (SandboxApiError, OSError, Exception) as exc:  # noqa: BLE001 — fail closed
        updates["status"] = "failed_closed"
        updates["terminal_reason"] = "sandbox_reproduce_failed"
        updates["errors"] = list(state.get("errors") or []) + [
            {
                "code": "sandbox_reproduce_failed",
                "message": str(exc),
                "retryable": False,
                "node": "reproduce",
            }
        ]
        updates["audit_events"] = append_audit(
            {**state, **updates}, "reproduce", "error", str(exc)
        )
    return updates


def node_patch(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    updates = _touch(state, "patch")
    repro = state.get("reproduction_result") or {}
    if not repro.get("reproduced"):
        updates["status"] = "escalated"
        updates["terminal_reason"] = "reproduction_failed"
        updates["escalation_report"] = _escalation(
            {**state, **updates},
            reason_code="reproduction_failed",
            summary="Failure signature was not reproduced in sandbox",
            what_happened="Reproduce node did not observe a reproduced failure signature",
            why_no_fix="Cannot propose a validated fix without reproduction",
            attempts=[
                {
                    "kind": "reproduce",
                    "status": "failed",
                    "detail": repro.get("message") or "not reproduced",
                }
            ],
            next_checks=[
                "Inspect sandbox fidelity gaps",
                "Confirm workload manifests in the fixture workspace",
            ],
        )
        updates["audit_events"] = append_audit(
            {**state, **updates}, "patch", "escalated", "reproduction_failed"
        )
        return updates

    attempt_count = int((state.get("attempt_count") or {}).get("patch", 0))
    if attempt_count >= max_patch_attempts():
        updates["status"] = "escalated"
        updates["terminal_reason"] = "budget_exhausted"
        updates["escalation_report"] = _escalation(
            {**state, **updates},
            reason_code="budget_exhausted",
            summary="Patch attempt budget exhausted",
            what_happened=f"Already used {attempt_count} patch attempts",
            why_no_fix="Attempt budget exhausted without a validated fix",
            attempts=[
                {
                    "kind": "patch",
                    "status": "failed",
                    "detail": "budget_exhausted",
                    "patch_id": state.get("active_patch_id"),
                }
            ],
        )
        updates.pop("validation_retryable", None)
        updates["audit_events"] = append_audit(
            {**state, **updates}, "patch", "escalated", "budget_exhausted"
        )
        return updates

    proposal = propose_patch(state)
    if proposal.get("policy_status") == "rejected":
        # Count the rejected attempt toward budget, then escalate if exhausted next loop
        patches = list(state.get("candidate_patches") or [])
        patches.append(proposal)
        attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
        attempts["patch"] = int(proposal["attempt"])
        updates["candidate_patches"] = patches
        updates["active_patch_id"] = proposal["patch_id"]
        updates["attempt_count"] = attempts
        updates["policy_decisions"] = list(state.get("policy_decisions") or []) + [
            {
                "rule": "patch_policy",
                "decision": "deny",
                "message": "; ".join(
                    v.get("message", v.get("rule", ""))
                    for v in (proposal.get("policy_violations") or [])
                ),
                "at": utc_now(),
            }
        ]
        if int(attempts["patch"]) >= max_patch_attempts():
            updates["status"] = "escalated"
            updates["terminal_reason"] = "policy_blocked"
            updates["escalation_report"] = _escalation(
                {**state, **updates},
                reason_code="policy_blocked",
                summary="Patch rejected by policy and budget exhausted",
                what_happened="Constrained patch failed allowlist/secret/privilege checks",
                why_no_fix="Policy rejected candidate patches",
                attempts=[
                    {
                        "kind": "patch",
                        "status": "blocked",
                        "detail": "policy_rejected",
                        "patch_id": proposal["patch_id"],
                    }
                ],
            )
        else:
            # Mark retryable so validate can skip and route back — actually better escalate on policy
            updates["status"] = "escalated"
            updates["terminal_reason"] = "policy_blocked"
            updates["escalation_report"] = _escalation(
                {**state, **updates},
                reason_code="policy_blocked",
                summary="Patch rejected by policy",
                what_happened="Constrained patch failed allowlist/secret/privilege checks",
                why_no_fix="Policy rejected the candidate patch",
                attempts=[
                    {
                        "kind": "patch",
                        "status": "blocked",
                        "detail": "policy_rejected",
                        "patch_id": proposal["patch_id"],
                    }
                ],
            )
        updates["audit_events"] = append_audit(
            {**state, **updates}, "patch", "policy_rejected", proposal["patch_id"]
        )
        return updates

    patches = list(state.get("candidate_patches") or [])
    patches.append(proposal)
    attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
    attempts["patch"] = int(proposal["attempt"])
    updates["candidate_patches"] = patches
    updates["active_patch_id"] = proposal["patch_id"]
    updates["attempt_count"] = attempts
    updates["validation_retryable"] = False
    updates["policy_decisions"] = list(state.get("policy_decisions") or []) + [
        {
            "rule": "patch_allowlist_and_secrets",
            "decision": "allow",
            "message": "Phase 2 patch policy allow",
            "at": utc_now(),
        }
    ]
    updates["audit_events"] = append_audit(
        {**state, **updates}, "patch", "proposed", proposal["patch_id"]
    )
    return updates


def _deploy_body_for_patch(
    state: RunState, patch: dict[str, Any] | None
) -> dict[str, Any]:
    manifests = state.get("manifests") or {}
    hint = (patch or {}).get("sandbox_deploy_hint") or {}
    path = hint.get("manifests_path") or manifests.get("path") or "deploy/manifests"
    body: dict[str, Any] = {
        "repository_sha": state["commit_sha"],
        "workspace_path": state.get("workspace_path") or str(DEFAULT_SCENARIO),
        "manifests": {
            "type": manifests.get("type", "yaml"),
            "path": path,
        },
        "wait_seconds": 5,
    }
    if hint.get("use_files_as_patch") and patch:
        files = [
            {"path": f["path"], "content": f["content"]}
            for f in (patch.get("files") or [])
            if f.get("action") != "delete" and isinstance(f.get("content"), str)
        ]
        if files:
            # Deploy from original manifests path with overlay patch files.
            body["manifests"]["path"] = manifests.get("path") or "deploy/manifests"
            body["patch"] = {"files": files}
    return body


def node_validate(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now(), "validation_retryable": False}
    updates = _touch(state, "validate")

    mode = state.get("sandbox_mode") or "skipped"
    sandbox_id = state.get("sandbox_id")
    before_key = (state.get("failure_signature") or {}).get("key")
    # Prefer the pre-fix signature key from reproduction.
    repro_key = (state.get("reproduction_result") or {}).get("signature_key")
    if repro_key:
        before_key = repro_key
    active = state.get("active_patch_id")
    patch = next(
        (p for p in (state.get("candidate_patches") or []) if p.get("patch_id") == active),
        None,
    )

    if mode == "recorded_stub":
        recorded = _load_recorded()
        validation = recorded["validation"]
        finalized = recorded["finalize"]
        updates["validation_results"] = list(state.get("validation_results") or []) + [
            validation
        ]
        updates["result_id"] = finalized["result_id"]
        updates["validated_fix_record"] = finalized["record"]
        updates["failure_signature"] = recorded["observe_fixed"]["signature"]
        updates["validation_retryable"] = False
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", "recorded_stub", finalized["result_id"]
        )
        return updates

    client = SandboxClient()
    try:
        assert sandbox_id, "sandbox_id required for live validate"
        client.deploy_revision(sandbox_id, _deploy_body_for_patch(state, patch))
        after = client.observe_failure(sandbox_id, {})
        updates["failure_signature"] = after["signature"]
        validation = client.run_validation(
            sandbox_id,
            {
                "plan": {
                    "commands": [],
                    "health_checks": [
                        {
                            "type": "rollout",
                            "resource": "deployment/payments-api",
                            "mandatory": True,
                        },
                        {"type": "signature_absent", "mandatory": True},
                    ],
                    "compare_to_signature_key": before_key,
                }
            },
        )
        updates["validation_results"] = list(state.get("validation_results") or []) + [
            validation
        ]
        if not validation.get("passed") or validation.get("fail_closed"):
            patch_attempts = int((state.get("attempt_count") or {}).get("patch", 0))
            if patch_attempts < max_patch_attempts() and not validation.get("fail_closed"):
                updates["validation_retryable"] = True
                updates["audit_events"] = append_audit(
                    {**state, **updates},
                    "validate",
                    "retry_patch",
                    f"attempt={patch_attempts}",
                )
                return updates
            if validation.get("fail_closed"):
                updates["status"] = "failed_closed"
                updates["terminal_reason"] = "validation_failed_or_unavailable"
            else:
                updates["status"] = "escalated"
                updates["terminal_reason"] = "validation_failed"
                updates["escalation_report"] = _escalation(
                    {**state, **updates},
                    reason_code="validation_failed",
                    summary="Validation failed and patch budget exhausted",
                    what_happened="Sandbox validation did not pass after patch attempts",
                    why_no_fix="No passing patch within attempt budget",
                    attempts=[
                        {
                            "kind": "validate",
                            "status": "failed",
                            "detail": "validation_failed",
                            "patch_id": active,
                        }
                    ],
                )
            updates["validation_retryable"] = False
            updates["audit_events"] = append_audit(
                {**state, **updates},
                "validate",
                "fail_closed" if updates["status"] == "failed_closed" else "escalated",
                "validation did not pass",
            )
            if sandbox_id and updates["status"] in {"failed_closed", "escalated"}:
                try:
                    client.destroy_sandbox(sandbox_id, {"reason": "agent-validate-failed"})
                except Exception:  # noqa: BLE001
                    pass
            return updates

        finalized = client.finalize_result(
            sandbox_id, {"notes": "phase2 validated fix"}
        )
        updates["result_id"] = finalized["result_id"]
        updates["validated_fix_record"] = finalized.get("record")
        updates["validation_retryable"] = False
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", "finalized", finalized["result_id"]
        )
        try:
            client.destroy_sandbox(sandbox_id, {"reason": "agent-phase2-complete"})
        except Exception:  # noqa: BLE001
            pass
    except (SandboxApiError, OSError, AssertionError, Exception) as exc:  # noqa: BLE001
        updates["status"] = "failed_closed"
        updates["terminal_reason"] = "sandbox_validate_failed"
        updates["validation_retryable"] = False
        updates["errors"] = list(state.get("errors") or []) + [
            {
                "code": "sandbox_validate_failed",
                "message": str(exc),
                "retryable": False,
                "node": "validate",
            }
        ]
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", "error", str(exc)
        )
        if sandbox_id:
            try:
                SandboxClient().destroy_sandbox(
                    sandbox_id, {"reason": "agent-validate-error"}
                )
            except Exception:  # noqa: BLE001
                pass
    return updates


def route_after_validate(state: RunState) -> RouteAfterValidate:
    if state.get("status") in {"failed_closed", "escalated"}:
        return "publish_or_escalate"
    if state.get("validation_retryable"):
        return "patch"
    if state.get("result_id"):
        return "publish_or_escalate"
    return "publish_or_escalate"


def node_publish_or_escalate(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"current_node": None, "updated_at": utc_now()}
    updates = _touch(state, "publish_or_escalate")

    published = publish(state)
    updates["publish"] = published
    if not published.get("ok"):
        updates["status"] = "failed_closed"
        updates["terminal_reason"] = published.get("error") or "publish_failed"
        updates["pull_request_url"] = None
        updates["errors"] = list(state.get("errors") or []) + [
            {
                "code": published.get("error") or "publish_failed",
                "message": published.get("message") or "publish failed",
                "retryable": False,
                "node": "publish_or_escalate",
            }
        ]
        updates["audit_events"] = append_audit(
            {**state, **updates},
            "publish_or_escalate",
            "fail_closed",
            published.get("message"),
        )
    else:
        updates["status"] = "success_draft_pr_ready"
        updates["terminal_reason"] = (
            "draft_pr_dry_run" if published.get("dry_run") else "draft_pr_opened"
        )
        updates["pull_request_url"] = published.get("pull_request_url")
        updates["pull_request_branch"] = published.get("branch")
        updates["audit_events"] = append_audit(
            {**state, **updates},
            "publish_or_escalate",
            "success_draft_pr_ready",
            published.get("message"),
        )
    updates["current_node"] = None
    updates["updated_at"] = utc_now()

    # Persist inspectable run_record when a data dir is in use.
    try:
        merged = {**state, **updates}
        RunStore().save_run(for_run_record_validation(merged))
    except Exception:  # noqa: BLE001 — persistence must not crash the graph
        pass
    return updates


__all__ = [
    "node_ingest",
    "node_evidence",
    "node_diagnose",
    "node_reproduce",
    "node_patch",
    "node_validate",
    "node_publish_or_escalate",
    "route_after_validate",
]
