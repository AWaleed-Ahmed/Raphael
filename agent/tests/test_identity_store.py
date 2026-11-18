"""Identity store: hashed credentials, expiry, revocation and tenant scoping."""

from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from raphael_agent import identity
from raphael_agent.identity import IdentityStore, token_hash


@pytest.fixture
def store(tmp_path):
    s = IdentityStore(tmp_path / "identity.sqlite3")
    s.upsert_tenant("gh-100", installation_id=1, github_account_id=100, github_login="acme", account_type="Organization")
    s.set_tenant_repos("gh-100", ["Acme/API", "acme/web"])
    s.upsert_tenant("gh-200", installation_id=2, github_account_id=200, github_login="solo", account_type="User")
    s.set_tenant_repos("gh-200", ["solo/app"])
    return s


def test_reads_do_not_create_the_database(tmp_path):
    s = IdentityStore(tmp_path / "missing.sqlite3")
    assert s.session_principal("rs_anything", None) is None
    assert s.connector_principal("rc_anything") is None
    s.revoke_session("rs_anything")
    assert s.revoke_connector("gh-100", "conn_x") is False
    assert not (tmp_path / "missing.sqlite3").exists()


def test_tokens_are_stored_only_as_hashes(store):
    session = store.create_session(7, "octo", {"gh-100": "operator"})
    _, connector = store.create_connector("gh-100", label="laptop")
    raw = store.path.read_bytes()
    assert session.encode() not in raw and connector.encode() not in raw
    with sqlite3.connect(store.path) as conn:
        hashes = {row[0] for row in conn.execute("SELECT token_sha256 FROM sessions UNION SELECT token_sha256 FROM connectors")}
    assert hashes == {token_hash(session), token_hash(connector)}


def test_session_principal_uses_tenant_repos_and_role(store):
    token = store.create_session(7, "octo", {"gh-100": "operator", "gh-200": "reader"})
    assert token.startswith("rs_")
    assert store.session_principal(token, "gh-100") == {
        "tenant_id": "gh-100", "role": "operator", "repositories": ["acme/api", "acme/web"],
    }
    assert store.session_principal(token, "gh-200")["role"] == "reader"


def test_session_requires_tenant_choice_when_it_grants_several(store):
    several = store.create_session(7, "octo", {"gh-100": "operator", "gh-200": "reader"})
    single = store.create_session(8, "solo", {"gh-200": "operator"})
    assert store.session_principal(several, None) is None
    assert store.session_principal(single, None)["tenant_id"] == "gh-200"


def test_session_cannot_reach_ungranted_tenant(store):
    token = store.create_session(7, "octo", {"gh-200": "reader"})
    assert store.session_principal(token, "gh-100") is None


def test_unknown_role_is_rejected(store):
    with pytest.raises(ValueError):
        store.create_session(7, "octo", {"gh-100": "admin"})


def test_revoked_and_expired_sessions_stop_working(store, monkeypatch):
    revoked = store.create_session(7, "octo", {"gh-100": "operator"})
    store.revoke_session(revoked)
    assert store.session_principal(revoked, "gh-100") is None

    monkeypatch.setattr(identity, "SESSION_TTL", timedelta(seconds=-1))
    expired = store.create_session(7, "octo", {"gh-100": "operator"})
    assert store.session_principal(expired, "gh-100") is None


def test_tenant_without_repos_grants_nothing(store):
    store.set_tenant_repos("gh-200", [])
    token = store.create_session(8, "solo", {"gh-200": "operator"})
    assert store.session_principal(token, "gh-200") is None


def test_connector_lifecycle(store):
    connector_id, token = store.create_connector("gh-100", label="cluster-a", created_by=7)
    assert token.startswith("rc_")
    assert store.connector_principal(token) == {"tenant_id": "gh-100", "connector_id": connector_id}
    assert store.revoke_connector("gh-200", connector_id) is False  # wrong tenant
    assert store.revoke_connector("gh-100", connector_id) is True
    assert store.connector_principal(token) is None
    assert store.revoke_connector("gh-100", connector_id) is False  # already revoked


def test_connector_records_last_use(store):
    _, token = store.create_connector("gh-100")
    store.connector_principal(token)
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT last_used_at FROM connectors").fetchone()[0] is not None


def test_disabling_tenant_blocks_sessions_and_revokes_connectors(store):
    session = store.create_session(7, "octo", {"gh-100": "operator"})
    _, connector = store.create_connector("gh-100")
    store.disable_tenant("gh-100")
    assert store.session_principal(session, "gh-100") is None
    assert store.connector_principal(connector) is None
    # Reinstalling reactivates the tenant but not the revoked connector.
    store.upsert_tenant("gh-100", installation_id=3, github_account_id=100, github_login="acme", account_type="Organization")
    assert store.session_principal(session, "gh-100") is not None
    assert store.connector_principal(connector) is None


def test_incremental_repo_updates(store):
    store.update_tenant_repos("gh-100", added=["Acme/Jobs", "acme/api"], removed=["acme/web"])
    token = store.create_session(7, "octo", {"gh-100": "operator"})
    assert store.session_principal(token, "gh-100")["repositories"] == ["acme/api", "acme/jobs"]


def test_tenant_for_repo_requires_matching_installation_and_active_tenant(store):
    assert store.tenant_for_repo(1, "ACME/api") == "gh-100"
    assert store.tenant_for_repo(2, "acme/api") is None      # other installation
    assert store.tenant_for_repo(1, "acme/unlisted") is None  # repo not selected
    store.disable_tenant("gh-100")
    assert store.tenant_for_repo(1, "acme/api") is None
    assert IdentityStore(store.path.with_name("absent.sqlite3")).tenant_for_repo(1, "acme/api") is None


def test_default_path_follows_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("RAPHAEL_IDENTITY_DB", raising=False)
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    assert identity.identity_db_path() == tmp_path / "identity.sqlite3"
    monkeypatch.setenv("RAPHAEL_IDENTITY_DB", str(tmp_path / "custom.db"))
    assert identity.identity_db_path() == tmp_path / "custom.db"
