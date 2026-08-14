"""Command ACL (locked): write → status/help/feedback; else admin or team."""

from __future__ import annotations

from raphael_agent.github_commands.parse import PRIVILEGED_VERBS, WRITE_VERBS

WRITE_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
ADMIN_ASSOCIATIONS = frozenset({"OWNER"})
WRITE_PERMISSIONS = frozenset({"write", "maintain", "admin"})
ADMIN_PERMISSIONS = frozenset({"admin"})


def normalize_association(value: str | None) -> str:
    return (value or "").strip().upper()


def is_write(
    *,
    association: str | None,
    permission: str | None = None,
) -> bool:
    if (permission or "").strip().lower() in WRITE_PERMISSIONS:
        return True
    return normalize_association(association) in WRITE_ASSOCIATIONS


def is_admin(
    *,
    association: str | None,
    permission: str | None = None,
) -> bool:
    if (permission or "").strip().lower() in ADMIN_PERMISSIONS:
        return True
    return normalize_association(association) in ADMIN_ASSOCIATIONS


def acl_allows(
    verb: str,
    *,
    association: str | None,
    login: str | None,
    permission: str | None = None,
    team_logins: frozenset[str] | None = None,
) -> bool:
    """True when the actor may attempt ``verb`` (deferred verbs still ACL-gated)."""
    team = team_logins or frozenset()
    actor = (login or "").strip().lstrip("@").lower()
    in_team = bool(actor) and actor in team
    admin = is_admin(association=association, permission=permission) or in_team
    write = admin or is_write(association=association, permission=permission)

    if verb in WRITE_VERBS:
        return write
    if verb in PRIVILEGED_VERBS:
        return admin
    # Unknown verbs: same bar as write so we can reply "unknown" to collaborators.
    return write
