"""Unit tests for publish: PR body, branch naming, dry-run, policy gates."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from raphael_agent.publish import publish
from raphael_agent.publish.branch import branch_name_for_run, pr_title_for_run
from raphael_agent.publish.pr_body import build_pr_body
from raphael_agent.schema_util import validate_agent


def _base_run(**overrides: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "run_id": "run-publish-1",
        "tenant_id": "local-dev",
        "status": "running",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
        "target_environment": "staging",
        "trigger": {
            "kind": "fixture",
            "event_id": "e1",
            "received_at": "2026-08-10T12:00:00Z",
        },
        "affected_resources": [
            {"kind": "Deployment", "name": "payments-api", "namespace": "payments"}
        ],
        "evidence": [
            {
                "evidence_id": "ev-1",
                "kind": "ci_log",
                "summary": "probe failed",
                "content_excerpt": "Readiness probe failed",
            }
        ],
        "diagnosis": {
            "classification": {
                "category": "supported",
                "failure_class": "probe_misconfiguration",
            },
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-probe-port",
                    "rank": 1,
                    "statement": "probe port mismatch",
                    "confidence": 0.92,
                    "supporting_evidence_ids": ["ev-1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "selected_hypothesis_id": "hyp-probe-port",
            "confidence": 0.92,
            "confidence_threshold": 0.7,
            "supporting_evidence_ids": ["ev-1"],
            "analyzer": {"name": "t", "mode": "deterministic"},
            "diagnosed_at": "2026-08-10T12:00:00Z",
        },
        "result_id": "res-abc",
        "sandbox_id": "sb-1",
        "reproduction_result": {
            "reproduced": True,
            "signature_key": "probe_port_mismatch:payments-api:8080!=9090",
        },
        "validation_results": [
            {
                "sandbox_id": "sb-1",
                "passed": True,
                "fail_closed": False,
                "full_validation": True,
                "checks": [
                    {
                        "name": "signature_compare",
                        "kind": "signature_compare",
                        "status": "passed",
                        "duration_ms": 1,
                    }
                ],
                "completed_at": "2026-08-10T12:00:00Z",
            }
        ],
        "candidate_patches": [
            {
                "patch_id": "patch-1",
                "attempt": 1,
                "hypothesis_id": "hyp-probe-port",
                "files": [
                    {
                        "path": "deploy/manifests/broken.yaml",
                        "action": "modify",
                        "content": "port: 8080\n",
                    }
                ],
                "rationale": {
                    "summary": "fix probe port",
                    "evidence_ids": ["ev-1"],
                    "risk_notes": "low",
                    "rollback_notes": "revert",
                },
                "policy_status": "allowed",
                "created_at": "2026-08-10T12:00:00Z",
            }
        ],
        "active_patch_id": "patch-1",
    }
    run.update(overrides)
    return run


def test_branch_naming_git_safe():
    name = branch_name_for_run(_base_run(run_id="Run ID/Weird!!"))
    assert name.startswith("raphael/")
    assert " " not in name
    assert "!" not in name
    assert "probe-misconfiguration" in name or "probe" in name


def test_pr_title_format():
    title = pr_title_for_run(_base_run())
    assert title.startswith("[Raphael] Fix payments-api")


def test_pr_body_has_required_sections():
    body = build_pr_body(_base_run())
    for heading in (
        "## Incident summary",
        "## Root cause",
        "## Evidence",
        "## Change",
        "## Validation",
        "## Sandbox fidelity",
        "## Risk and blast radius",
        "## Rollback",
        "## Audit link",
    ):
        assert heading in body
    assert "res-abc" in body
    assert "probe_port_mismatch" in body


def test_publish_requires_result_id(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    result = publish(_base_run(result_id=None))
    assert result["ok"] is False
    assert result["error"] == "result_id_required"
    assert result["pull_request_url"] is None


def test_publish_skips_escalated(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    result = publish(_base_run(status="escalated"))
    assert result["ok"] is False
    assert result["error"] == "run_not_publishable"


def test_publish_dry_run_sets_placeholder_url(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    result = publish(_base_run())
    validate_agent("publish_result.json", result)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["draft"] is True
    assert result["pull_request_url"]
    assert "raphael_dry_run=1" in result["pull_request_url"]
    assert result["result_id"] == "res-abc"


def test_publish_idempotent_replay(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    first = publish(_base_run())
    again = publish(
        _base_run(
            pull_request_url=first["pull_request_url"],
            publish=first,
        )
    )
    assert again["ok"] is True
    assert again["idempotent_replay"] is True
    assert again["pull_request_url"] == first["pull_request_url"]


def test_publish_live_uses_github_client(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "test-token")
    gh = MagicMock()
    gh.get_ref_sha.return_value = "sha-base"
    gh.find_open_pr.return_value = None
    gh.create_draft_pr.return_value = {
        "html_url": "https://github.com/raphael/demo/pull/42",
        "number": 42,
    }
    result = publish(_base_run(), github=gh)
    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["pull_request_url"].endswith("/pull/42")
    assert result["draft"] is True
    gh.ensure_branch.assert_called()
    gh.put_file.assert_called()
    gh.create_draft_pr.assert_called()


def test_publish_live_idempotent_open_pr(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "test-token")
    gh = MagicMock()
    gh.get_ref_sha.return_value = "sha-base"
    gh.find_open_pr.return_value = {
        "html_url": "https://github.com/raphael/demo/pull/7",
        "number": 7,
    }
    result = publish(_base_run(), github=gh)
    assert result["idempotent_replay"] is True
    gh.put_file.assert_not_called()
    gh.create_draft_pr.assert_not_called()


@pytest.mark.skipif(
    __import__("os").environ.get("RAPHAEL_LIVE_PUBLISH") != "1",
    reason="Set RAPHAEL_LIVE_PUBLISH=1 and RAPHAEL_GITHUB_TOKEN to enable",
)
def test_optional_live_network_publish():
    pytest.skip("placeholder — use manual smoke with RAPHAEL_PUBLISH_MODE=live")
