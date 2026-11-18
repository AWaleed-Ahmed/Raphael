"""Installation webhooks over HTTP, and DB-first webhook tenant scoping."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from starlette.testclient import TestClient

from raphael_agent.http_api.app import create_app
from raphael_agent.identity import IdentityStore
from raphael_agent.ingest.github import WebhookAuthError, github_scope

SECRET = "test-webhook-secret"


def created_payload() -> dict:
    return {
        "action": "created",
        "installation": {"id": 11, "account": {"id": 100, "login": "acme", "type": "Organization"}},
        "repositories": [{"full_name": "acme/api"}],
    }


def repo_payload(owner="acme", name="api", installation_id=11) -> dict:
    return {"installation": {"id": installation_id}, "repository": {"owner": {"login": owner}, "name": name}}


def post(client, event: str, payload: dict, secret: str | None = SECRET):
    body = json.dumps(payload).encode()
    headers = {"X-GitHub-Event": event, "X-GitHub-Delivery": "d-1", "Content-Type": "application/json"}
    if secret is not None:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/v1/webhooks/github", content=body, headers=headers)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_WEBHOOK_SECRET", SECRET)
    for name in ("RAPHAEL_IDENTITY_DB", "RAPHAEL_AUTH_SOURCE", "RAPHAEL_ALLOW_INSECURE_LOCAL",
                 "RAPHAEL_GITHUB_INSTALLATIONS"):
        monkeypatch.delenv(name, raising=False)
    return TestClient(create_app())


def test_signed_installation_created_records_tenant(client):
    response = post(client, "installation", created_payload())
    assert response.status_code == 202
    assert response.json()["decision"] == "tenant_active"
    assert IdentityStore().tenant_for_repo(11, "acme/api") == "gh-100"


def test_repository_event_updates_repos_over_http(client):
    post(client, "installation", created_payload())
    payload = {**created_payload(), "action": "added",
               "repositories_added": [{"full_name": "acme/jobs"}], "repositories_removed": []}
    assert post(client, "installation_repositories", payload).status_code == 202
    assert IdentityStore().tenant_for_repo(11, "acme/jobs") == "gh-100"


def test_bad_signature_is_rejected_before_any_write(client):
    response = post(client, "installation", created_payload(), secret="wrong")
    assert response.status_code == 401
    assert IdentityStore().tenant_for_repo(11, "acme/api") is None


def test_malformed_installation_payload_is_400(client):
    assert post(client, "installation", {"action": "created"}).status_code == 400


def test_recorded_installation_scopes_later_webhooks(client):
    post(client, "installation", created_payload())
    identity = github_scope(repo_payload())
    assert identity.tenant_id == "gh-100" and identity.repositories == ("acme/api",)


def test_unrecorded_repo_falls_back_to_env_mapping_outside_db_mode(client, monkeypatch):
    monkeypatch.setenv("RAPHAEL_GITHUB_INSTALLATIONS", json.dumps({"22": {"solo/app": {"tenant_id": "env-tenant"}}}))
    assert github_scope(repo_payload("solo", "app", 22)).tenant_id == "env-tenant"


def test_db_mode_ignores_env_mapping(client, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AUTH_SOURCE", "db")
    monkeypatch.setenv("RAPHAEL_GITHUB_INSTALLATIONS", json.dumps({"22": {"solo/app": {"tenant_id": "env-tenant"}}}))
    with pytest.raises(WebhookAuthError):
        github_scope(repo_payload("solo", "app", 22))


def test_db_mode_requires_a_webhook_secret_even_when_insecure_local(client, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AUTH_SOURCE", "db")
    monkeypatch.setenv("RAPHAEL_ALLOW_INSECURE_LOCAL", "1")
    monkeypatch.delenv("RAPHAEL_GITHUB_WEBHOOK_SECRET")
    assert post(client, "installation", created_payload(), secret=None).status_code == 401
    assert IdentityStore().tenant_for_repo(11, "acme/api") is None
