"""Connector credential API: issue once, list without secrets, revoke, tenant isolation."""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from raphael_agent.http_api.app import MAX_ACTIVE_CONNECTORS, create_app
from raphael_agent.identity import IdentityStore


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    for name in ("RAPHAEL_IDENTITY_DB", "RAPHAEL_AUTH_SOURCE", "RAPHAEL_ALLOW_INSECURE_LOCAL",
                 "RAPHAEL_INTERFACE_TOKENS", "RAPHAEL_INTERFACE_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    store = IdentityStore()
    for tenant, inst, login in (("gh-100", 1, "acme"), ("gh-200", 2, "solo")):
        store.upsert_tenant(tenant, installation_id=inst, github_account_id=int(tenant[3:]),
                            github_login=login, account_type="Organization")
        store.set_tenant_repos(tenant, [f"{login}/app"])
    operator = store.create_session(7, "octo", {"gh-100": "operator"})
    reader = store.create_session(8, "viewer", {"gh-100": "reader"})
    other = store.create_session(9, "solo", {"gh-200": "operator"})
    return TestClient(create_app()), store, operator, reader, other


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_operator_creates_connector_and_sees_token_once(env):
    client, store, operator, *_ = env
    response = client.post("/v1/connectors", headers=auth(operator), json={"label": " laptop "})
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["token"].startswith("rc_") and body["tenant_id"] == "gh-100" and body["label"] == "laptop"
    assert store.connector_principal(body["token"])["connector_id"] == body["connector_id"]
    listed = client.get("/v1/connectors", headers=auth(operator)).json()["connectors"]
    assert [row["connector_id"] for row in listed] == [body["connector_id"]]
    assert body["token"] not in json.dumps(listed) and "token_sha256" not in json.dumps(listed)


def test_empty_body_is_allowed(env):
    client, _, operator, *_ = env
    assert client.post("/v1/connectors", headers=auth(operator)).status_code == 201


def test_reader_can_list_but_not_create_or_revoke(env):
    client, store, operator, reader, _ = env
    connector_id = client.post("/v1/connectors", headers=auth(operator)).json()["connector_id"]
    assert client.get("/v1/connectors", headers=auth(reader)).status_code == 200
    assert client.post("/v1/connectors", headers=auth(reader)).status_code == 403
    assert client.delete(f"/v1/connectors/{connector_id}", headers=auth(reader)).status_code == 403


def test_tenants_cannot_see_or_revoke_each_others_connectors(env):
    client, store, operator, _, other = env
    created = client.post("/v1/connectors", headers=auth(operator)).json()
    assert client.get("/v1/connectors", headers=auth(other)).json() == {"connectors": []}
    assert client.delete(f"/v1/connectors/{created['connector_id']}", headers=auth(other)).status_code == 404
    assert store.connector_principal(created["token"]) is not None


def test_revoke_disables_the_token(env):
    client, store, operator, *_ = env
    created = client.post("/v1/connectors", headers=auth(operator)).json()
    response = client.delete(f"/v1/connectors/{created['connector_id']}", headers=auth(operator))
    assert response.status_code == 200 and response.json() == {"connector_id": created["connector_id"], "revoked": True}
    assert store.connector_principal(created["token"]) is None
    assert client.delete(f"/v1/connectors/{created['connector_id']}", headers=auth(operator)).status_code == 404


def test_active_connector_cap(env):
    client, _, operator, *_ = env
    ids = [client.post("/v1/connectors", headers=auth(operator)).json()["connector_id"]
           for _ in range(MAX_ACTIVE_CONNECTORS)]
    assert client.post("/v1/connectors", headers=auth(operator)).status_code == 409
    client.delete(f"/v1/connectors/{ids[0]}", headers=auth(operator))
    assert client.post("/v1/connectors", headers=auth(operator)).status_code == 201


@pytest.mark.parametrize("body", [{"label": 5}, {"label": "x" * 65}, ["not", "an", "object"]])
def test_invalid_label_is_rejected(env, body):
    client, _, operator, *_ = env
    assert client.post("/v1/connectors", headers=auth(operator), json=body).status_code == 400


def test_unregistered_tenant_cannot_create(env, monkeypatch):
    client, *_ = env
    monkeypatch.setenv("RAPHAEL_INTERFACE_TOKENS", json.dumps(
        {"env-op": {"tenant_id": "not-installed", "role": "operator", "repositories": ["x/y"]}}
    ))
    assert client.post("/v1/connectors", headers=auth("env-op")).status_code == 409


def test_insecure_local_without_identity_is_refused(env, monkeypatch):
    client, *_ = env
    monkeypatch.setenv("RAPHAEL_ALLOW_INSECURE_LOCAL", "1")
    assert client.get("/v1/connectors").status_code == 403
    assert client.post("/v1/connectors").status_code == 403
