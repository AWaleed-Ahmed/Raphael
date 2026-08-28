import json
from uuid import uuid4

from starlette.testclient import TestClient

from raphael_dispatch.app import create_app


def job(tenant_seed: str) -> dict:
    job_id = str(uuid4())
    return {"protocol_version": "1.0", "message_id": str(uuid4()), "job_id": job_id,
            "kind": "job", "sent_at": "2026-08-28T00:00:00Z", "payload": {
                "job_id": job_id, "repository": {"clone_url": "https://example.com/a.git"},
                "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                "narrowed_location": {"file_path": "deploy/app.yaml"}, "lease_ttl_seconds": 30}}


def client(monkeypatch):
    monkeypatch.setenv("RAPHAEL_DISPATCH_TOKENS", json.dumps({
        "producer-a": {"tenant_id": "a", "role": "producer"},
        "connector-a": {"tenant_id": "a", "role": "connector"},
        "producer-b": {"tenant_id": "b", "role": "producer"},
        "connector-b": {"tenant_id": "b", "role": "connector"},
    }))
    return TestClient(create_app())


def test_role_and_cross_tenant_rejections(monkeypatch):
    c = client(monkeypatch)
    assert c.get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer producer-a"}).status_code == 403
    assert c.post("/v1/tenants/a/jobs", headers={"Authorization": "Bearer connector-a"}, json=job("a")).status_code == 403
    assert c.get("/v1/tenants/b/jobs/next", headers={"Authorization": "Bearer connector-a"}).status_code == 403


def test_two_tenant_isolation_and_claim(monkeypatch):
    c = client(monkeypatch)
    for tenant, token in (("a", "producer-a"), ("b", "producer-b")):
        response = c.post(f"/v1/tenants/{tenant}/jobs", headers={"Authorization": f"Bearer {token}"}, json=job(tenant))
        assert response.status_code == 202
    first = c.get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer connector-a"})
    assert first.status_code == 200 and first.json()["pending"] is True
    assert first.json()["messages"][0]["payload"]["job_id"]
    assert c.get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer connector-a"}).json()["pending"] is False
    second = c.get("/v1/tenants/b/jobs/next", headers={"Authorization": "Bearer connector-b"})
    assert second.status_code == 200 and second.json()["pending"] is True


def test_empty_queue_signal(monkeypatch):
    response = client(monkeypatch).get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer connector-a"})
    assert response.status_code == 200
    assert response.json() == {"messages": [], "pending": False}


def test_claim_is_released_after_lease_expiry(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/a/jobs", headers={"Authorization": "Bearer producer-a"}, json=job("a"))
    assert submitted.status_code == 202
    headers = {"Authorization": "Bearer connector-a"}
    assert c.get("/v1/tenants/a/jobs/next", headers=headers).json()["pending"] is True
    job_id = submitted.json()["job_id"]
    c.app.state.claimed_jobs[job_id]["claimed_at"] = "2000-01-01T00:00:00+00:00"
    assert c.get("/v1/tenants/a/jobs/next", headers=headers).json()["pending"] is True


def test_cross_tenant_result_rejected(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/b/jobs", headers={"Authorization": "Bearer producer-b"}, json=job("b"))
    job_id = submitted.json()["job_id"]
    action = c.get("/v1/tenants/b/jobs/next", headers={"Authorization": "Bearer connector-b"}).json()["messages"][0]
    result = {"protocol_version": "1.0", "message_id": str(uuid4()), "job_id": job_id, "kind": "result",
              "sent_at": "2026-08-28T00:00:00Z", "payload": {"job_id": job_id, "action_id": action["payload"]["action_id"],
              "verb": "create_sandbox", "status": "failed", "error": {"code": "x", "message": "x"}}}
    assert c.post("/v1/results", headers={"Authorization": "Bearer connector-a"}, json=result).status_code == 403
