"""Operator metrics summary tests."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from raphael_agent.http_api.app import create_app
from raphael_agent.metrics import summarize_store
from raphael_agent.store import RunStore


def test_summarize_store(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    store = RunStore(tmp_path)
    store.save_run(
        {
            "run_id": "m1",
            "status": "success_draft_pr_ready",
            "created_at": "2026-08-10T12:00:00Z",
            "updated_at": "2026-08-10T12:01:00Z",
            "attempt_count": {"diagnosis": 1, "patch": 1},
            "publish": {"mode": "dry_run", "dry_run": True, "ok": True},
        }
    )
    store.save_run(
        {
            "run_id": "m2",
            "status": "escalated",
            "created_at": "2026-08-10T12:00:00Z",
            "updated_at": "2026-08-10T12:00:30Z",
            "attempt_count": {"diagnosis": 1, "patch": 0},
        }
    )
    store.append_decision(
        {
            "decision": "accepted",
            "event_id": "e1",
            "fingerprint": "f",
            "decided_at": "2026-08-10T12:00:00Z",
        }
    )
    summary = summarize_store(store)
    assert summary["runs_total"] == 2
    assert summary["by_terminal_status"]["success_draft_pr_ready"] == 1
    assert summary["by_terminal_status"]["escalated"] == 1
    assert summary["publish_modes"]["dry_run"] == 1
    assert summary["ingest_decisions"]["accepted"] == 1
    assert summary["patch_attempts_total"] == 1


def test_metrics_endpoint(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    response = client.get("/v1/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "runs_total" in body
    assert "by_terminal_status" in body
