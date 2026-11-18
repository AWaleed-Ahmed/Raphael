"""GitHub App installation lifecycle -> tenants and repositories."""

from __future__ import annotations

import pytest

from raphael_agent.identity import IdentityStore
from raphael_agent.ingest.installations import handle_installation_event, tenant_id_for_account


def installation(action: str, *, repos=None, account_id=100, login="acme", account_type="Organization", inst_id=11):
    payload = {
        "action": action,
        "installation": {"id": inst_id, "account": {"id": account_id, "login": login, "type": account_type}},
    }
    if repos is not None:
        payload["repositories"] = [{"full_name": name} for name in repos]
    return payload


def repos_event(action: str, *, added=(), removed=(), account_id=100, inst_id=11):
    payload = installation(action, account_id=account_id, inst_id=inst_id)
    payload["repositories_added"] = [{"full_name": name} for name in added]
    payload["repositories_removed"] = [{"full_name": name} for name in removed]
    return payload


@pytest.fixture
def store(tmp_path):
    return IdentityStore(tmp_path / "identity.sqlite3")


def test_created_makes_active_tenant_with_selected_repos(store):
    result = handle_installation_event("installation", installation("created", repos=["acme/API", "acme/web"]), store)
    assert result == {"decision": "tenant_active", "tenant_id": "gh-100", "action": "created"}
    assert store.tenant_for_repo(11, "acme/api") == "gh-100"
    assert store.tenant_for_repo(11, "acme/web") == "gh-100"


def test_tenant_id_is_the_stable_account_id_not_the_login(store):
    handle_installation_event("installation", installation("created", repos=["acme/api"]), store)
    handle_installation_event("installation", installation("new_permissions_accepted", login="acme-renamed"), store)
    assert tenant_id_for_account(100) == "gh-100"
    assert store.tenant_for_repo(11, "acme/api") == "gh-100"


def test_repository_changes_apply_as_deltas(store):
    handle_installation_event("installation", installation("created", repos=["acme/api"]), store)
    result = handle_installation_event(
        "installation_repositories", repos_event("added", added=["acme/jobs"], removed=["acme/api"]), store
    )
    assert result["decision"] == "tenant_repos_updated" and result["added"] == 1 and result["removed"] == 1
    assert store.tenant_for_repo(11, "acme/jobs") == "gh-100"
    assert store.tenant_for_repo(11, "acme/api") is None


def test_deleted_and_suspended_disable_and_revoke(store):
    handle_installation_event("installation", installation("created", repos=["acme/api"]), store)
    _, connector = store.create_connector("gh-100")
    assert handle_installation_event("installation", installation("suspend"), store)["decision"] == "tenant_disabled"
    assert store.tenant_for_repo(11, "acme/api") is None
    assert store.connector_principal(connector) is None
    handle_installation_event("installation", installation("unsuspend"), store)
    assert store.tenant_for_repo(11, "acme/api") == "gh-100"  # repos kept across suspension
    assert store.connector_principal(connector) is None       # revoked credentials stay revoked
    handle_installation_event("installation", installation("deleted"), store)
    assert store.tenant_status("gh-100") == "disabled"


def test_repo_event_never_reactivates_a_disabled_tenant(store):
    handle_installation_event("installation", installation("created", repos=["acme/api"]), store)
    handle_installation_event("installation", installation("suspend"), store)
    handle_installation_event("installation_repositories", repos_event("added", added=["acme/jobs"]), store)
    assert store.tenant_status("gh-100") == "disabled"
    assert store.tenant_for_repo(11, "acme/jobs") is None


def test_out_of_order_repo_event_creates_the_tenant(store):
    handle_installation_event("installation_repositories", repos_event("added", added=["solo/app"], account_id=200, inst_id=22), store)
    assert store.tenant_for_repo(22, "solo/app") == "gh-200"


def test_unknown_actions_are_ignored(store):
    result = handle_installation_event("installation", installation("new_feature"), store)
    assert result["decision"] == "ignored"
    assert store.tenant_status("gh-100") is None


@pytest.mark.parametrize("payload", [
    {"action": "created"},
    {"action": "created", "installation": {"id": "11", "account": {"id": 100, "login": "acme", "type": "Organization"}}},
    {"action": "created", "installation": {"id": 11, "account": {"id": 100, "login": "acme", "type": "Bot"}}},
    {"action": "created", "installation": {"id": 11, "account": {"id": 100, "login": "acme", "type": "User"}},
     "repositories": [{"name": "no-full-name"}]},
])
def test_malformed_payloads_are_rejected_without_writes(store, payload):
    with pytest.raises(ValueError):
        handle_installation_event("installation", payload, store)
    assert not store.path.exists()
