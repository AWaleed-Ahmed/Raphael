"""GitHub App installation lifecycle -> tenants (docs/auth-tenancy-design-2026-11-18.md).

A tenant is one GitHub App installation account. ``installation`` events create,
reactivate or disable it; ``installation_repositories`` events keep its selected
repositories in sync. Callers verify the webhook signature first.
"""

from __future__ import annotations

from typing import Any

from raphael_agent.identity import IdentityStore

INSTALLATION_EVENTS = frozenset({"installation", "installation_repositories"})
_ACTIVATE = frozenset({"created", "unsuspend", "new_permissions_accepted"})
_DISABLE = frozenset({"deleted", "suspend"})


def tenant_id_for_account(account_id: int) -> str:
    """Stable across account renames: GitHub account IDs never change."""
    return f"gh-{account_id}"


def _installation(payload: dict[str, Any]) -> tuple[int, int, str, str]:
    installation = payload.get("installation")
    account = installation.get("account") if isinstance(installation, dict) else None
    if not isinstance(account, dict):
        raise ValueError("installation event is missing installation.account")
    installation_id, account_id = installation.get("id"), account.get("id")
    login, account_type = account.get("login"), account.get("type")
    if (
        not isinstance(installation_id, int)
        or not isinstance(account_id, int)
        or not isinstance(login, str)
        or not login
        or account_type not in {"User", "Organization"}
    ):
        raise ValueError("installation event has an invalid installation or account")
    return installation_id, account_id, login, account_type


def _repo_names(items: Any) -> list[str]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError("repository list must be an array")
    names = []
    for item in items:
        name = item.get("full_name") if isinstance(item, dict) else None
        if not isinstance(name, str) or name.count("/") != 1:
            raise ValueError("repository entry is missing full_name")
        names.append(name)
    return names


def handle_installation_event(
    event_name: str, payload: dict[str, Any], store: IdentityStore | None = None
) -> dict[str, Any]:
    """Apply one verified installation webhook; returns a decision summary."""
    store = store or IdentityStore()
    action = payload.get("action")
    installation_id, account_id, login, account_type = _installation(payload)
    tenant_id = tenant_id_for_account(account_id)

    def activate() -> None:
        store.upsert_tenant(
            tenant_id,
            installation_id=installation_id,
            github_account_id=account_id,
            github_login=login,
            account_type=account_type,
        )

    if event_name == "installation":
        if action in _ACTIVATE:
            repos = _repo_names(payload.get("repositories")) if action == "created" else None
            activate()
            if repos is not None:
                store.set_tenant_repos(tenant_id, repos)
            return {"decision": "tenant_active", "tenant_id": tenant_id, "action": action}
        if action in _DISABLE:
            store.disable_tenant(tenant_id)
            return {"decision": "tenant_disabled", "tenant_id": tenant_id, "action": action}
    elif event_name == "installation_repositories" and action in {"added", "removed"}:
        added = _repo_names(payload.get("repositories_added"))
        removed = _repo_names(payload.get("repositories_removed"))
        if store.tenant_status(tenant_id) is None:
            activate()  # out-of-order delivery; never reactivates a disabled tenant
        store.update_tenant_repos(tenant_id, added=added, removed=removed)
        return {
            "decision": "tenant_repos_updated",
            "tenant_id": tenant_id,
            "added": len(added),
            "removed": len(removed),
        }
    return {"decision": "ignored", "reason": f"unhandled {event_name}.{action}"}
