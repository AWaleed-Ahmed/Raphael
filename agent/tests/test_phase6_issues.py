"""Phase 6 — labeled Issues route + optional model + fix_rules."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from raphael_agent.graph import run_stub_graph
from raphael_agent.graph.state import initial_run_state
from raphael_agent.ingest.github import parse_github_webhook
from raphael_agent.ingest.normalize import normalize_github_issue
from raphael_agent.patch.llm import try_llm_patch
from raphael_agent.publish import publish
from raphael_agent.rules import load_or_derive_fix_rules
from raphael_agent.schema_util import validate_agent

AGENT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = AGENT_ROOT / "fixtures" / "github_issue_labeled.json"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE = REPO_ROOT / "agent" / "fixtures" / "scenarios" / "probe_port_mismatch"


def test_normalize_labeled_issue():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seed = normalize_github_issue(
        payload,
        raw_ref="fixture:issue",
        commit_sha="abcdef1234567890abcdef1234567890abcdef12",
    )
    assert seed["trigger"]["kind"] == "github_issue"
    assert seed["delivery_mode"] == "issue_snippet"
    assert seed["issue_number"] == 42
    assert "raphael:fix" in seed["issue_labels"]
    assert seed["failure_class_hint"] == "probe_misconfiguration"
    assert seed["commit_sha"].startswith("abcdef")


def test_ignore_issue_without_trigger_label():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["issue"]["labels"] = [{"name": "bug"}]
    payload["action"] = "opened"
    del payload["label"]
    with pytest.raises(ValueError, match="missing trigger label"):
        normalize_github_issue(payload, raw_ref="x", commit_sha="abcdef1")


def test_parse_issues_webhook(monkeypatch):
    monkeypatch.setenv("RAPHAEL_ISSUE_TRIGGER_LABEL", "raphael:fix")
    body = FIXTURE.read_bytes()
    seed, reason = parse_github_webhook(body, event_name="issues", delivery_id="d1")
    assert reason == ""
    assert seed is not None
    assert seed["issue_number"] == 42


def test_preset_fix_rules(tmp_path: Path):
    raphael = tmp_path / ".raphael"
    raphael.mkdir()
    (raphael / "issue-fix.yaml").write_text(
        "writable_path_prefixes:\n  - deploy/\nmust:\n  - keep probes\nmust_not:\n  - secrets\n",
        encoding="utf-8",
    )
    rules = load_or_derive_fix_rules(tmp_path)
    validate_agent("fix_rules.json", rules)
    assert rules["source"] == "preset"
    assert any(p.startswith("deploy") for p in rules["writable_path_prefixes"])


def test_derived_fix_rules(tmp_path: Path):
    (tmp_path / "CONTRIBUTING.md").write_text(
        "# Contributing\n- Prefer small diffs\n- writable paths: deploy/\n",
        encoding="utf-8",
    )
    rules = load_or_derive_fix_rules(tmp_path)
    validate_agent("fix_rules.json", rules)
    assert rules["source"] == "derived"
    assert "CONTRIBUTING.md" in rules["source_paths"]


def test_issue_route_escalates_without_model(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "0")
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    seed = {
        "run_id": "ghi-test-1",
        "tenant_id": "local-dev",
        "trigger_kind": "github_issue",
        "event_id": "issues:1:labeled",
        "commit_sha": "abcdef1234567",
        "repository": {"owner": "raphael", "name": "demo"},
        "delivery_mode": "issue_snippet",
        "issue_number": 7,
        "issue_labels": ["raphael:fix"],
        "issue_title": "Please fix",
        "issue_body": "no class hint",
        "provisional_failure_key": "github_issue|raphael:fix|7",
    }
    from raphael_agent.ingest.normalize import normalize_fixture_event

    normalized = normalize_fixture_event(seed)
    state = initial_run_state(normalized, sandbox_mode="skipped")
    final = run_stub_graph(state)
    assert final["status"] == "escalated"
    assert final.get("terminal_reason") in {"low_confidence", "model_required", "policy_blocked"}


def test_issue_route_with_hint_and_workspace_templates(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "0")
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    seed = {
        "run_id": "ghi-probe-1",
        "tenant_id": "local-dev",
        "trigger_kind": "github_issue",
        "event_id": "issues:42:labeled",
        "commit_sha": "abcdef1234567",
        "repository": {"owner": "raphael", "name": "demo"},
        "delivery_mode": "issue_snippet",
        "issue_number": 42,
        "issue_labels": ["raphael:fix"],
        "issue_title": "Probe wrong",
        "issue_body": "raphael-failure-class: probe_misconfiguration",
        "failure_class_hint": "probe_misconfiguration",
        "workspace_path": str(PROBE),
        "manifests": {"type": "yaml", "path": "deploy/manifests", "fixed_path": "deploy/fixed"},
        "provisional_failure_key": "github_issue|raphael:fix|42|probe",
    }
    from raphael_agent.ingest.normalize import normalize_fixture_event

    normalized = normalize_fixture_event(seed)
    state = initial_run_state(normalized, sandbox_mode="recorded_stub")
    final = run_stub_graph(state)
    assert final["status"] == "success_fix_proposed"
    assert final.get("publish", {}).get("delivery") == "issue_snippet"
    assert final.get("publish", {}).get("ok") is True
    assert final.get("publish", {}).get("dry_run") is True
    assert final.get("fix_rules") is not None


def test_llm_patch_mocked(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "1")
    monkeypatch.setenv("RAPHAEL_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("RAPHAEL_LLM_BASE_URL", "https://llm.test/v1")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "fix probe port",
                                    "files": [
                                        {
                                            "path": "deploy/app.yaml",
                                            "action": "modify",
                                            "content": "apiVersion: v1\n",
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ]
            }

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(httpx, "Client", _Client)
    run = {
        "attempt_count": {"diagnosis": 1, "patch": 0},
        "delivery_mode": "issue_snippet",
        "trigger": {"kind": "github_issue"},
        "issue_title": "fix",
        "issue_body": "please",
        "fix_rules": {
            "source": "derived",
            "writable_path_prefixes": ["deploy/"],
            "must": [],
            "must_not": [],
            "created_at": "2026-08-10T00:00:00Z",
        },
        "evidence": [],
        "diagnosis": {
            "selected_hypothesis_id": "hyp-issue-model",
            "classification": {"failure_class": "issue_model_fix"},
        },
        "manifests": {"path": "deploy/manifests"},
    }
    proposal = try_llm_patch(run)
    assert proposal is not None
    assert proposal["policy_status"] == "allowed"
    assert proposal["files"][0]["path"] == "deploy/app.yaml"


def test_issue_snippet_publish_dry_run():
    run = {
        "run_id": "ghi-pub",
        "status": "running",
        "delivery_mode": "issue_snippet",
        "trigger": {"kind": "github_issue"},
        "result_id": "issue-local-ghi-pub",
        "issue_number": 9,
        "commit_sha": "abcdef1234567",
        "repository": {"owner": "raphael", "name": "demo"},
        "active_patch_id": "patch-1",
        "candidate_patches": [
            {
                "patch_id": "patch-1",
                "policy_status": "allowed",
                "rationale": {"summary": "fix it", "evidence_ids": []},
                "files": [
                    {
                        "path": "deploy/app.yaml",
                        "action": "modify",
                        "content": "port: 8080\n",
                    }
                ],
            }
        ],
    }
    result = publish(run)
    assert result["ok"] is True
    assert result["delivery"] == "issue_snippet"
    assert result["dry_run"] is True
    assert "port: 8080" in (result.get("fix_snippet") or "")
    validate_agent("publish_result.json", result)
