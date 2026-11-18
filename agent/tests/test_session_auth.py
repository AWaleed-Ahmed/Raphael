"""Interface API auth with identity-store sessions (rs_ bearer tokens)."""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from raphael_agent.http_api.app import create_app
from raphael_agent.identity import IdentityStore
from raphael_agent.store import open_run_store


def _run(run_id: str, tenant: str, owner: str, name: str) -> dict:
    return {
        "run_id": run_id,
        "tenant_id": tenant,
        "repository": {"owner": owner, "name": name},
        "commit_sha": "a" * 40,
        "status": "running",
        "created_at": "2026-11-18T00:00:00Z",
        "updated_at": "2026-11-18T00:00:00Z",
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("RAPHAEL_IDENTITY_DB", raising=False)
    monkeypatch.delenv("RAPHAEL_AUTH_SOURCE", raising=False)
    monkeypatch.delenv("RAPHAEL_INTERFACE_TOKENS", raising=False)
    monkeypatch.delenv("RAPHAEL_INTERFACE_TOKEN", raising=False)
    monkeypatch.delenv("RAPHAEL_ALLOW_INSECURE_LOCAL", raising=False)
    store = IdentityStore()
    store.upsert_tenant("gh-100", installation_id=1, github_account_id=100, github_login="acme", account_type="Organization")
    store.set_tenant_repos("gh-100", ["acme/api"])
    store.upsert_tenant("gh-200", installation_id=2, github_account_id=200, github_login="solo", account_type="User")
    store.set_tenant_repos("gh-200", ["solo/app"])
    runs = open_run_store()
    runs.save_run(_run("run-acme", "gh-100", "acme", "api"))
    runs.save_run(_run("run-acme-other-repo", "gh-100", "acme", "secret"))
    runs.save_run(_run("run-solo", "gh-200", "solo", "app"))
    return TestClient(create_app()), store


def _ids(response) -> set[str]:
    assert response.status_code == 200, response.text
    body = response.json()
    items = body.get("runs") or body.get("items") or []
    return {item["run_id"] for item in items}


def test_session_sees_only_its_tenant_and_repos(env):
    client, store = env
    token = store.create_session(7, "octo", {"gh-100": "operator"})
    response = client.get("/v1/runs", headers={"Authorization": f"Bearer {token}"})
    assert _ids(response) == {"run-acme"}


def test_tenant_header_selects_among_granted_tenants(env):
    client, store = env
    token = store.create_session(7, "octo", {"gh-100": "operator", "gh-200": "reader"})
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/v1/runs", headers=headers).status_code == 401  # ambiguous
    assert _ids(client.get("/v1/runs", headers={**headers, "X-Raphael-Tenant": "gh-200"})) == {"run-solo"}


def test_session_cannot_select_an_ungranted_tenant(env):
    client, store = env
    token = store.create_session(8, "solo", {"gh-200": "operator"})
    response = client.get("/v1/runs", headers={"Authorization": f"Bearer {token}", "X-Raphael-Tenant": "gh-100"})
    assert response.status_code == 401


def test_revoked_or_unknown_session_is_rejected(env):
    client, store = env
    token = store.create_session(7, "octo", {"gh-100": "operator"})
    store.revoke_session(token)
    assert client.get("/v1/runs", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/v1/runs", headers={"Authorization": "Bearer rs_forged"}).status_code == 401


def test_session_cannot_read_another_tenants_run(env):
    client, store = env
    token = store.create_session(7, "octo", {"gh-100": "operator"})
    response = client.get("/v1/runs/run-solo", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_env_tokens_still_work_without_db_mode(env, monkeypatch):
    client, _ = env
    monkeypatch.setenv("RAPHAEL_INTERFACE_TOKENS", json.dumps(
        {"env-token": {"tenant_id": "gh-200", "role": "reader", "repositories": ["solo/app"]}}
    ))
    assert _ids(client.get("/v1/runs", headers={"Authorization": "Bearer env-token"})) == {"run-solo"}


def test_db_mode_disables_env_tokens_and_insecure_local(env, monkeypatch):
    client, store = env
    monkeypatch.setenv("RAPHAEL_AUTH_SOURCE", "db")
    monkeypatch.setenv("RAPHAEL_ALLOW_INSECURE_LOCAL", "1")
    monkeypatch.setenv("RAPHAEL_INTERFACE_TOKENS", json.dumps(
        {"env-token": {"tenant_id": "gh-200", "role": "reader", "repositories": ["solo/app"]}}
    ))
    assert client.get("/v1/runs", headers={"Authorization": "Bearer env-token"}).status_code == 401
    assert client.get("/v1/runs").status_code == 401
    token = store.create_session(7, "octo", {"gh-100": "operator"})
    assert _ids(client.get("/v1/runs", headers={"Authorization": f"Bearer {token}"})) == {"run-acme"}
