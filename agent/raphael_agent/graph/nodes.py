"""LangGraph node stubs for the Phase 0 happy path."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raphael_agent.diagnosis import stub_diagnose
from raphael_agent.evidence import collect_evidence
from raphael_agent.patch import stub_propose_patch
from raphael_agent.publish import stub_publish
from raphael_agent.graph.state import RunState, append_audit, utc_now
from raphael_agent.sandbox_client import SandboxApiError, SandboxClient

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
RECORDED = FIXTURES / "recorded_sandbox_responses.json"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCENARIO = REPO_ROOT / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"


def _load_recorded() -> dict[str, Any]:
    return json.loads(RECORDED.read_text(encoding="utf-8"))


def _touch(state: RunState, node: str) -> dict[str, Any]:
    return {
        "current_node": node,
        "status": "running",
        "updated_at": utc_now(),
        "audit_events": append_audit(state, node, "enter"),
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
    diagnosis = stub_diagnose(state)
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
    if classification.get("category") == "blocked" or (
        diagnosis.get("selected_hypothesis_id") is None or conf < threshold
    ):
        reason = (
            "blocked_category"
            if classification.get("category") == "blocked"
            else "low_confidence"
        )
        now = utc_now()
        updates["status"] = "escalated"
        updates["terminal_reason"] = reason
        updates["escalation_report"] = {
            "reason_code": reason,
            "summary": "Diagnosis did not clear confidence / policy gate",
            "what_happened": diagnosis.get("notes") or "stub diagnosis gate",
            "evidence_ids": [e["evidence_id"] for e in state.get("evidence") or []],
            "hypotheses_considered": [
                {
                    "hypothesis_id": h["hypothesis_id"],
                    "statement": h["statement"],
                    "confidence": h["confidence"],
                }
                for h in diagnosis.get("hypotheses") or []
            ],
            "attempts": [{"kind": "other", "status": "blocked", "detail": reason}],
            "why_no_fix": "Automatic fix not proposed after diagnosis gate",
            "recommended_next_checks": [
                "Review evidence_ids and hypothesis ranking",
                "Confirm failure class is in the supported set",
            ],
            "sandbox_id": None,
            "result_id": None,
            "escalated_at": now,
        }
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
        now = utc_now()
        updates["status"] = "escalated"
        updates["terminal_reason"] = "reproduction_failed"
        updates["escalation_report"] = {
            "reason_code": "reproduction_failed",
            "summary": "Failure signature was not reproduced in sandbox",
            "what_happened": "Reproduce node did not observe a reproduced failure signature",
            "evidence_ids": [e["evidence_id"] for e in state.get("evidence") or []],
            "hypotheses_considered": [
                {
                    "hypothesis_id": h["hypothesis_id"],
                    "statement": h["statement"],
                    "confidence": h["confidence"],
                }
                for h in (state.get("diagnosis") or {}).get("hypotheses") or []
            ],
            "attempts": [
                {
                    "kind": "reproduce",
                    "status": "failed",
                    "detail": repro.get("message") or "not reproduced",
                }
            ],
            "why_no_fix": "Cannot propose a validated fix without reproduction",
            "recommended_next_checks": [
                "Inspect sandbox fidelity gaps",
                "Confirm workload manifests in the fixture workspace",
            ],
            "sandbox_id": state.get("sandbox_id"),
            "result_id": None,
            "escalated_at": now,
        }
        updates["audit_events"] = append_audit(
            {**state, **updates}, "patch", "escalated", "reproduction_failed"
        )
        return updates

    proposal = stub_propose_patch(state)
    patches = list(state.get("candidate_patches") or [])
    patches.append(proposal)
    attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
    attempts["patch"] = int(proposal["attempt"])
    updates["candidate_patches"] = patches
    updates["active_patch_id"] = proposal["patch_id"]
    updates["attempt_count"] = attempts
    updates["policy_decisions"] = list(state.get("policy_decisions") or []) + [
        {
            "rule": "stub_allow_config_patch",
            "decision": "allow",
            "message": "Phase 0 stub policy allow",
            "at": utc_now(),
        }
    ]
    updates["audit_events"] = append_audit(
        {**state, **updates}, "patch", "proposed", proposal["patch_id"]
    )
    return updates


def node_validate(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    updates = _touch(state, "validate")

    mode = state.get("sandbox_mode") or "skipped"
    sandbox_id = state.get("sandbox_id")
    before_key = (state.get("failure_signature") or {}).get("key")
    active = state.get("active_patch_id")
    patch = next(
        (p for p in (state.get("candidate_patches") or []) if p.get("patch_id") == active),
        None,
    )
    hint = (patch or {}).get("sandbox_deploy_hint") or {}
    fixed_path = hint.get("manifests_path") or (state.get("manifests") or {}).get(
        "fixed_path", "deploy/manifests_fixed"
    )

    if mode == "recorded_stub":
        recorded = _load_recorded()
        validation = recorded["validation"]
        finalized = recorded["finalize"]
        updates["validation_results"] = list(state.get("validation_results") or []) + [validation]
        updates["result_id"] = finalized["result_id"]
        updates["validated_fix_record"] = finalized["record"]
        updates["failure_signature"] = recorded["observe_fixed"]["signature"]
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", "recorded_stub", finalized["result_id"]
        )
        return updates

    client = SandboxClient()
    workspace = state.get("workspace_path") or str(DEFAULT_SCENARIO)
    try:
        assert sandbox_id, "sandbox_id required for live validate"
        client.deploy_revision(
            sandbox_id,
            {
                "repository_sha": state["commit_sha"],
                "workspace_path": workspace,
                "manifests": {"type": "yaml", "path": fixed_path},
                "wait_seconds": 5,
            },
        )
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
            updates["status"] = "failed_closed"
            updates["terminal_reason"] = "validation_failed_or_unavailable"
            updates["audit_events"] = append_audit(
                {**state, **updates}, "validate", "fail_closed", "validation did not pass"
            )
            if sandbox_id:
                try:
                    client.destroy_sandbox(sandbox_id, {"reason": "agent-validate-failed"})
                except Exception:  # noqa: BLE001
                    pass
            return updates

        finalized = client.finalize_result(
            sandbox_id, {"notes": "phase0 stub validated fix"}
        )
        updates["result_id"] = finalized["result_id"]
        updates["validated_fix_record"] = finalized.get("record")
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", "finalized", finalized["result_id"]
        )
        try:
            client.destroy_sandbox(sandbox_id, {"reason": "agent-phase0-complete"})
        except Exception:  # noqa: BLE001
            pass
    except (SandboxApiError, OSError, AssertionError, Exception) as exc:  # noqa: BLE001
        updates["status"] = "failed_closed"
        updates["terminal_reason"] = "sandbox_validate_failed"
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
                SandboxClient().destroy_sandbox(sandbox_id, {"reason": "agent-validate-error"})
            except Exception:  # noqa: BLE001
                pass
    return updates


def node_publish_or_escalate(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"current_node": None, "updated_at": utc_now()}
    updates = _touch(state, "publish_or_escalate")

    published = stub_publish(state)
    if not published["ok"]:
        updates["status"] = "failed_closed"
        updates["terminal_reason"] = published["error"]
        updates["errors"] = list(state.get("errors") or []) + [
            {
                "code": published["error"] or "publish_failed",
                "message": published["message"],
                "retryable": False,
                "node": "publish_or_escalate",
            }
        ]
        updates["audit_events"] = append_audit(
            {**state, **updates}, "publish_or_escalate", "fail_closed", published["message"]
        )
    else:
        updates["status"] = "success_draft_pr_ready"
        updates["terminal_reason"] = "phase0_placeholder_no_pr"
        updates["pull_request_url"] = None
        updates["audit_events"] = append_audit(
            {**state, **updates},
            "publish_or_escalate",
            "success_draft_pr_ready",
            published["message"],
        )
    updates["current_node"] = None
    return updates


# Keep normalize import available for smoke runners.
__all__ = [
    "node_ingest",
    "node_evidence",
    "node_diagnose",
    "node_reproduce",
    "node_patch",
    "node_validate",
    "node_publish_or_escalate",
]
