"""Dispatch auth with identity-store connector credentials (rc_ bearer tokens)."""

import json
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from raphael_agent.identity import IdentityStore
from raphael_dispatch.app import create_app


def job(tenant: str) -> dict:
    job_id = str(uuid4())
    return {"protocol_version": "1.0", "message_id": str(uuid4()), "job_id": job_id,
            "kind": "job", "sent_at": "2026-11-18T00:00:00Z", "payload": {
                "job_id": job_id, "repository": {"clone_url": "https://example.com/a.git"},
                "commit_sha": "0123456789abcdef0123456789abcdef01234567",
                "narrowed_location": {"file_path": "deploy/app.yaml"}, "lease_ttl_seconds": 30}}


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_IDENTITY_DB", str(tmp_path / "identity.sqlite3"))
    monkeypatch.delenv("RAPHAEL_AUTH_SOURCE", raising=False)
    monkeypatch.delenv("RAPHAEL_ALLOW_INSECURE_LOCAL", raising=False)
    monkeypatch.setenv("RAPHAEL_DISPATCH_TOKENS", json.dumps({
        "producer-acme": {"tenant_id": "gh-100", "role": "producer"},
    }))
    store = IdentityStore()
    store.upsert_tenant("gh-100", installation_id=1, github_account_id=100, github_login="acme", account_type="Organization")
    store.upsert_tenant("gh-200", installation_id=2, github_account_id=200, github_login="solo", account_type="User")
    return TestClient(create_app()), store


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_issued_connector_claims_jobs_for_its_tenant(setup):
    client, store = setup
    _, token = store.create_connector("gh-100", label="cluster")
    assert client.post("/v1/tenants/gh-100/jobs", headers=bearer("producer-acme"), json=job("gh-100")).status_code == 202
    claimed = client.get("/v1/tenants/gh-100/jobs/next", headers=bearer(token))
    assert claimed.status_code == 200 and claimed.json()["pending"] is True


def test_connector_cannot_reach_another_tenant(setup):
    client, store = setup
    _, token = store.create_connector("gh-200")
    assert client.get("/v1/tenants/gh-100/jobs/next", headers=bearer(token)).status_code == 403


def test_connector_token_cannot_produce(setup):
    client, store = setup
    _, token = store.create_connector("gh-100")
    assert client.post("/v1/tenants/gh-100/jobs", headers=bearer(token), json=job("gh-100")).status_code == 403


def test_revoked_forged_and_disabled_credentials_are_rejected(setup):
    client, store = setup
    connector_id, revoked = store.create_connector("gh-100")
    store.revoke_connector("gh-100", connector_id)
    assert client.get("/v1/tenants/gh-100/jobs/next", headers=bearer(revoked)).status_code == 401
    assert client.get("/v1/tenants/gh-100/jobs/next", headers=bearer("rc_forged")).status_code == 401
    _, live = store.create_connector("gh-200")
    store.disable_tenant("gh-200")
    assert client.get("/v1/tenants/gh-200/jobs/next", headers=bearer(live)).status_code == 401


def test_db_mode_rejects_env_tokens_and_keeps_legacy_closed(setup, monkeypatch):
    client, store = setup
    monkeypatch.setenv("RAPHAEL_AUTH_SOURCE", "db")
    monkeypatch.setenv("RAPHAEL_ALLOW_INSECURE_LOCAL", "1")
    assert client.post("/v1/tenants/gh-100/jobs", headers=bearer("producer-acme"), json=job("gh-100")).status_code == 401
    _, token = store.create_connector("gh-100")
    assert client.get("/v1/tenants/gh-100/jobs/next", headers=bearer(token)).status_code == 200
    monkeypatch.delenv("RAPHAEL_DISPATCH_TOKENS")
    assert client.post("/v1/jobs", json=job("gh-100")).status_code == 403
