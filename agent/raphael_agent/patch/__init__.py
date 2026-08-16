"""Constrained patch proposal generation (FR-040–045)."""

from __future__ import annotations

from typing import Any

from raphael_agent.patch.config import max_patch_attempts
from raphael_agent.patch.llm import try_llm_patch
from raphael_agent.patch.policy import apply_policy
from raphael_agent.patch.templates import generate_files_for_diagnosis
from raphael_agent.schema_util import validate_agent
from raphael_agent.timeutil import utc_now

__all__ = [
    "propose_patch",
    "stub_propose_patch",
    "max_patch_attempts",
    "apply_policy",
]


def _is_issue_route(run: dict[str, Any]) -> bool:
    return (run.get("trigger") or {}).get("kind") == "github_issue" or run.get(
        "delivery_mode"
    ) == "issue_snippet"


def propose_patch(run: dict[str, Any]) -> dict[str, Any]:
    """Build a constrained patch_proposal for the selected diagnosis."""
    # Route B: optional model patch first (still policy-gated).
    if _is_issue_route(run):
        llm_proposal = try_llm_patch(run)
        if llm_proposal is not None:
            return llm_proposal

    diagnosis = run.get("diagnosis") or {}
    hypothesis_id = diagnosis.get("selected_hypothesis_id") or "hyp-unknown"
    attempt = int((run.get("attempt_count") or {}).get("patch", 0)) + 1
    evidence_ids = [e["evidence_id"] for e in run.get("evidence") or [] if e.get("evidence_id")]
    manifests = run.get("manifests") or {}
    manifests_path = manifests.get("path") or "deploy/manifests"

    files, summary = generate_files_for_diagnosis(run)
    if not files:
        # Fallback for fixture workspaces that ship a parallel fixed tree (recorded/live probe).
        fixed_path = manifests.get("fixed_path")
        if fixed_path and (diagnosis.get("classification") or {}).get("failure_class") == (
            "probe_misconfiguration"
        ):
            files = [
                {
                    "path": f"{fixed_path}/.raphael-use-fixed-tree",
                    "action": "modify",
                    "content": "# deploy hint: use fixed manifests path\n",
                    "unified_diff_hunk": None,
                }
            ]
            summary = (
                "Align readiness probe port (deploy via fixed manifests path hint)"
            )
            deploy_hint = {
                "manifests_path": fixed_path,
                "use_files_as_patch": False,
            }
        elif _is_issue_route(run):
            # No model and no template — empty marker so policy can reject / escalate.
            files = [
                {
                    "path": f"{manifests_path}/.raphael-empty-patch",
                    "action": "modify",
                    "content": "# no model/template fix available for issue route\n",
                    "unified_diff_hunk": None,
                }
            ]
            summary = "No model or deterministic fix available for issue"
            deploy_hint = {
                "manifests_path": manifests_path,
                "use_files_as_patch": False,
            }
        else:
            files = [
                {
                    "path": f"{manifests_path}/.raphael-empty-patch",
                    "action": "modify",
                    "content": "# no deterministic fix generated\n",
                    "unified_diff_hunk": None,
                }
            ]
            summary = "No deterministic file fix available"
            deploy_hint = {
                "manifests_path": manifests_path,
                "use_files_as_patch": False,
            }
    else:
        deploy_hint = {
            "manifests_path": manifests_path,
            "use_files_as_patch": True,
        }

    localized = list(run.get("fault_candidates") or [])[:3]
    localized_note = ""
    if localized:
        top = localized[0]
        localized_note = (
            f" Top localized candidate: {top.get('path')}:{top.get('line')} "
            f"({top.get('symbol')}) score={top.get('score')}."
        )

    proposal: dict[str, Any] = {
        "patch_id": f"patch-{attempt}",
        "attempt": attempt,
        "hypothesis_id": hypothesis_id,
        "files": files,
        "unified_diff": None,
        "rationale": {
            "summary": f"{summary}.{localized_note}" if localized_note else summary,
            "evidence_ids": evidence_ids,
            "risk_notes": "Config/manifest-only change within allowlisted paths",
            "rollback_notes": "Revert the patched file(s) to the failing commit contents",
        },
        "policy_status": "pending",
        "policy_violations": [],
        "sandbox_deploy_hint": deploy_hint,
        "created_at": utc_now(),
    }
    proposal = apply_policy(proposal)
    # Issue route without LLM: escalate empty marker as model_required rather than fake allow.
    if (
        _is_issue_route(run)
        and any(
            str(f.get("path") or "").endswith(".raphael-empty-patch")
            for f in (proposal.get("files") or [])
        )
    ):
        proposal["policy_status"] = "rejected"
        proposal["policy_violations"] = [
            {
                "rule": "model_required",
                "message": "Issue route needs RAPHAEL_LLM_DIAGNOSIS=1 and RAPHAEL_LLM_PATCH=1 "
                "or a known raphael-failure-class template hit",
            }
        ]
    validate_agent("patch_proposal.json", proposal)
    return proposal


def stub_propose_patch(run: dict[str, Any]) -> dict[str, Any]:
    return propose_patch(run)
