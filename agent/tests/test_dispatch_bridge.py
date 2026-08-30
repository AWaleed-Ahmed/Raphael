"""Tests for the ingest→dispatch bridge (RAPHAEL_DISPATCH_BRIDGE_ENABLED)."""

from __future__ import annotations

import json
import os
import uuid

import pytest

from raphael_agent.ingest.dispatch_bridge import (
    build_job_envelope,
    bridge_enabled,
    submit_to_dispatch,
)


def _make_seed(*, clone_url: str | None = "https://github.com/test/repo.git", commit_sha: str = "abc1234") -> dict:
    return {
        "run_id": "ghw-12345",
        "tenant_id": "test-tenant",
        "trigger": {"kind": "github_workflow_run", "received_at": "2026-08-30T00:00:00Z"},
        "repository": {"owner": "test", "name": "repo", "clone_url": clone_url} if clone_url else {"owner": "test", "name": "repo"},
        "commit_sha": commit_sha,
        "correlation": {"deployment_config_path": None},
    }


class TestBridgeEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", raising=False)
        assert not bridge_enabled()

    def test_enabled_with_1(self, monkeypatch):
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "1")
        assert bridge_enabled()

    def test_enabled_with_true(self, monkeypatch):
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "true")
        assert bridge_enabled()

    def test_disabled_with_0(self, monkeypatch):
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "0")
        assert not bridge_enabled()


class TestBuildJobEnvelope:
    def test_valid_seed_produces_valid_envelope(self):
        seed = _make_seed()
        envelope = build_job_envelope(seed)
        assert envelope is not None
        assert envelope["protocol_version"] == "1.0"
        assert envelope["kind"] == "job"
        # job_id must be a valid UUID
        job_id = envelope["payload"]["job_id"]
        uuid.UUID(job_id)  # raises if invalid
        assert envelope["payload"]["repository"]["clone_url"] == "https://github.com/test/repo.git"
        assert envelope["payload"]["commit_sha"] == "abc1234"
        assert envelope["payload"]["narrowed_location"]["file_path"] == "."

    def test_missing_clone_url_returns_none(self):
        seed = _make_seed(clone_url=None)
        assert build_job_envelope(seed) is None

    def test_missing_commit_sha_returns_none(self):
        seed = _make_seed()
        seed["commit_sha"] = None
        assert build_job_envelope(seed) is None

    def test_correlation_config_path_used_as_file_path(self):
        seed = _make_seed()
        seed["correlation"]["deployment_config_path"] = "deploy/app.yaml"
        envelope = build_job_envelope(seed)
        assert envelope["payload"]["narrowed_location"]["file_path"] == "deploy/app.yaml"
        assert seed["_bridge_metadata"]["narrowed_location_source"] == "correlation"

    def test_default_file_path_when_no_correlation(self):
        seed = _make_seed()
        envelope = build_job_envelope(seed)
        assert envelope["payload"]["narrowed_location"]["file_path"] == "."
        assert seed["_bridge_metadata"]["narrowed_location_source"] == "default"

    def test_custom_default_file_path(self, monkeypatch):
        monkeypatch.setenv("RAPHAEL_BRIDGE_DEFAULT_FILE_PATH", "k8s/")
        seed = _make_seed()
        envelope = build_job_envelope(seed)
        assert envelope["payload"]["narrowed_location"]["file_path"] == "k8s/"

    def test_job_id_differs_from_run_id(self):
        seed = _make_seed()
        envelope = build_job_envelope(seed)
        assert envelope["payload"]["job_id"] != seed["run_id"]
        assert seed["_bridge_metadata"]["dispatch_job_id"] == envelope["payload"]["job_id"]

    def test_each_call_generates_unique_job_id(self):
        seed = _make_seed()
        e1 = build_job_envelope(seed)
        seed2 = _make_seed()
        e2 = build_job_envelope(seed2)
        assert e1["payload"]["job_id"] != e2["payload"]["job_id"]


