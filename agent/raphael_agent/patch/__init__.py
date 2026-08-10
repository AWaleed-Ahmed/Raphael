"""Patch stubs — Phase 2 will generate constrained repo patches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def stub_propose_patch(run: dict[str, Any]) -> dict[str, Any]:
    """Propose a constrained path change (fixture: switch to fixed manifests)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    diagnosis = run.get("diagnosis") or {}
    hypothesis_id = diagnosis.get("selected_hypothesis_id") or "hyp-unknown"
    attempt = int((run.get("attempt_count") or {}).get("patch", 0)) + 1
    manifests = run.get("manifests") or {}
    fixed_path = manifests.get("fixed_path") or "deploy/manifests_fixed"
    return {
        "patch_id": f"patch-{attempt}",
        "attempt": attempt,
        "hypothesis_id": hypothesis_id,
        "files": [
            {
                "path": f"{fixed_path}/.raphael-stub",
                "action": "modify",
                "content": "# stub marker: use fixed manifests path in sandbox deploy\n",
                "unified_diff_hunk": None,
            }
        ],
        "unified_diff": None,
        "rationale": {
            "summary": "Align readiness probe port with container port (stub uses fixed manifests dir)",
            "evidence_ids": [e["evidence_id"] for e in run.get("evidence") or []],
            "risk_notes": "Config-only change; no secret or RBAC edits",
            "rollback_notes": "Revert to previous probe port",
        },
        "policy_status": "allowed",
        "policy_violations": [],
        "sandbox_deploy_hint": {
            "manifests_path": fixed_path,
            "use_files_as_patch": False,
        },
        "created_at": now,
    }
