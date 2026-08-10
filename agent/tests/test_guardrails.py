"""Permission-matrix / pilot guardrails — must stay green for pilot week."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.guardrails import (
    assert_publish_guardrails,
    go_nogo_verdict,
    live_publish_allowed,
)
from raphael_agent.http_api import create_app
from raphael_agent.patch.policy import apply_policy
from raphael_agent.publish import publish
from raphael_agent.publish.config import effective_publish_mode
from tests.test_publish import _base_run

INJECTION = Path(__file__).resolve().parents[1] / "fixtures" / "injection"


@pytest.fixture(autouse=True)
def _safe_defaults(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.delenv("RAPHAEL_AUTO_MERGE", raising=False)
    monkeypatch.delenv("RAPHAEL_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "")


def test_no_publish_without_result_id():
    run = _base_run()
    run["result_id"] = None
    assert assert_publish_guardrails(run) == []
    result = publish(run)
    assert result["ok"] is False
    assert result["error"] == "result_id_required"
    assert result["pull_request_url"] is None


def test_no_publish_when_escalated():
    run = _base_run(status="escalated")
    result = publish(run)
    assert result["ok"] is False
    assert result["error"] == "run_not_publishable"


def test_partner_dry_run_blocks_live_even_with_token_and_mode(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "probe_misconfiguration")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "t")
    run = _base_run()
    assert effective_publish_mode(run) == "dry_run"
    assert live_publish_allowed(run) is False
    result = publish(run)
    assert result["dry_run"] is True
    assert "raphael_dry_run=1" in (result.get("pull_request_url") or "")


def test_empty_allowlist_never_live(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "allowlist")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "t")
    run = _base_run()
    assert effective_publish_mode(run) == "dry_run"
    assert live_publish_allowed(run) is False


def test_live_requires_all_gates(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "allowlist")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "live")
    monkeypatch.setenv("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "probe_misconfiguration")
    monkeypatch.setenv("RAPHAEL_GITHUB_TOKEN", "test-token")
    run = _base_run()
    assert live_publish_allowed(run) is True
    gh = MagicMock()
    gh.get_ref_sha.return_value = "sha"
    gh.find_open_pr.return_value = None
    gh.create_draft_pr.return_value = {
        "html_url": "https://github.com/raphael/demo/pull/42",
        "number": 42,
    }
    result = publish(run, github=gh)
    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["draft"] is True  # never merge


def test_validation_fail_closed_blocks_publish():
    run = _base_run()
    run["validation_results"] = [
        {
            "sandbox_id": "sb-1",
            "passed": False,
            "fail_closed": True,
            "full_validation": False,
            "checks": [],
        }
    ]
    result = publish(run)
    assert result["ok"] is False
    assert result["error"] == "validation_not_passed"


def test_injection_cannot_bypass_allowlist_or_force_pr():
    widen = json.loads((INJECTION / "widen_allowlist.json").read_text(encoding="utf-8"))
    rejected = apply_policy(dict(widen["malicious_patch"]))
    assert rejected["policy_status"] == "rejected"

    skip = json.loads((INJECTION / "skip_validation.json").read_text(encoding="utf-8"))
    run = _base_run()
    run["result_id"] = None
    run["evidence"] = skip["evidence"]
    result = publish(run)
    assert result["ok"] is False


def test_secret_redaction_guardrail():
    text, notes = redact_text("password=hunter2 bearer TOK")
    assert "hunter2" not in text.lower() or "REDACTED" in text
    assert notes


def test_go_nogo_safe_default(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.delenv("RAPHAEL_AUTO_MERGE", raising=False)
    verdict = go_nogo_verdict()
    assert verdict["go"] is True


def test_go_nogo_fails_on_auto_merge(monkeypatch):
    monkeypatch.setenv("RAPHAEL_AUTO_MERGE", "true")
    verdict = go_nogo_verdict()
    assert verdict["go"] is False
    assert "no_auto_merge_configured" in verdict["failed"]


def test_http_go_nogo(monkeypatch):
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.delenv("RAPHAEL_AUTO_MERGE", raising=False)
    client = TestClient(create_app())
    resp = client.get("/v1/pilot/go-nogo")
    assert resp.status_code == 200
    assert resp.json()["go"] is True