class TestSubmitToDispatch:
    def test_successful_submission(self, monkeypatch):
        """Bridge submits to orchestrator.intake() and job appears in tenant queue."""
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "1")

        # Reset the singleton so we get a fresh orchestrator
        import raphael_agent.ingest.dispatch_bridge as bridge_mod
        bridge_mod._orchestrator_instance = None

        seed = _make_seed()
        run = {"run_id": seed["run_id"], "status": "pending"}
        result = submit_to_dispatch(seed, run)

        assert result["submitted"] is True
        assert "dispatch_job_id" in result
        assert run["dispatch_job_id"] == result["dispatch_job_id"]
        assert run["narrowed_location_source"] == "default"

        # Verify job is in the orchestrator's tenant queue
        orch = bridge_mod._orchestrator_instance
        jobs = orch.tenant_jobs("test-tenant")
        assert len(jobs) == 1
        assert jobs[0]["run_id"] == result["dispatch_job_id"]

    def test_missing_clone_url_skips_gracefully(self):
        seed = _make_seed(clone_url=None)
        run = {"run_id": seed["run_id"], "status": "pending"}
        result = submit_to_dispatch(seed, run)

        assert result["submitted"] is False
        assert "missing" in result["reason"]
        assert "clone_url" in result["reason"]
        # run should NOT have dispatch_job_id set
        assert "dispatch_job_id" not in run

    def test_bridge_error_does_not_raise(self, monkeypatch):
        """If orchestrator.intake raises, submit_to_dispatch returns submitted=False."""
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "1")

        import raphael_agent.ingest.dispatch_bridge as bridge_mod

        # Inject a broken orchestrator
        class BrokenOrchestrator:
            def intake(self, *a, **kw):
                raise RuntimeError("simulated failure")

        bridge_mod._orchestrator_instance = BrokenOrchestrator()

        seed = _make_seed()
        run = {"run_id": seed["run_id"], "status": "pending"}
        result = submit_to_dispatch(seed, run)

        assert result["submitted"] is False
        assert "bridge_error" in result["reason"]
        assert "simulated failure" in result["reason"]

        # Clean up
        bridge_mod._orchestrator_instance = None


