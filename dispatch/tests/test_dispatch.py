from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from starlette.testclient import TestClient

from raphael_dispatch.app import app
from raphael_dispatch.protocol import SCHEMA_FILES, choose_next_action, get_schemas


client = TestClient(app)


def envelope(kind: str, payload: dict, job_id: str | None = None) -> dict:
    return {
        "protocol_version": "1.0",
        "message_id": str(uuid4()),
        "job_id": job_id,
        "kind": kind,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }


def sample_job() -> dict:
    job_id = str(uuid4())
    return envelope(
        "job",
        {
            "job_id": job_id,
            "repository": {"clone_url": "https://github.com/example/service.git", "name": "service"},
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "narrowed_location": {"file_path": "deploy/deployment.yaml", "line_start": 12},
            "lease_ttl_seconds": 60,
        },
        job_id,
    )


def test_health_reports_loaded_contracts() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["contracts_version"] == "contracts-v1.0.0"
    assert body["schemas_loaded"] == sorted(SCHEMA_FILES)


def test_all_connector_v1_schemas_are_loaded() -> None:
    assert set(get_schemas().schemas) == set(SCHEMA_FILES)


def test_job_action_result_terminal_round_trip() -> None:
    job = sample_job()
    assert client.post("/v1/validate", json=job).json() == {"valid": True, "kind": "job"}

    action = choose_next_action(job)
    assert action["kind"] == "action"
    assert action["payload"]["verb"] == "observe_failure"
    assert client.post("/v1/validate", json=action).json() == {"valid": True, "kind": "action"}

    job_id = job["payload"]["job_id"]
    action_id = action["payload"]["action_id"]
    signature = {
        "class": "service_port_mismatch",
        "key": "probe_port_mismatch:service:8080!=9090",
        "normalized": {
            "reason": "probe_port_mismatch",
            "resource_kind": "Deployment",
            "resource_name": "service",
        },
        "reproduced": True,
        "evidence_refs": [{"kind": "artifact", "id": "artifact-1"}],
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    result = envelope(
        "result",
        {
            "job_id": job_id,
            "action_id": action_id,
            "verb": "observe_failure",
            "status": "ok",
            "result": {"sandbox_id": "sb-fake", "signature": signature, "artifact_ids": ["artifact-1"]},
        },
        job_id,
    )
    assert client.post("/v1/validate", json=result).json() == {"valid": True, "kind": "result"}

    terminal = envelope(
        "terminal",
        {"job_id": job_id, "final_status": "escalated", "instructions": "discard_local_copy"},
        job_id,
    )
    assert client.post("/v1/validate", json=terminal).json() == {"valid": True, "kind": "terminal"}


def test_unknown_verb_is_rejected() -> None:
    job = sample_job()
    action = choose_next_action(job)
    action["payload"]["verb"] = "run_shell"
    response = client.post("/v1/validate", json=action)
    assert response.status_code == 422
    assert response.json()["valid"] is False
