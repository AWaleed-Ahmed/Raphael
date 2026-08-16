"""LangGraph nodes: ingest → evidence → diagnose → reproduce → patch → validate → publish."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from raphael_agent.budgets import check_budgets
from raphael_agent.diagnosis import diagnose
from raphael_agent.evidence import collect_evidence
from raphael_agent.graph.state import RunState, append_audit, utc_now
from raphael_agent.patch import max_patch_attempts, propose_patch
from raphael_agent.publish import publish
from raphael_agent.rules import load_or_derive_fix_rules
from raphael_agent.localization import (
    CandidateScorer,
    SupabaseCatalogError,
    SupabaseHealthyCatalogStore,
    compare_trace_to_healthy,
    extract_kubernetes_manifest_anchors,
    extract_route_to_handler_anchor,
    extract_stack_trace_anchors,
    extract_trace_divergence_anchor,
)
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


def _budget_halt_updates(state: RunState, node: str) -> dict[str, Any] | None:
    """If a budget is exhausted, return state updates that stop the run (no publish)."""
    halt = check_budgets(state, node=node)
    if halt is None:
        return None
    terminal = halt["terminal"]
    reason = halt["reason_code"]
    updates: dict[str, Any] = {
        "current_node": node,
        "status": terminal,
        "terminal_reason": reason,
        "updated_at": utc_now(),
        "escalation_report": _escalation(
            state,
            reason_code=reason,
            summary=f"Budget exhausted ({halt['kind']})",
            what_happened=halt["message"],
            why_no_fix="Attempt/time/cost budget exhausted — refuse speculative publish",
            attempts=[{"kind": "other", "status": "failed", "detail": halt["kind"]}],
            next_checks=[
                "Raise RAPHAEL_MAX_WALL_SECONDS / patch / diagnosis caps only if safe",
                "Inspect audit_events for the node that hit the budget",
            ],
        ),
        "errors": list(state.get("errors") or []) + [
            {
                "code": reason,
                "message": halt["message"],
                "retryable": False,
                "node": node,
            }
        ],
        "audit_events": append_audit(state, node, "budget_exhausted", halt["message"]),
    }
    return updates


def node_ingest(state: RunState) -> dict[str, Any]:
    halt = _budget_halt_updates(state, "ingest")
    if halt:
        return halt
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
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    halt = _budget_halt_updates(state, "evidence")
    if halt:
        return halt
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
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    halt = _budget_halt_updates(state, "diagnose")
    if halt:
        return halt
    updates = _touch(state, "diagnose")
    diagnosis = diagnose(state)
    attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
    attempts["diagnosis"] = int(attempts.get("diagnosis", 0)) + 1
    updates["diagnosis"] = diagnosis
    updates["attempt_count"] = attempts
    # Re-check after increment (diagnosis attempt budget)
    post = check_budgets({**state, **updates}, node="diagnose")
    if post is not None:
        updates["status"] = post["terminal"]
        updates["terminal_reason"] = post["reason_code"]
        updates["escalation_report"] = _escalation(
            {**state, **updates},
            reason_code=post["reason_code"],
            summary=f"Budget exhausted ({post['kind']})",
            what_happened=post["message"],
            why_no_fix="Diagnosis attempt budget exhausted — refuse speculative publish",
            attempts=[{"kind": "other", "status": "failed", "detail": post["kind"]}],
        )
        updates["audit_events"] = append_audit(
            {**state, **updates}, "diagnose", "budget_exhausted", post["message"]
        )
        return updates
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


def _is_issue_route(state: RunState) -> bool:
    return (state.get("trigger") or {}).get("kind") == "github_issue" or state.get(
        "delivery_mode"
    ) == "issue_snippet"


def _ensure_fix_rules(state: RunState, updates: dict[str, Any]) -> dict[str, Any]:
    if state.get("fix_rules") or updates.get("fix_rules"):
        return updates
    workspace = state.get("workspace_path") or updates.get("workspace_path")
    rules = load_or_derive_fix_rules(workspace)
    updates["fix_rules"] = rules
    updates["audit_events"] = append_audit(
        {**state, **updates},
        updates.get("current_node") or "reproduce",
        "fix_rules",
        f"source={rules.get('source')}",
    )
    return updates


def _runtime_observation_from_signature(
    state: RunState, signature: dict[str, Any]
) -> dict[str, Any]:
    """Project provider-neutral sandbox fields into localization input.

    Sandbox signatures intentionally stay small and contract-stable. Any richer
    stack/span/source fields emitted by an adapter live under normalized.attributes;
    this projection lets the localization node consume them without depending on
    a specific APM provider or sandbox implementation.
    """
    observation = dict(state.get("runtime_observation") or {})
    normalized = signature.get("normalized") if isinstance(signature.get("normalized"), dict) else {}
    attributes = normalized.get("attributes") if isinstance(normalized.get("attributes"), dict) else {}
    for key in (
        "stack_trace", "exception.stacktrace", "span_sequence", "spans",
        "stack_fingerprint", "source_file", "source_line", "source_symbol",
        "route", "http_route", "service_name", "environment", "operation",
        "changed_diff_hunks",
    ):
        if key in attributes and key not in observation:
            observation[key] = attributes[key]
    if signature.get("class") and "failure_class" not in observation:
        observation["failure_class"] = signature["class"]
    if signature.get("key") and "normalized_stack_trace" not in observation:
        observation["normalized_stack_trace"] = signature["key"]
    if normalized:
        for key in ("reason", "message", "resource_kind", "resource_name", "container"):
            if key in normalized and key not in observation:
                observation[key] = normalized[key]
    return observation


def node_reproduce(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    halt = _budget_halt_updates(state, "reproduce")
    if halt:
        return halt
    updates = _touch(state, "reproduce")
    updates = _ensure_fix_rules(state, updates)
    mode = state.get("sandbox_mode") or "skipped"

    if mode == "recorded_stub":
        recorded = _load_recorded()
        create = recorded["create"]
        observe = recorded["observe_broken"]
        updates["sandbox_id"] = create["sandbox_id"]
        updates["failure_signature"] = observe["signature"]
        updates["runtime_observation"] = _runtime_observation_from_signature(
            state, observe["signature"]
        )
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

    if mode == "skipped" and _is_issue_route(state):
        # Issue path without live sandbox: still allow rules+model patch → snippet.
        updates["reproduction_result"] = {
            "reproduced": True,
            "matched_expected": None,
            "signature_key": "issue_route_skipped_sandbox",
            "artifact_ids": [],
            "message": "issue route: sandbox skipped; clone/rules only",
        }
        updates["audit_events"] = append_audit(
            {**state, **updates}, "reproduce", "issue_skipped_sandbox", "ok"
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
        updates["runtime_observation"] = _runtime_observation_from_signature(
            state, observed["signature"]
        )
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


def _localization_observation(state: RunState) -> dict[str, Any]:
    # Keep caller/APM fields, then fill missing provider-neutral fields from the
    # sandbox signature. This matters when a caller supplied a partial runtime
    # observation: signature and trace comparisons should still be complete.
    observation = dict(state.get("runtime_observation") or {})
    signature = state.get("failure_signature") or {}
    normalized = signature.get("normalized") if isinstance(signature.get("normalized"), dict) else {}
    if signature.get("stack_trace"):
        observation.setdefault("stack_trace", signature["stack_trace"])
    if signature.get("span_sequence"):
        observation.setdefault("span_sequence", signature["span_sequence"])
    if signature.get("stack_fingerprint"):
        observation.setdefault("stack_fingerprint", signature["stack_fingerprint"])
    if normalized:
        for key, value in normalized.items():
            observation.setdefault(key, value)
    if signature.get("key"):
        observation.setdefault("normalized_stack_trace", signature["key"])
    return observation


def node_localize(state: RunState) -> dict[str, Any]:
    """Resolve healthy baselines and rank runtime/source candidates before patching.

    The node is deliberately fail-open for legacy runs: if Supabase scope or
    credentials are absent, it records a skipped localization result and leaves
    the existing diagnosis/template path intact.
    """
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    halt = _budget_halt_updates(state, "localize")
    if halt:
        return halt
    updates = _touch(state, "localize")
    updates["healthy_trace_comparisons"] = []
    updates["fault_candidates"] = []

    try:
        store = SupabaseHealthyCatalogStore()
    except SupabaseCatalogError as exc:
        updates["localization_result"] = {
            "status": "skipped",
            "reason": "supabase_catalog_unavailable",
            "message": str(exc),
        }
        updates["audit_events"] = append_audit(
            {**state, **updates}, "localize", "skipped", "supabase_catalog_unavailable"
        )
        return updates

    client_id = str(state.get("client_id") or os.environ.get("RAPHAEL_CLIENT_ID") or "").strip()
    company_id = str(state.get("company_id") or os.environ.get("RAPHAEL_COMPANY_ID") or "").strip()
    client_name = state.get("client_name")
    if not client_id:
        updates["localization_result"] = {
            "status": "skipped",
            "reason": "client_scope_missing",
        }
        updates["audit_events"] = append_audit(
            {**state, **updates}, "localize", "skipped", "client_scope_missing"
        )
        return updates

    try:
        client = store.get_client(client_id)
        if not client:
            raise SupabaseCatalogError(f"client not found: {client_id}")
        resolved_company_id = str(client["company_id"])
        if company_id and company_id != resolved_company_id:
            raise SupabaseCatalogError("company_id does not match the client registry")
        company_id = resolved_company_id
        client_name = client.get("client_name") or client_name

        observation = _localization_observation(state)
        correlation = state.get("correlation") or {}
        service_name = str(
            observation.get("service_name")
            or correlation.get("workload")
            or (state.get("repository") or {}).get("name")
            or "unknown"
        )
        environment = str(
            observation.get("environment")
            or state.get("target_environment")
            or os.environ.get("RAPHAEL_DEFAULT_ENVIRONMENT")
            or "unknown"
        )
        operation = str(
            observation.get("operation")
            or correlation.get("operation")
            or correlation.get("check_name")
            or "unknown"
        )
        query_operation = None if operation == "unknown" else operation
        baselines = store.list_healthy_traces(
            company_id=company_id,
            client_id=client_id,
            service_name=service_name,
            environment=environment,
            operation=query_operation,
        )

        unhealthy = dict(observation)
        unhealthy.setdefault("operation", operation)
        if state.get("failure_signature", {}).get("key"):
            unhealthy.setdefault(
                "normalized_stack_trace", state["failure_signature"]["key"]
            )
        # Promote the deepest application frame into the comparison payload so
        # healthy baselines can confirm whether the failing source anchor is
        # the same one (even when the telemetry adapter only supplied a raw
        # stack string).
        stack_trace = observation.get("stack_trace") or observation.get("exception.stacktrace")
        stack_anchors = (
            extract_stack_trace_anchors(stack_trace, "ev-localize-stack")
            if isinstance(stack_trace, str)
            else []
        )
        if stack_anchors:
            top_stack = stack_anchors[0]
            unhealthy.setdefault("source_file", top_stack.file_path)
            unhealthy.setdefault("source_line", top_stack.line_number)
            unhealthy.setdefault("source_symbol", top_stack.symbol_name)
        comparisons = []
        for baseline in baselines:
            scoped_unhealthy = {
                **unhealthy,
                "company_id": company_id,
                "client_id": client_id,
                "service_name": service_name,
                "environment": environment,
                "operation": operation,
            }
            # Compare against the already scoped baseline rows. Calling the
            # adapter query helper inside this loop would re-fetch every
            # baseline once per baseline and duplicate comparison records.
            comparisons.append(compare_trace_to_healthy(scoped_unhealthy, baseline).to_dict())
        updates["company_id"] = company_id
        updates["client_id"] = client_id
        if client_name:
            updates["client_name"] = str(client_name)
        updates["healthy_trace_comparisons"] = comparisons

        anchors = list(stack_anchors)
        spans = observation.get("span_sequence") or observation.get("spans") or []
        if isinstance(spans, list) and spans and baselines:
            golden = baselines[0].get("span_sequence") or []
            trace_anchor = extract_trace_divergence_anchor(
                spans, [str(item) for item in golden], "ev-localize-trace"
            )
            if trace_anchor:
                anchors.append(trace_anchor)
        route = observation.get("route") or observation.get("http_route")
        if isinstance(route, str) and baselines:
            route_map = baselines[0].get("route_handler_map") or baselines[0].get("route_handler_maps") or {}
            if isinstance(route_map, dict):
                route_anchor = extract_route_to_handler_anchor(route, route_map, "ev-localize-route")
                if route_anchor:
                    anchors.append(route_anchor)
        normalized = (state.get("failure_signature") or {}).get("normalized") or {}
        if isinstance(normalized, dict) and normalized.get("reason"):
            anchors.extend(
                extract_kubernetes_manifest_anchors(
                    {
                        "reason": normalized.get("reason"),
                        "manifest_path": (state.get("manifests") or {}).get("path"),
                    },
                    "ev-localize-k8s",
                )
            )

        repository = state.get("repository") or {}
        changed_hunks = list(state.get("changed_diff_hunks") or observation.get("changed_diff_hunks") or [])
        failure_class = str(
            ((state.get("diagnosis") or {}).get("classification") or {}).get("failure_class")
            or (state.get("failure_signature") or {}).get("class")
            or state.get("failure_class_hint")
            or "generic_failure"
        )
        candidates = []
        if anchors or changed_hunks:
            candidates = CandidateScorer().generate_and_rank_candidates(
                repository=f"{repository.get('owner', 'unknown')}/{repository.get('name', 'unknown')}",
                git_sha=str(state.get("commit_sha") or "unknown"),
                anchors=anchors,
                changed_diff_hunks=changed_hunks,
                failure_class=failure_class,
                first_divergent_anchor=anchors[0] if anchors else None,
                workspace_path=state.get("workspace_path"),
            )
        updates["fault_candidates"] = [candidate.to_dict() for candidate in candidates]
        updates["localization_result"] = {
            "status": "completed",
            "company_id": company_id,
            "client_id": client_id,
            "service_name": service_name,
            "environment": environment,
            "operation": operation,
            "baseline_count": len(baselines),
            "comparison_count": len(comparisons),
            "candidate_count": len(candidates),
        }
        updates["audit_events"] = append_audit(
            {**state, **updates},
            "localize",
            "completed",
            f"baselines={len(baselines)} comparisons={len(comparisons)} candidates={len(candidates)}",
        )
    except Exception as exc:  # noqa: BLE001 — localization must not bypass existing safety gates
        updates["localization_result"] = {
            "status": "error",
            "reason": "localization_failed",
            "message": str(exc),
        }
        updates["audit_events"] = append_audit(
            {**state, **updates}, "localize", "error", str(exc)
        )
    return updates


def node_patch(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        return {"updated_at": utc_now()}
    halt = _budget_halt_updates(state, "patch")
    if halt:
        return halt
    updates = _touch(state, "patch")
    updates = _ensure_fix_rules(state, updates)
    merged_for_patch = {**state, **updates}
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

    proposal = propose_patch(merged_for_patch)
    if proposal.get("policy_status") == "rejected":
        # Count the rejected attempt toward budget, then escalate if exhausted next loop
        patches = list(state.get("candidate_patches") or [])
        patches.append(proposal)
        attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
        attempts["patch"] = int(proposal["attempt"])
        updates["candidate_patches"] = patches
        updates["active_patch_id"] = proposal["patch_id"]
        updates["attempt_count"] = attempts
        reason = "model_required" if any(
            v.get("rule") == "model_required"
            for v in (proposal.get("policy_violations") or [])
            if isinstance(v, dict)
        ) else "policy_blocked"
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
        updates["status"] = "escalated"
        updates["terminal_reason"] = reason
        updates["escalation_report"] = _escalation(
            {**state, **updates},
            reason_code=reason,
            summary="Patch rejected by policy"
            if reason == "policy_blocked"
            else "Issue fix requires model or known failure class",
            what_happened="Constrained patch failed allowlist/secret/privilege checks"
            if reason == "policy_blocked"
            else "No LLM patch and no template for issue route",
            why_no_fix="Policy rejected the candidate patch"
            if reason == "policy_blocked"
            else "Enable RAPHAEL_LLM_DIAGNOSIS + RAPHAEL_LLM_PATCH or set raphael-failure-class",
            attempts=[
                {
                    "kind": "patch",
                    "status": "blocked",
                    "detail": reason,
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
            "message": "Phase 2/6 patch policy allow",
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
    halt = _budget_halt_updates(state, "validate")
    if halt:
        halt["validation_retryable"] = False
        return halt
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

    # Make the localization-to-sandbox handoff explicit and inspectable. The
    # sandbox remains contract-compatible (it accepts only patch files), while
    # this audit event tells operators whether the selected patch actually
    # touches one of the ranked runtime candidates.
    localized_candidates = list(state.get("fault_candidates") or [])
    if localized_candidates:
        patch_paths = {
            str(item.get("path") or "").replace("\\", "/").lstrip("./")
            for item in (patch or {}).get("files") or []
        }
        candidate_paths = {
            str(item.get("path") or "").replace("\\", "/").lstrip("./")
            for item in localized_candidates
            if item.get("path")
        }
        matched_paths = sorted(patch_paths & candidate_paths)
        top = localized_candidates[0]
        event = "localized_candidate_patch_match" if matched_paths else "localized_candidate_patch_mismatch"
        detail = (
            f"top={top.get('path')}:{top.get('line')} patch_paths={len(patch_paths)} "
            f"matched={','.join(matched_paths) if matched_paths else 'none'}"
        )
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", event, detail
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

    if mode == "skipped" and _is_issue_route(state):
        # Local/CI issue path without live sandbox: mint a local result_id for snippet delivery.
        if not patch or patch.get("policy_status") != "allowed":
            updates["status"] = "escalated"
            updates["terminal_reason"] = "validation_failed"
            updates["validation_retryable"] = False
            updates["escalation_report"] = _escalation(
                {**state, **updates},
                reason_code="validation_failed",
                summary="No allowed patch to propose on issue route",
                what_happened="Skipped-sandbox issue validate requires an allowed patch",
                why_no_fix="Cannot deliver a fix snippet without an allowed patch",
            )
            return updates
        result_id = f"issue-local-{state['run_id']}"
        updates["result_id"] = result_id
        updates["validation_retryable"] = False
        updates["audit_events"] = append_audit(
            {**state, **updates}, "validate", "issue_skipped_sandbox", result_id
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


def _maybe_terminal_comment(state: RunState, updates: dict[str, Any]) -> None:
    """GH-M2–M4 terminal GitHub surfaces; never fail the graph or call sandbox HTTP."""
    merged = {**state, **updates}
    try:
        from raphael_agent.github_commands.auto_comments import maybe_on_terminal

        maybe_on_terminal(merged)
    except Exception:  # noqa: BLE001
        pass
    try:
        from raphael_agent.github_commands.check_runs import maybe_complete_check_run

        maybe_complete_check_run(merged)
    except Exception:  # noqa: BLE001
        return


def node_publish_or_escalate(state: RunState) -> dict[str, Any]:
    if state.get("status") in {"failed_closed", "escalated"}:
        updates = {"current_node": None, "updated_at": utc_now()}
        _maybe_terminal_comment(state, updates)
        return updates
    halt = _budget_halt_updates(state, "publish_or_escalate")
    if halt:
        # Never publish after budget exhaust
        halt["current_node"] = None
        halt["pull_request_url"] = None
        _maybe_terminal_comment(state, halt)
        return halt
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
    elif published.get("delivery") == "issue_snippet":
        updates["status"] = "success_fix_proposed"
        updates["terminal_reason"] = (
            "fix_snippet_dry_run" if published.get("dry_run") else "fix_snippet_posted"
        )
        updates["issue_comment_url"] = published.get("issue_comment_url")
        updates["pull_request_url"] = None
        updates["pull_request_branch"] = None
        updates["audit_events"] = append_audit(
            {**state, **updates},
            "publish_or_escalate",
            "success_fix_proposed",
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
    _maybe_terminal_comment(state, updates)
    return updates


__all__ = [
    "node_ingest",
    "node_evidence",
    "node_diagnose",
    "node_reproduce",
    "node_localize",
    "node_patch",
    "node_validate",
    "node_publish_or_escalate",
    "route_after_validate",
]
