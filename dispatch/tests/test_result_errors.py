"""Auth failures remain distinct from wire validation and result conflicts."""
import copy
import json

import pytest
from starlette.testclient import TestClient

from raphael_agent.store import RunStore
from raphael_dispatch.app import create_app
from raphael_dispatch.orchestrator import Orchestrator
from tests.test_orchestrator import job_envelope, result_for, create_result


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_DISPATCH_TOKENS", json.dumps({
        "connector": {"role": "connector", "tenant_id": "test"},
        "producer": {"role": "producer", "tenant_id": "test"},
        "other": {"role": "connector", "tenant_id": "other"},
    }))
    return TestClient(create_app(Orchestrator(store=RunStore(tmp_path))))


def headers(token="connector"):
    return {"Authorization": f"Bearer {token}"}


def pending_result(client):
    job = job_envelope()
    assert client.post("/v1/tenants/test/jobs", headers=headers("producer"), json=job).status_code == 202
    action = client.get("/v1/tenants/test/jobs/next", headers=headers()).json()["messages"][0]
    result = create_result(job["job_id"])
    result["cluster_backend"] = "kubectl"
    return result_for(action, result=result)


@pytest.mark.parametrize("body", ['{', '[]', '{"payload": null}', '{"payload": []}'])
def test_malformed_result_is_validation_error(client, body):
    response = client.post("/v1/results", headers=headers(), content=body)
    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert response.json()["error"]
    assert client.app.state.orchestrator.jobs == {}


@pytest.mark.parametrize("token,status", [(None, 401), ("invalid", 401), ("producer", 403)])
def test_authentication_precedes_validation(client, token, status):
    response = client.post("/v1/results", headers=headers(token) if token else {}, content='{')
    assert response.status_code == status
    assert response.json()["valid"] is False


def test_real_backend_result_and_conflicting_replay(client):
    result = pending_result(client)
    assert client.post("/v1/results", headers=headers("other"), json=result).status_code == 403
    response = client.post("/v1/results", headers=headers(), json=result)
    assert response.status_code == 200, response.text
    assert response.json()["messages"][0]["payload"]["verb"] == "deploy_revision"
    assert client.post("/v1/results", headers=headers(), json=result).json()["idempotent_replay"] is True
    conflict = copy.deepcopy(result)
    conflict["payload"]["result"]["namespace"] = "different-namespace"
    response = client.post("/v1/results", headers=headers(), json=conflict)
    assert response.status_code == 422
    assert response.json() == {"valid": False, "error": "action_id replayed with a different result payload"}


def test_invalid_backend_result_does_not_advance_job(client):
    result = pending_result(client)
    result["payload"]["result"]["cluster_backend"] = "unsupported-backend"
    response = client.post("/v1/results", headers=headers(), json=result)
    assert response.status_code == 422
    assert response.json()["valid"] is False
    assert "cluster_backend" in response.json()["error"]
    state = client.app.state.orchestrator.jobs[result["job_id"]]
    assert state["dispatch"]["pending_action"]["payload"]["action_id"] == result["payload"]["action_id"]
