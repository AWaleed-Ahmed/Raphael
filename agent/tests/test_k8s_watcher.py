"""FR-002 Kubernetes workload ingest tests."""

from __future__ import annotations

import json
from pathlib import Path

from starlette.testclient import TestClient

from raphael_agent.http_api.app import create_app
from raphael_agent.ingest.k8s_watcher import normalize_k8s_workload

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "k8s_workload_failure.json"


def test_normalize_k8s_workload():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seed = normalize_k8s_workload(payload, raw_ref="fixture:k8s")
    assert seed["trigger"]["kind"] == "k8s_workload"
    assert seed["correlation"]["workload"] == "payments-api"
    assert seed["delivery_mode"] == "draft_pr"
    assert seed["commit_sha"].startswith("abcdef")


def test_k8s_webhook_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RAPHAEL_K8S_WATCHER", raising=False)
    client = TestClient(create_app())
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    response = client.post("/v1/webhooks/k8s", json=payload)
    assert response.status_code == 202
    assert response.json()["decision"] == "ignored"


def test_k8s_webhook_accepts_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_K8S_WATCHER", "1")
    monkeypatch.setenv("RAPHAEL_INGEST_RUN_GRAPH", "0")
    client = TestClient(create_app())
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    response = client.post("/v1/webhooks/k8s", json=payload)
    assert response.status_code == 202
    body = response.json()
    assert body["ingest"]["decision"] == "accepted"
    assert body.get("run_id")
