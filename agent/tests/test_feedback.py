"""FR-065 feedback recording tests."""

from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from raphael_agent.feedback import (
    JsonlFeedbackRecorder,
    feedback_from_pull_request_webhook,
    feedback_from_run,
    normalize_feedback_event,
)
from raphael_agent.http_api import create_app
from raphael_agent.publish import publish
from raphael_agent.schema_util import validate_agent
from tests.test_publish import _base_run


def test_normalize_and_schema(tmp_path: Path):
    event = normalize_feedback_event(
        {
            "outcome": "rejected",
            "source": "test",
            "run_id": "r1",
            "notes": "false positive",
        }
    )
    validate_agent(
        "feedback_event.json",
        {k: v for k, v in event.items() if v is not None},
    )
    rec = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl")
    recorded = rec.record(event)
    assert recorded["outcome"] == "rejected"
    assert len(rec.read_all()) == 1


def test_feedback_from_run_and_publish_hook(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_FEEDBACK_ON_PUBLISH", "1")
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_FEEDBACK_RECORDER", "jsonl")
    run = _base_run()
    result = publish(run)
    assert result["ok"] is True
    rows = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl").read_all()
    assert any(r.get("outcome") == "dry_run_prepared" for r in rows)


def test_pull_request_webhook_merged():
    payload = {
        "action": "closed",
        "pull_request": {
            "id": 55,
            "number": 12,
            "merged": True,
            "html_url": "https://github.com/raphael/demo/pull/12",
        },
        "repository": {"name": "demo", "owner": {"login": "raphael"}},
        "sender": {"login": "alice"},
    }
    event = feedback_from_pull_request_webhook(payload)
    assert event is not None
    assert event["outcome"] == "merged"
    assert event["actor"] == "alice"


def test_http_feedback_endpoint(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_FEEDBACK_RECORDER", "jsonl")
    client = TestClient(create_app())
    resp = client.post(
        "/v1/feedback",
        json={
            "outcome": "accepted",
            "run_id": "r-http",
            "notes": "lgtm",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["outcome"] == "accepted"


def test_feedback_from_run_fields():
    run = _base_run()
    event = feedback_from_run(run, outcome="accepted", source="cli", actor="bob")
    assert event["failure_class"] == "probe_misconfiguration"
    assert event["run_id"] == run["run_id"]
    assert event["actor"] == "bob"
