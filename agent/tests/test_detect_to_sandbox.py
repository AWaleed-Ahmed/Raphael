"""Detection â†’ sandbox wiring tests.

Answers: is the agent connected to the sandbox, and does a deployment failure
auto-start a run?

Connection: yes over HTTP (``RAPHAEL_SANDBOX_URL``, default :8090) when
``sandbox_mode=live``. Auto-detect: only when a webhook hits the agent **and**
``RAPHAEL_INGEST_RUN_GRAPH=1``. There is no silent cluster scrape unless the
K8s watcher webhook is enabled and fed events.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from raphael_agent.http_api.app import create_app
from raphael_agent.ingest import accept_and_run_graph
from raphael_agent.sandbox_client import SandboxClient
from raphael_agent.schema_util import for_run_record_validation, validate_agent
from raphael_agent.store import RunStore

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
WORKSPACE = REPO_ROOT / "agent" / "fixtures" / "scenarios" / "probe_port_mismatch"
GH_WORKFLOW = AGENT_ROOT / "fixtures" / "github_workflow_run_failure.json"


def test_agent_sandbox_client_defaults_to_8090():
    client = SandboxClient(validate=False)
    assert client.base_url.rstrip("/").endswith(":8090") or "8090" in client.base_url


def test_webhook_does_not_auto_run_graph_by_default(monkeypatch, tmp_path):
    """CI/deployment failure webhook alone does NOT run the graph unless opted in."""
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("RAPHAEL_INGEST_RUN_GRAPH", raising=False)
    monkeypatch.setenv("RAPHAEL_INGEST_COOLDOWN_SECONDS", "0")

    client = TestClient(create_app())
    body = GH_WORKFLOW.read_bytes()
    response = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "deliv-no-autorun",
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["ingest"]["decision"] == "accepted"
    assert payload["status"] == "pending"
    # Graph never ran â€” no terminal success/escalate from this request alone.
    assert payload["status"] not in {
        "success_draft_pr_ready",
        "escalated",
        "failed_closed",
    }


def test_webhook_autorun_sets_terminal_status(monkeypatch, tmp_path):
    """With RAPHAEL_INGEST_RUN_GRAPH=1 the webhook response includes graph status."""
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("RAPHAEL_INGEST_RUN_GRAPH", "1")
    monkeypatch.setenv("RAPHAEL_AGENT_SANDBOX_MODE", "recorded_stub")
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_INGEST_COOLDOWN_SECONDS", "0")

    client = TestClient(create_app())
    body = GH_WORKFLOW.read_bytes()
    response = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "deliv-autorun-1",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ingest"]["decision"] == "accepted"
    # Without workspace/manifests the graph typically escalates or fails closed â€”
    # the important FR property is that detection triggered a graph run.
    assert payload["status"] in {
        "success_draft_pr_ready",
        "escalated",
        "failed_closed",
        "pending",
    }
    assert payload["status"] != "pending"


def test_ci_failure_event_through_graph_to_sandbox_stub(monkeypatch, tmp_path):
    """End-to-end: failed-run event â†’ graph â†’ sandbox recorded_stub â†’ dry-run PR."""
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_INGEST_COOLDOWN_SECONDS", "0")

    event = {
        "run_id": f"detect-e2e-{uuid.uuid4().hex[:8]}",
        "tenant_id": "local-dev",
        "trigger_kind": "github_workflow_run",
        "event_id": f"wf-detect-{uuid.uuid4().hex[:8]}",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
        "target_environment": "staging",
        "workspace_path": str(WORKSPACE),
        "manifests": {
            "type": "yaml",
            "path": "deploy/manifests",
            "fixed_path": "deploy/manifests_fixed",
        },
        "provisional_failure_key": f"github_workflow_run|deploy|{uuid.uuid4().hex[:6]}",
    }
    decision, final = accept_and_run_graph(
        event, store=RunStore(tmp_path), sandbox_mode="recorded_stub"
    )
    assert decision["decision"] == "accepted"
    assert final is not None
    validate_agent("run_record.json", for_run_record_validation(final))
    assert final["status"] == "success_draft_pr_ready"
    assert final["sandbox_mode"] == "recorded_stub"
    assert final.get("result_id")
    assert final.get("pull_request_url") and "raphael_dry_run=1" in final["pull_request_url"]


@pytest.mark.kind
def test_ci_failure_through_live_sandbox_kind(monkeypatch, tmp_path):
    """Same detection path against a live controller (kind). Skips if down."""
    client = SandboxClient(validate=False)
    if not client.is_reachable():
        pytest.skip(
            "sandbox controller not reachable â€” start kind + controller on :8090"
        )

    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_INGEST_COOLDOWN_SECONDS", "0")

    event = {
        "run_id": f"detect-live-{uuid.uuid4().hex[:8]}",
        "tenant_id": "local-dev",
        "trigger_kind": "github_workflow_run",
        "event_id": f"wf-live-{uuid.uuid4().hex[:8]}",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
        "target_environment": "staging",
        "workspace_path": str(WORKSPACE),
        "manifests": {
            "type": "yaml",
            "path": "deploy/manifests",
            "fixed_path": "deploy/manifests_fixed",
        },
        "provisional_failure_key": f"github_workflow_run|deploy|{uuid.uuid4().hex[:6]}",
    }
    decision, final = accept_and_run_graph(
        event, store=RunStore(tmp_path), sandbox_mode="live"
    )
    assert decision["decision"] == "accepted"
    assert final is not None
    validate_agent("run_record.json", for_run_record_validation(final))
    assert final["sandbox_mode"] == "live"
    assert final["status"] in {
        "success_draft_pr_ready",
        "escalated",
        "failed_closed",
    }
    if final["status"] == "success_draft_pr_ready":
        assert final.get("sandbox_id")
        assert final.get("result_id")