class TestPrecedenceRule:
    """When bridge is enabled AND stub graph is enabled, bridge takes precedence."""

    def test_bridge_enabled_suppresses_stub_graph(self, monkeypatch):
        """Confirm that when bridge succeeds, the stub graph is NOT invoked."""
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "1")
        monkeypatch.setenv("RAPHAEL_INGEST_RUN_GRAPH", "1")
        monkeypatch.setenv("RAPHAEL_INGEST_MAX_CONCURRENT_RUNS", "100")
        monkeypatch.setenv("RAPHAEL_AGENT_TENANT_ID", "bridge-test-1")

        import raphael_agent.ingest.dispatch_bridge as bridge_mod
        bridge_mod._orchestrator_instance = None

        stub_graph_called = []

        def fake_stub_graph(run):
            stub_graph_called.append(True)
            return run

        monkeypatch.setattr("raphael_agent.graph.run_stub_graph", fake_stub_graph)

        from starlette.testclient import TestClient
        from raphael_agent.http_api.app import app

        client = TestClient(app)

        # Craft a minimal workflow_run webhook payload matching real GitHub format
        wf_id = str(uuid.uuid4().int % 10**12)
        sha = uuid.uuid4().hex[:40]
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": int(wf_id),
                "name": f"CI-bridge-{wf_id}",
                "conclusion": "failure",
                "head_sha": sha,
                "head_branch": "main",
            },
            "repository": {
                "owner": {"login": "test"},
                "name": "repo",
                "clone_url": "https://github.com/test/repo.git",
            },
        }

        response = client.post(
            "/v1/webhooks/github",
            json=payload,
            headers={"x-github-event": "workflow_run", "x-github-delivery": "test-delivery-1"},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        body = response.json()
        # Bridge should have submitted
        assert "dispatch_job_id" in body, f"No dispatch_job_id in: {body}"
        # Stub graph should NOT have been called
        assert len(stub_graph_called) == 0

    def test_bridge_disabled_allows_stub_graph(self, monkeypatch):
        """When bridge is disabled, stub graph runs normally."""
        monkeypatch.delenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", raising=False)
        monkeypatch.setenv("RAPHAEL_INGEST_RUN_GRAPH", "1")
        monkeypatch.setenv("RAPHAEL_INGEST_MAX_CONCURRENT_RUNS", "100")
        monkeypatch.setenv("RAPHAEL_AGENT_TENANT_ID", "bridge-test-2")

        stub_graph_called = []

        def fake_stub_graph(run):
            stub_graph_called.append(True)
            return run

        monkeypatch.setattr("raphael_agent.graph.run_stub_graph", fake_stub_graph)

        from starlette.testclient import TestClient
        from raphael_agent.http_api.app import app

        client = TestClient(app)

        wf_id = str(uuid.uuid4().int % 10**12)
        sha = uuid.uuid4().hex[:40]
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": int(wf_id),
                "name": f"CI-nobridge-{wf_id}",
                "conclusion": "failure",
                "head_sha": sha,
                "head_branch": "main",
            },
            "repository": {
                "owner": {"login": "test"},
                "name": "repo",
                "clone_url": "https://github.com/test/repo.git",
            },
        }

        response = client.post(
            "/v1/webhooks/github",
            json=payload,
            headers={"x-github-event": "workflow_run", "x-github-delivery": f"test-delivery-nobridge-{wf_id}"},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        # Stub graph SHOULD have been called
        assert len(stub_graph_called) == 1

    def test_bridge_skip_falls_back_to_stub_graph(self, monkeypatch):
        """When bridge is enabled but skips (missing clone_url), stub graph still runs."""
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "1")
        monkeypatch.setenv("RAPHAEL_INGEST_RUN_GRAPH", "1")
        monkeypatch.setenv("RAPHAEL_INGEST_MAX_CONCURRENT_RUNS", "100")
        monkeypatch.setenv("RAPHAEL_AGENT_TENANT_ID", "bridge-test-3")

        stub_graph_called = []

        def fake_stub_graph(run):
            stub_graph_called.append(True)
            return run

        monkeypatch.setattr("raphael_agent.graph.run_stub_graph", fake_stub_graph)

        from starlette.testclient import TestClient
        from raphael_agent.http_api.app import app

        client = TestClient(app)

        # Payload WITHOUT clone_url — bridge will skip
        wf_id = str(uuid.uuid4().int % 10**12)
        sha = uuid.uuid4().hex[:40]
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": int(wf_id),
                "name": f"CI-noclone-{wf_id}",
                "conclusion": "failure",
                "head_sha": sha,
                "head_branch": "main",
            },
            "repository": {
                "owner": {"login": "test"},
                "name": "repo",
                # no clone_url
            },
        }

        response = client.post(
            "/v1/webhooks/github",
            json=payload,
            headers={"x-github-event": "workflow_run", "x-github-delivery": f"test-delivery-noclone-{wf_id}"},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        body = response.json()
        # Bridge should NOT have submitted
        assert "dispatch_job_id" not in body
        # Stub graph SHOULD have been called as fallback
        assert len(stub_graph_called) == 1


class TestRealWebhookPayload:
    """Validate bridge against a real GitHub Actions workflow_run failure payload."""

    def test_real_github_payload_bridges_correctly(self, monkeypatch):
        """Real workflow_run payload from GitHub bridges to dispatch with correct fields."""
        monkeypatch.setenv("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "1")
        monkeypatch.delenv("RAPHAEL_INGEST_RUN_GRAPH", raising=False)
        monkeypatch.setenv("RAPHAEL_AGENT_TENANT_ID", f"real-payload-{uuid.uuid4().hex[:8]}")
        monkeypatch.setenv("RAPHAEL_INGEST_MAX_CONCURRENT_RUNS", "100")

        import raphael_agent.ingest.dispatch_bridge as bridge_mod
        bridge_mod._orchestrator_instance = None

        from pathlib import Path
        fixture = Path(__file__).parent / "fixtures" / "real_workflow_run_failure.json"
        with open(fixture) as f:
            payload = json.load(f)

        from starlette.testclient import TestClient
        from raphael_agent.http_api.app import app

        client = TestClient(app)
        response = client.post(
            "/v1/webhooks/github",
            json=payload,
            headers={
                "x-github-event": "workflow_run",
                "x-github-delivery": "real-payload-test-delivery",
            },
        )

        assert response.status_code == 202, f"Got {response.status_code}: {response.json()}"
        body = response.json()

        # Bridge should have submitted
        assert "dispatch_job_id" in body, f"No dispatch_job_id: {body}"
        dispatch_job_id = body["dispatch_job_id"]
        uuid.UUID(dispatch_job_id)  # valid UUID

        # run_id should be derived from workflow_run.id, NOT the dispatch job_id
        assert body["run_id"] == "ghw-33334546362"
        assert dispatch_job_id != body["run_id"]

        # Verify job in dispatch queue has correct fields
        orch = bridge_mod._orchestrator_instance
        tenant_id = os.environ["RAPHAEL_AGENT_TENANT_ID"]
        jobs = orch.tenant_jobs(tenant_id)
        assert len(jobs) == 1
        job = jobs[0]
        assert job["run_id"] == dispatch_job_id
        assert job["commit_sha"] == "d6e85236104e8222240c0d88edd5a83fee7f967a"
        assert job["repository"]["clone_url"] == "https://github.com/AmazingDude/raphael-e2e-fixture.git"
        # narrowed_location should be the default placeholder (no deployment_config_path in this event)
        assert job["narrowed_location"]["file_path"] == "."
