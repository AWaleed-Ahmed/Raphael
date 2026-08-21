"""I0 run list / create / actions HTTP API."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from raphael_agent.http_api.app import create_app
from raphael_agent.runs import delivery_patch_from_run
from raphael_agent.schema_util import validate_agent

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
WORKSPACE = REPO_ROOT / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RAPHAEL_INTERFACE_TOKEN", raising=False)
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_MANUAL_RUN_GRAPH", "1")
    monkeypatch.setenv("RAPHAEL_INGEST_COOLDOWN_SECONDS", "0")
    return TestClient(create_app())


def _create_body(action_id: str) -> dict:
    return {
        "trigger_kind": "manual_ui",
        "action_id": action_id,
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
        "workspace_path": str(WORKSPACE),
        "manifests": {
            "type": "yaml",
            "path": "deploy/manifests",
            "fixed_path": "deploy/manifests_fixed",
        },
        "sandbox_mode": "recorded_stub",
    }


def test_create_list_get_run(client):
    created = client.post("/v1/runs", json=_create_body("act-create-1"))
    assert created.status_code == 201, created.text
    body = created.json()
    validate_agent("run_create_response.json", body)
    assert body["idempotent_replay"] is False
    run_id = body["run_id"]
    assert body["status"] in {
        "success_draft_pr_ready",
        "escalated",
        "failed_closed",
        "pending",
        "running",
    }

    listed = client.get("/v1/runs", params={"owner": "raphael", "repo": "demo"})
    assert listed.status_code == 200
    payload = listed.json()
    validate_agent("run_list_response.json", payload)
    assert any(r["run_id"] == run_id for r in payload["runs"])

    got = client.get(f"/v1/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["run_id"] == run_id


def test_create_idempotent(client):
    body = _create_body("act-idem-1")
    first = client.post("/v1/runs", json=body)
    second = client.post("/v1/runs", json=body)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert second.json()["run_id"] == first.json()["run_id"]


def test_create_idempotent_conflict(client):
    body = _create_body("act-idem-2")
    assert client.post("/v1/runs", json=body).status_code == 201
    body2 = dict(body)
    body2["commit_sha"] = "bbbbbb1234567"
    conflict = client.post("/v1/runs", json=body2)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict_idempotency"


def test_actions_feedback_retry_escalate_cancel(client, tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_MANUAL_RUN_GRAPH", "0")
    # pending run only
    created = client.post(
        "/v1/runs",
        json={
            **_create_body("act-pending-1"),
            "sandbox_mode": "skipped",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["run_id"]
    assert created.json()["status"] == "pending"

    fb = client.post(
        f"/v1/runs/{run_id}/actions",
        json={
            "verb": "feedback",
            "action_id": "act-fb-1",
            "outcome": "rejected",
            "notes": "nope",
        },
    )
    assert fb.status_code == 200
    validate_agent("run_action_response.json", fb.json())
    assert fb.json()["feedback_event_id"]

    # escalate in-flight
    esc = client.post(
        f"/v1/runs/{run_id}/actions",
        json={"verb": "escalate", "action_id": "act-esc-1", "notes": "human"},
    )
    assert esc.status_code == 200
    assert esc.json()["status"] == "escalated"
    assert esc.json()["terminal_reason"] == "human_requested"

    # cancel on terminal → conflict
    bad = client.post(
        f"/v1/runs/{run_id}/actions",
        json={"verb": "cancel", "action_id": "act-cancel-bad"},
    )
    assert bad.status_code == 409

    # new pending for cancel
    monkeypatch.setenv("RAPHAEL_MANUAL_RUN_GRAPH", "0")
    pending = client.post(
        "/v1/runs",
        json={**_create_body("act-pending-2"), "sandbox_mode": "skipped"},
    )
    pid = pending.json()["run_id"]
    cancelled = client.post(
        f"/v1/runs/{pid}/actions",
        json={"verb": "cancel", "action_id": "act-cancel-1"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # retry from escalated parent with graph
    monkeypatch.setenv("RAPHAEL_MANUAL_RUN_GRAPH", "1")
    retry = client.post(
        f"/v1/runs/{run_id}/actions",
        json={
            "verb": "retry",
            "action_id": "act-retry-1",
            "sandbox_mode": "recorded_stub",
        },
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["result_run_id"] != run_id
    child = client.get(f"/v1/runs/{retry.json()['result_run_id']}")
    assert child.json().get("parent_run_id") == run_id


def test_auth_requires_token_when_set(client, monkeypatch):
    monkeypatch.setenv("RAPHAEL_INTERFACE_TOKEN", "secret-token")
    denied = client.get("/v1/runs")
    assert denied.status_code == 401
    ok = client.get(
        "/v1/runs", headers={"Authorization": "Bearer secret-token"}
    )
    assert ok.status_code == 200


def test_delivery_patch_helper():
    run = {
        "candidate_patches": [
            {
                "patch_id": "p1",
                "unified_diff": "diff --git a/x b/x\n",
                "files": [],
            }
        ],
        "active_patch_id": "p1",
        "publish": {},
    }
    assert "diff --git" in (delivery_patch_from_run(run) or "")



def test_manual_terminal_actions_record_outcomes(client, monkeypatch):
    monkeypatch.setenv("RAPHAEL_MANUAL_RUN_GRAPH", "0")
    recorded = []
    monkeypatch.setattr(
        "raphael_agent.runs.record_run_outcome",
        lambda run: recorded.append(dict(run)) or True,
    )

    escalated = client.post(
        "/v1/runs",
        json={**_create_body("act-telemetry-escalate"), "sandbox_mode": "skipped"},
    )
    assert escalated.status_code == 201
    escalated_id = escalated.json()["run_id"]
    response = client.post(
        f"/v1/runs/{escalated_id}/actions",
        json={"verb": "escalate", "action_id": "act-telemetry-escalate-action"},
    )
    assert response.status_code == 200
    assert recorded[-1]["run_id"] == escalated_id
    assert recorded[-1]["status"] == "escalated"

    cancelled = client.post(
        "/v1/runs",
        json={**_create_body("act-telemetry-cancel"), "sandbox_mode": "skipped"},
    )
    assert cancelled.status_code == 201
    cancelled_id = cancelled.json()["run_id"]
    response = client.post(
        f"/v1/runs/{cancelled_id}/actions",
        json={"verb": "cancel", "action_id": "act-telemetry-cancel-action"},
    )
    assert response.status_code == 200
    assert recorded[-1]["run_id"] == cancelled_id
    assert recorded[-1]["status"] == "cancelled"


def test_graph_terminal_records_outcome(monkeypatch):
    from raphael_agent.graph.nodes import node_publish_or_escalate

    recorded = []
    monkeypatch.setattr(
        "raphael_agent.graph.nodes.record_run_outcome",
        lambda run: recorded.append(dict(run)) or True,
    )
    updates = node_publish_or_escalate(
        {
            "run_id": "graph-terminal-1",
            "status": "failed_closed",
            "terminal_reason": "already_failed",
            "repository": {"owner": "raphael", "name": "demo"},
        }
    )

    assert updates["current_node"] is None
    assert recorded[0]["run_id"] == "graph-terminal-1"
    assert recorded[0]["status"] == "failed_closed"
