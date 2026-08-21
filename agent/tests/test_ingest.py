"""Phase 1 ingest: normalize, policy, webhook auth, persistence."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.evidence.github_actions import collect_github_actions_evidence
from raphael_agent.http_api import create_app
from raphael_agent.ingest import (
    WebhookAuthError,
    accept_failed_run_event,
    normalize_failed_run_event,
    parse_github_webhook,
    verify_github_signature,
)
from raphael_agent.ingest.policy import IngestPolicyConfig
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore

AGENT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = AGENT_ROOT / "fixtures" / "failed_run_event.json"
GH_WORKFLOW = AGENT_ROOT / "fixtures" / "github_workflow_run_failure.json"
GH_CHECK = AGENT_ROOT / "fixtures" / "github_check_run_failure.json"


@pytest.fixture()
def store(tmp_path: Path) -> RunStore:
    return RunStore(tmp_path / "data")


def test_normalize_fixture_has_fingerprint():
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seed = normalize_failed_run_event(event)
    assert seed["failure_fingerprint"]
    assert seed["correlation"]["workload"] == "payments-api"
    assert seed["trigger"]["kind"] == "fixture"


def test_normalize_github_workflow_run():
    payload = json.loads(GH_WORKFLOW.read_text(encoding="utf-8"))
    seed = normalize_failed_run_event(payload)
    assert seed["trigger"]["kind"] == "github_workflow_run"
    assert seed["repository"]["owner"] == "raphael"
    assert seed["commit_sha"].startswith("abcdef")
    assert "Deploy staging" in seed["correlation"]["workflow_name"]
    assert seed["run_id"] == "ghw-5544332211"


def test_normalize_github_check_run():
    payload = json.loads(GH_CHECK.read_text(encoding="utf-8"))
    seed = normalize_failed_run_event(payload)
    assert seed["trigger"]["kind"] == "github_check_run"
    assert seed["correlation"]["check_name"] == "deploy / helm-upgrade"


def test_github_pipeline_evidence_is_scoped_to_triggering_repository():
    base = json.loads(GH_WORKFLOW.read_text(encoding="utf-8"))
    first = dict(base)
    first["repository"] = {"owner": {"login": "acme"}, "name": "payments"}
    first["workflow_run"] = dict(base["workflow_run"])
    first["workflow_run"]["head_sha"] = "1111111111111111111111111111111111111111"
    second = dict(base)
    second["repository"] = {"owner": {"login": "globex"}, "name": "orders"}
    second["workflow_run"] = dict(base["workflow_run"])
    second["workflow_run"]["head_sha"] = "2222222222222222222222222222222222222222"

    first_run = normalize_failed_run_event(first)
    second_run = normalize_failed_run_event(second)
    first_evidence = collect_github_actions_evidence(first_run)
    second_evidence = collect_github_actions_evidence(second_run)

    assert first_run["repository"] != second_run["repository"]
    assert first_run["commit_sha"] != second_run["commit_sha"]
    assert "acme/payments" in first_evidence[0]["content_excerpt"]
    assert "globex/orders" in second_evidence[0]["content_excerpt"]
    assert "globex/orders" not in first_evidence[0]["content_excerpt"]
    assert "acme/payments" not in second_evidence[0]["content_excerpt"]


def test_accept_persists_run(store: RunStore):
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["run_id"] = "ingest-test-001"
    decision, run = accept_failed_run_event(
        event, store=store, sandbox_mode="skipped"
    )
    validate_agent("ingest_decision.json", decision)
    assert decision["decision"] == "accepted"
    assert run is not None
    assert store.get_run(run["run_id"]) is not None
    assert run["failure_fingerprint"] == decision["fingerprint"]


def test_dedupe_active_run(store: RunStore):
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["run_id"] = "ingest-dedupe-a"
    d1, r1 = accept_failed_run_event(event, store=store, sandbox_mode="skipped")
    assert d1["decision"] == "accepted" and r1 is not None

    event2 = dict(event)
    event2["run_id"] = "ingest-dedupe-b"
    event2["event_id"] = "evt-dup"
    d2, r2 = accept_failed_run_event(event2, store=store, sandbox_mode="skipped")
    assert d2["decision"] == "duplicate"
    assert r2 is None
    assert d2["existing_run_id"] == r1["run_id"]


def test_cooldown(store: RunStore):
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["run_id"] = "ingest-cool-a"
    d1, r1 = accept_failed_run_event(event, store=store, sandbox_mode="skipped")
    assert d1["decision"] == "accepted"
    # Mark prior terminal so active dedupe does not fire; cooldown should.
    assert r1 is not None
    r1["status"] = "success_draft_pr_ready"
    store.save_run(r1)

    event2 = dict(event)
    event2["run_id"] = "ingest-cool-b"
    event2["event_id"] = "evt-cool"
    d2, r2 = accept_failed_run_event(
        event2,
        store=store,
        policy=IngestPolicyConfig(cooldown_seconds=3600, max_concurrent_runs=10),
        sandbox_mode="skipped",
    )
    assert d2["decision"] == "cooldown"
    assert r2 is None
    assert (d2.get("cooldown_seconds_remaining") or 0) > 0


def test_concurrency_limit(store: RunStore):
    policy = IngestPolicyConfig(cooldown_seconds=0, max_concurrent_runs=1)
    base = json.loads(FIXTURE.read_text(encoding="utf-8"))

    e1 = dict(base)
    e1["run_id"] = "ingest-conc-1"
    e1["commit_sha"] = "aaaaaaaaaaaaa"
    e1["event_id"] = "e1"
    d1, _ = accept_failed_run_event(e1, store=store, policy=policy, sandbox_mode="skipped")
    assert d1["decision"] == "accepted"

    e2 = dict(base)
    e2["run_id"] = "ingest-conc-2"
    e2["commit_sha"] = "bbbbbbbbbbbbb"
    e2["event_id"] = "e2"
    d2, r2 = accept_failed_run_event(e2, store=store, policy=policy, sandbox_mode="skipped")
    assert d2["decision"] == "concurrency_limit"
    assert r2 is None


def test_webhook_signature_roundtrip():
    secret = "test-secret"
    body = b'{"ok":true}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    verify_github_signature(body, "sha256=" + digest, secret=secret)
    with pytest.raises(WebhookAuthError):
        verify_github_signature(body, "sha256=deadbeef", secret=secret)


def test_parse_github_webhook_workflow():
    body = GH_WORKFLOW.read_bytes()
    seed, reason = parse_github_webhook(
        body,
        event_name="workflow_run",
        delivery_id="deliv-1",
        signature_header=None,
        secret=None,
    )
    assert reason == ""
    assert seed is not None
    assert seed["trigger"]["kind"] == "github_workflow_run"


def test_http_webhook_accepts_failure(store: RunStore, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path / "http-data"))
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("RAPHAEL_INGEST_RUN_GRAPH", raising=False)
    # Force cooldown off for isolated HTTP test store
    monkeypatch.setenv("RAPHAEL_INGEST_COOLDOWN_SECONDS", "0")
    monkeypatch.setenv("RAPHAEL_INGEST_MAX_CONCURRENT_RUNS", "10")

    client = TestClient(create_app())
    body = GH_WORKFLOW.read_bytes()
    resp = client.post(
        "/v1/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "deliv-http-1",
        },
    )
    assert resp.status_code == 202
    payload = resp.json()
    assert payload["ingest"]["decision"] == "accepted"
    run_id = payload["run_id"]
    got = client.get(f"/v1/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["status"] == "pending"


def test_http_ignores_success_conclusion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path / "http-ignore"))
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", raising=False)
    payload = json.loads(GH_WORKFLOW.read_text(encoding="utf-8"))
    payload["workflow_run"]["conclusion"] = "success"
    client = TestClient(create_app())
    resp = client.post(
        "/v1/webhooks/github",
        content=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": "deliv-ignore",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["decision"] == "ignored"


def test_redaction_strips_secrets():
    text, notes = redact_text("Authorization: Bearer SUPERSECRETTOKEN value")
    assert "SUPERSECRETTOKEN" not in text
    assert "bearer_token" in notes or "generic_api_key" in notes
