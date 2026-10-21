import pytest
from starlette.testclient import TestClient

from raphael_agent.sandbox_config import secret_fixture_args
from raphael_agent.store import RunStore
from raphael_dispatch.app import create_app
from raphael_dispatch.orchestrator import Orchestrator
from tests.test_orchestrator import job_envelope


@pytest.mark.parametrize("selection", ["", "payments-test"])
def test_fixture_selection_reaches_real_queue_and_survives_restart(tmp_path, monkeypatch, selection):
    import json
    monkeypatch.setenv("RAPHAEL_SECRET_FIXTURE_SET", selection)
    monkeypatch.setenv("RAPHAEL_DISPATCH_TOKENS", json.dumps({
        "p": {"tenant_id": "test", "role": "producer"},
        "c": {"tenant_id": "test", "role": "connector"},
    }))
    store = RunStore(tmp_path)
    job = job_envelope()
    expected = secret_fixture_args()
    with TestClient(create_app(Orchestrator(store=store))) as client:
        response = client.post("/v1/tenants/test/jobs", json=job,
                               headers={"Authorization": "Bearer p"})
        assert response.status_code == 202
    monkeypatch.setenv("RAPHAEL_SECRET_FIXTURE_SET", "different-set")
    with TestClient(create_app(Orchestrator(store=store))) as client:
        response = client.get("/v1/tenants/test/jobs/next", headers={"Authorization": "Bearer c"})
        assert response.status_code == 200
        action = response.json()["messages"][0]
        assert action["payload"]["verb"] == "create_sandbox"
        args = action["payload"]["args"]
        assert {k: v for k, v in args.items() if k == "secret_fixture_set"} == expected


@pytest.mark.parametrize("invalid", ["../secrets", "/etc/secrets", "a/b", "a\\b"])
def test_fixture_selection_rejects_paths(monkeypatch, invalid):
    monkeypatch.setenv("RAPHAEL_SECRET_FIXTURE_SET", invalid)
    with pytest.raises(ValueError, match="not a path"):
        secret_fixture_args()
