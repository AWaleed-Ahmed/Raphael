"""GitHub App login: state, code exchange on core, role mapping, sessions."""

from __future__ import annotations

import importlib

import httpx
import pytest
from starlette.testclient import TestClient

import raphael_agent.github_oauth as github_oauth
from raphael_agent.http_api.app import create_app

# The http_api package exports a Starlette `app`, which shadows the module name.
app_module = importlib.import_module("raphael_agent.http_api.app")
from raphael_agent.identity import IdentityStore
from raphael_agent.store import open_run_store

USER_TOKEN = "gho_user_secret_token"
REAL_CLIENT = httpx.Client


def github(*, org_role="admin", membership_status=200, exchange_ok=True):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/login/oauth/access_token":
            if not exchange_ok:
                return httpx.Response(200, json={"error": "bad_verification_code"})
            assert b"client_secret=app-secret" in request.content
            return httpx.Response(200, json={"access_token": USER_TOKEN, "token_type": "bearer"})
        assert request.headers["authorization"] == f"Bearer {USER_TOKEN}"
        if path == "/user":
            return httpx.Response(200, json={"id": 7, "login": "octo"})
        if path == "/user/installations":
            return httpx.Response(200, json={"installations": [
                {"id": 3, "account": {"id": 7, "login": "octo", "type": "User"}},
                {"id": 1, "account": {"id": 100, "login": "acme", "type": "Organization"}},
                {"id": 9, "account": {"id": 900, "login": "elsewhere", "type": "Organization"}},
            ]})
        if path == "/user/memberships/orgs/acme":
            return httpx.Response(membership_status, json={"role": org_role, "state": "active"})
        return httpx.Response(404)
    return handler


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_GITHUB_APP_CLIENT_ID", "Iv1.app")
    monkeypatch.setenv("RAPHAEL_GITHUB_APP_CLIENT_SECRET", "app-secret")
    monkeypatch.setenv("RAPHAEL_GITHUB_OAUTH_REDIRECT_URI", "https://raphael.example/auth/callback")
    for name in ("RAPHAEL_IDENTITY_DB", "RAPHAEL_AUTH_SOURCE", "RAPHAEL_ALLOW_INSECURE_LOCAL",
                 "RAPHAEL_INTERFACE_TOKENS", "RAPHAEL_INTERFACE_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(app_module, "_auth_hits", {})
    store = IdentityStore()
    store.upsert_tenant("gh-7", installation_id=3, github_account_id=7, github_login="octo", account_type="User")
    store.set_tenant_repos("gh-7", ["octo/site"])
    store.upsert_tenant("gh-100", installation_id=1, github_account_id=100, github_login="acme", account_type="Organization")
    store.set_tenant_repos("gh-100", ["acme/api"])
    return TestClient(create_app()), store


def mock_github(monkeypatch, handler):
    monkeypatch.setattr(github_oauth.httpx, "Client",
                        lambda **kwargs: REAL_CLIENT(**kwargs, transport=httpx.MockTransport(handler)))


def login(client):
    start = client.get("/v1/auth/github/start").json()
    return client.post("/v1/auth/github/callback", json={"code": "the-code", "state": start["state"]})


def test_start_requires_configuration(env, monkeypatch):
    client, _ = env
    monkeypatch.delenv("RAPHAEL_GITHUB_APP_CLIENT_SECRET")
    assert client.get("/v1/auth/github/start").status_code == 503


def test_start_returns_authorize_url_with_state(env):
    client, _ = env
    response = client.get("/v1/auth/github/start")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    url = httpx.URL(body["authorize_url"])
    assert url.host == "github.com" and url.path == "/login/oauth/authorize"
    assert url.params["client_id"] == "Iv1.app" and url.params["state"] == body["state"]
    assert url.params["redirect_uri"] == "https://raphael.example/auth/callback"


def test_login_maps_installations_to_roles(env, monkeypatch):
    client, _ = env
    mock_github(monkeypatch, github(org_role="admin"))
    response = login(client)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["session_token"].startswith("rs_") and body["github_login"] == "octo"
    assert {t["tenant_id"]: t["role"] for t in body["tenants"]} == {"gh-7": "operator", "gh-100": "operator"}


@pytest.mark.parametrize("org_role,status", [("member", 200), ("admin", 500)])
def test_non_admin_or_unknown_membership_is_reader(env, monkeypatch, org_role, status):
    client, _ = env
    mock_github(monkeypatch, github(org_role=org_role, membership_status=status))
    roles = {t["tenant_id"]: t["role"] for t in login(client).json()["tenants"]}
    assert roles == {"gh-7": "operator", "gh-100": "reader"}


def test_session_from_login_reaches_scoped_api(env, monkeypatch):
    client, _ = env
    mock_github(monkeypatch, github())
    token = login(client).json()["session_token"]
    open_run_store().save_run({"run_id": "r1", "tenant_id": "gh-100", "repository": {"owner": "acme", "name": "api"},
                               "commit_sha": "a" * 40, "status": "running"})
    me = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and len(me.json()["tenants"]) == 2
    runs = client.get("/v1/runs", headers={"Authorization": f"Bearer {token}", "X-Raphael-Tenant": "gh-100"})
    assert runs.status_code == 200 and [r["run_id"] for r in runs.json()["runs"]] == ["r1"]


def test_state_is_single_use_and_must_be_known(env, monkeypatch):
    client, _ = env
    mock_github(monkeypatch, github())
    state = client.get("/v1/auth/github/start").json()["state"]
    assert client.post("/v1/auth/github/callback", json={"code": "c", "state": state}).status_code == 200
    assert client.post("/v1/auth/github/callback", json={"code": "c", "state": state}).status_code == 400
    assert client.post("/v1/auth/github/callback", json={"code": "c", "state": "forged"}).status_code == 400
    assert client.post("/v1/auth/github/callback", json={"state": state}).status_code == 400


def test_failed_code_exchange_creates_no_session(env, monkeypatch):
    client, store = env
    mock_github(monkeypatch, github(exchange_ok=False))
    response = login(client)
    assert response.status_code == 502 and response.json()["error"]["message"] == "login failed"
    import sqlite3
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_github_user_token_is_never_stored(env, monkeypatch):
    client, store = env
    mock_github(monkeypatch, github())
    session = login(client).json()["session_token"]
    raw = store.path.read_bytes()
    assert USER_TOKEN.encode() not in raw and session.encode() not in raw


def test_logout_revokes_the_session(env, monkeypatch):
    client, _ = env
    mock_github(monkeypatch, github())
    headers = {"Authorization": f"Bearer {login(client).json()['session_token']}"}
    assert client.post("/v1/auth/logout", headers=headers).json() == {"logged_out": True}
    assert client.get("/v1/me", headers=headers).status_code == 401
    assert client.post("/v1/auth/logout", headers={"Authorization": "Bearer env-token"}).status_code == 401
    assert client.get("/v1/me").status_code == 401


def test_auth_endpoints_are_rate_limited(env, monkeypatch):
    client, _ = env
    monkeypatch.setattr(app_module, "AUTH_RATE_LIMIT", 3)
    codes = [client.get("/v1/auth/github/start").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
