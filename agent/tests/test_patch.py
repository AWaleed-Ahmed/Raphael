"""Patch policy and template tests."""

from __future__ import annotations

from pathlib import Path

from raphael_agent.patch import propose_patch
from raphael_agent.patch.policy import apply_policy, check_patch_policy, path_allowed
from raphael_agent.schema_util import validate_agent

REPO = Path(__file__).resolve().parents[2]
PROBE_WS = REPO / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"


def test_path_allowlist():
    assert path_allowed("deploy/manifests/app.yaml")
    assert path_allowed(".github/workflows/deploy.yml")
    assert not path_allowed("src/main.go")
    assert not path_allowed("secrets/prod.env")


def test_policy_rejects_secret_like():
    proposal = {
        "files": [
            {
                "path": "deploy/app.yaml",
                "action": "modify",
                "content": "api_key: SUPERSECRETVALUE123\n",
            }
        ]
    }
    violations = check_patch_policy(proposal)
    assert any(v["rule"] == "secret_like_content" for v in violations)


def test_policy_rejects_privilege():
    proposal = {
        "files": [
            {
                "path": "deploy/app.yaml",
                "action": "modify",
                "content": "securityContext:\n  privileged: true\n",
            }
        ]
    }
    violations = check_patch_policy(proposal)
    assert any(v["rule"] == "privilege_escape" for v in violations)


def test_propose_probe_fix_minimal(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    run = {
        "workspace_path": str(PROBE_WS),
        "manifests": {
            "type": "yaml",
            "path": "deploy/manifests",
            "fixed_path": "deploy/manifests_fixed",
        },
        "evidence": [{"evidence_id": "ev-1"}],
        "attempt_count": {"diagnosis": 1, "patch": 0},
        "diagnosis": {
            "selected_hypothesis_id": "hyp-probe-port",
            "classification": {
                "category": "supported",
                "failure_class": "probe_misconfiguration",
            },
        },
    }
    proposal = propose_patch(run)
    validate_agent("patch_proposal.json", proposal)
    assert proposal["policy_status"] == "allowed"
    assert proposal["sandbox_deploy_hint"]["use_files_as_patch"] is True
    contents = "\n".join(f.get("content") or "" for f in proposal["files"])
    assert "port: 8080" in contents
    assert "port: 9090" not in contents.split("readinessProbe:")[-1]


def test_apply_policy_sets_rejected():
    proposal = {
        "patch_id": "p1",
        "attempt": 1,
        "hypothesis_id": "h",
        "files": [{"path": "evil/bin.sh", "action": "modify", "content": "echo hi\n"}],
        "rationale": {"summary": "x", "evidence_ids": []},
        "policy_status": "pending",
        "created_at": "2026-08-10T12:00:00Z",
    }
    updated = apply_policy(proposal)
    assert updated["policy_status"] == "rejected"
