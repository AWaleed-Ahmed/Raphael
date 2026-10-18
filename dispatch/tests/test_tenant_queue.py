import json
from uuid import uuid4
from datetime import datetime, timedelta, timezone

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
        "connector-a2": {"tenant_id": "a", "role": "connector"},
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
    replay = c.get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer connector-a"}).json()
    assert replay["pending"] is True
    assert replay["claim"] == first.json()["claim"]
    assert replay["messages"] == first.json()["messages"]
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
    claim = c.app.state.orchestrator.jobs[job_id]["dispatch"]["claim"]
    claim["lease_expires_at"] = "2000-01-01T00:00:00+00:00"
    response = c.get("/v1/tenants/a/jobs/next", headers=headers)
    assert response.json() == {"messages": [], "pending": False}
    assert c.app.state.orchestrator.jobs[job_id]["dispatch"]["stage"] == "terminal"


def test_claim_is_not_disclosed_to_a_second_connector(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/a/jobs", headers={"Authorization": "Bearer producer-a"}, json=job("a"))
    job_id = submitted.json()["job_id"]
    first = c.get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer connector-a"})
    second = c.get("/v1/tenants/a/jobs/next", headers={"Authorization": "Bearer connector-a2"})
    assert first.json()["claim"]["action_id"] == first.json()["messages"][0]["payload"]["action_id"]
    assert second.json() == {"messages": [], "pending": False}
    assert "connector_id" not in first.json()["claim"]
    action = first.json()["messages"][0]["payload"]
    wrong_owner = {"Authorization": "Bearer connector-a2"}
    renewal = {key: first.json()["claim"][key] for key in ("action_id", "claim_id")}
    renewal["renewal_sequence"] = 1
    assert c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=wrong_owner, json=renewal).status_code == 409
    result = {
        "protocol_version": "1.0", "message_id": str(uuid4()), "job_id": job_id,
        "kind": "result", "sent_at": "2026-10-13T00:00:00Z",
        "payload": {"job_id": job_id, "action_id": action["action_id"], "verb": action["verb"],
                    "status": "failed", "error": {"code": "forged", "message": "wrong connector"}},
    }
    assert c.post("/v1/results", headers=wrong_owner, json=result).status_code == 422
    assert c.app.state.orchestrator.jobs[job_id]["dispatch"]["pending_action"]["payload"]["action_id"] == action["action_id"]


def test_malformed_lease_request_returns_422(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/a/jobs", headers={"Authorization": "Bearer producer-a"}, json=job("a"))
    job_id = submitted.json()["job_id"]
    headers = {"Authorization": "Bearer connector-a", "content-type": "application/json"}
    for body in (b"[1]", b"{"):
        response = c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=headers, content=body)
        assert response.status_code == 422


def test_lease_renewal_is_claim_bound_monotonic_and_idempotent(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/a/jobs", headers={"Authorization": "Bearer producer-a"}, json=job("a"))
    job_id = submitted.json()["job_id"]
    headers = {"Authorization": "Bearer connector-a"}
    response = c.get("/v1/tenants/a/jobs/next", headers=headers)
    action = response.json()["messages"][0]["payload"]
    claim = response.json()["claim"]
    now = datetime.now(timezone.utc)
    c.app.state.orchestrator.clock = lambda: now
    body = {"action_id": action["action_id"], "claim_id": claim["claim_id"], "renewal_sequence": 1}
    renewed = c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=headers, json=body)
    assert renewed.status_code == 200
    expiry = renewed.json()["lease_expires_at"]
    assert c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=headers, json=body).json()["lease_expires_at"] == expiry
    stale = {**body, "renewal_sequence": 3}
    assert c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=headers, json=stale).status_code == 409
    assert c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers={"Authorization": "Bearer connector-b"}, json=body).status_code == 403
    assert c.post(f"/v1/tenants/b/jobs/{job_id}/lease", headers=headers, json=body).status_code == 403
    assert c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=headers, json={**body, "claim_id": str(uuid4())}).status_code == 409
    assert datetime.fromisoformat(expiry.replace("Z", "+00:00")) <= now + timedelta(seconds=30)


def test_expired_claim_terminalizes_before_late_result(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/a/jobs", headers={"Authorization": "Bearer producer-a"}, json=job("a"))
    job_id = submitted.json()["job_id"]
    headers = {"Authorization": "Bearer connector-a"}
    response = c.get("/v1/tenants/a/jobs/next", headers=headers).json()
    action = response["messages"][0]["payload"]
    claim = response["claim"]
    clock = [datetime.now(timezone.utc)]
    c.app.state.orchestrator.clock = lambda: clock[0]
    clock[0] += timedelta(seconds=31)
    request = {"action_id": action["action_id"], "claim_id": claim["claim_id"], "renewal_sequence": 1}
    assert c.post(f"/v1/tenants/a/jobs/{job_id}/lease", headers=headers, json=request).status_code == 409
    result = {
        "protocol_version": "1.0", "message_id": str(uuid4()), "job_id": job_id,
        "kind": "result", "sent_at": clock[0].isoformat(),
        "payload": {"job_id": job_id, "action_id": action["action_id"], "verb": action["verb"], "status": "failed",
                    "error": {"code": "late", "message": "late result"}},
    }
    assert c.post("/v1/results", headers=headers, json=result).status_code == 422
    assert c.app.state.orchestrator.jobs[job_id]["dispatch"]["stage"] == "terminal"


def test_cross_tenant_result_rejected(monkeypatch):
    c = client(monkeypatch)
    submitted = c.post("/v1/tenants/b/jobs", headers={"Authorization": "Bearer producer-b"}, json=job("b"))
    job_id = submitted.json()["job_id"]
    action = c.get("/v1/tenants/b/jobs/next", headers={"Authorization": "Bearer connector-b"}).json()["messages"][0]
    result = {"protocol_version": "1.0", "message_id": str(uuid4()), "job_id": job_id, "kind": "result",
              "sent_at": "2026-08-28T00:00:00Z", "payload": {"job_id": job_id, "action_id": action["payload"]["action_id"],
              "verb": "create_sandbox", "status": "failed", "error": {"code": "x", "message": "x"}}}
    assert c.post("/v1/results", headers={"Authorization": "Bearer connector-a"}, json=result).status_code == 403


def test_results_require_authentication_before_processing(monkeypatch):
    c = client(monkeypatch)
    response = c.post("/v1/results", json={"not": "a result envelope"})
    assert response.status_code == 401
    assert response.json() == {"valid": False, "error": "missing bearer token"}
