from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from starlette.testclient import TestClient

from raphael_agent.store import RunStore
from raphael_dispatch.orchestrator import Orchestrator


ROOT = Path(__file__).resolve().parents[2]


def _load_combined_factory():
    """Load the production run.py factory rather than reconstructing its routes in the test."""
    name = "raphael_combined_app_under_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, ROOT / "run.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.create_app


def _job(*, lease_ttl_seconds: int = 30) -> dict:
    job_id = str(uuid4())
    return {
        "protocol_version": "1.0",
        "message_id": str(uuid4()),
        "job_id": job_id,
        "kind": "job",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "job_id": job_id,
            "repository": {"clone_url": "https://github.com/example/service.git", "name": "service"},
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "narrowed_location": {"file_path": "deploy/deployment.yaml"},
            "lease_ttl_seconds": lease_ttl_seconds,
        },
    }


def test_combined_run_app_rehydrates_and_reaps_automatically(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_LEASE_REAP_INTERVAL_SECONDS", "0.1")
    monkeypatch.setenv(
        "RAPHAEL_DISPATCH_TOKENS",
        json.dumps(
            {
                "producer-a": {"tenant_id": "tenant-a", "role": "producer"},
                "connector-a": {"tenant_id": "tenant-a", "role": "connector"},
                "producer-b": {"tenant_id": "tenant-b", "role": "producer"},
                "connector-b": {"tenant_id": "tenant-b", "role": "connector"},
            }
        ),
    )
    headers_a = {"Authorization": "Bearer connector-a"}
    headers_b = {"Authorization": "Bearer connector-b"}

    # Seed a persisted job before the production app is constructed.  The app's
    # lifespan must rehydrate it before the first connector poll can succeed.
    seeded = Orchestrator(store=RunStore(tmp_path))
    restored_job = _job(lease_ttl_seconds=60)
    restored_action = seeded.intake(restored_job, tenant_id="tenant-a")["messages"][0]

    combined = _load_combined_factory()()
    with TestClient(combined) as client:
        restored = client.get("/v1/tenants/tenant-a/jobs/next", headers=headers_a)
        assert restored.status_code == 200
        assert restored.json() == {"messages": [restored_action], "pending": True}

        # Submit through the actual combined route, make its lease expired, and
        # wait for the lifespan task.  No manual /v1/leases/reap call is made.
        expiring_job = _job(lease_ttl_seconds=30)
        submitted = client.post(
            "/v1/tenants/tenant-b/jobs",
            headers={"Authorization": "Bearer producer-b"},
            json=expiring_job,
        )
        assert submitted.status_code == 202
        state = combined.state.orchestrator.jobs[expiring_job["payload"]["job_id"]]
        state["dispatch"]["last_activity_at"] = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
        combined.state.orchestrator._save(state)

        time.sleep(0.25)

        assert state["dispatch"]["stage"] == "terminal"
        assert state["status"] == "failed_closed"
        assert state["terminal_reason"] == "job_lease_expired"
        assert client.get("/v1/tenants/tenant-b/jobs/next", headers=headers_b).json() == {
            "messages": [],
            "pending": False,
        }
