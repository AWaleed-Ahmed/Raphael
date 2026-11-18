"""SQLite identity store: tenants, repositories, sessions and connector credentials.

See docs/auth-tenancy-design-2026-11-18.md. Credentials are stored only as
SHA-256 hashes. Reads never create the database, so until the first write every
lookup misses and callers fall back to environment-configured credentials.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SESSION_PREFIX = "rs_"
CONNECTOR_PREFIX = "rc_"
SESSION_TTL = timedelta(days=7)
ROLES = frozenset({"reader", "operator"})

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    github_account_id INTEGER UNIQUE,
    github_login TEXT,
    account_type TEXT,
    installation_id INTEGER UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    disabled_at TEXT
);
CREATE TABLE IF NOT EXISTS tenant_repos (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    repo_full_name TEXT NOT NULL,
    PRIMARY KEY (tenant_id, repo_full_name)
);
CREATE TABLE IF NOT EXISTS users (
    github_user_id INTEGER PRIMARY KEY,
    github_login TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_sha256 TEXT PRIMARY KEY,
    github_user_id INTEGER NOT NULL REFERENCES users(github_user_id),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS session_access (
    token_sha256 TEXT NOT NULL REFERENCES sessions(token_sha256),
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    role TEXT NOT NULL,
    PRIMARY KEY (token_sha256, tenant_id)
);
CREATE TABLE IF NOT EXISTS connectors (
    connector_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    token_sha256 TEXT NOT NULL UNIQUE,
    label TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);
"""


def identity_db_path() -> Path:
    explicit = os.environ.get("RAPHAEL_IDENTITY_DB", "").strip()
    if explicit:
        return Path(explicit)
    root = Path(os.environ.get("RAPHAEL_AGENT_DATA_DIR") or ".raphael-agent-data")
    return root / "identity.sqlite3"


def db_only() -> bool:
    """Production profile: ignore environment-configured credentials entirely."""
    return os.environ.get("RAPHAEL_AUTH_SOURCE", "").strip().lower() == "db"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


class IdentityStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else identity_db_path()

    def _connect(self, *, create: bool) -> sqlite3.Connection | None:
        if not create and not self.path.is_file():
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        return conn

    # Writes (used by the installation, connector and login flows).

    def upsert_tenant(
        self,
        tenant_id: str,
        *,
        installation_id: int,
        github_account_id: int,
        github_login: str,
        account_type: str,
    ) -> None:
        conn = self._connect(create=True)
        with conn:
            conn.execute(
                """INSERT INTO tenants (tenant_id, github_account_id, github_login, account_type,
                                        installation_id, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?)
                   ON CONFLICT(tenant_id) DO UPDATE SET
                     github_login = excluded.github_login, account_type = excluded.account_type,
                     installation_id = excluded.installation_id, status = 'active', disabled_at = NULL""",
                (tenant_id, github_account_id, github_login, account_type, installation_id, _iso(_now())),
            )
        conn.close()

    def set_tenant_repos(self, tenant_id: str, repos: list[str]) -> None:
        conn = self._connect(create=True)
        with conn:
            conn.execute("DELETE FROM tenant_repos WHERE tenant_id = ?", (tenant_id,))
            conn.executemany(
                "INSERT INTO tenant_repos (tenant_id, repo_full_name) VALUES (?, ?)",
                [(tenant_id, repo.lower()) for repo in sorted(set(repos))],
            )
        conn.close()

    def disable_tenant(self, tenant_id: str) -> None:
        conn = self._connect(create=True)
        now = _iso(_now())
        with conn:
            conn.execute(
                "UPDATE tenants SET status = 'disabled', disabled_at = ? WHERE tenant_id = ?",
                (now, tenant_id),
            )
            conn.execute(
                "UPDATE connectors SET revoked_at = ? WHERE tenant_id = ? AND revoked_at IS NULL",
                (now, tenant_id),
            )
        conn.close()

    def create_session(
        self, github_user_id: int, github_login: str, access: dict[str, str]
    ) -> str:
        if any(role not in ROLES for role in access.values()):
            raise ValueError("unknown session role")
        token = SESSION_PREFIX + secrets.token_urlsafe(32)
        digest, now = token_hash(token), _now()
        conn = self._connect(create=True)
        with conn:
            conn.execute(
                """INSERT INTO users (github_user_id, github_login, created_at, last_login_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(github_user_id) DO UPDATE SET
                     github_login = excluded.github_login, last_login_at = excluded.last_login_at""",
                (github_user_id, github_login, _iso(now), _iso(now)),
            )
            conn.execute(
                "INSERT INTO sessions (token_sha256, github_user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (digest, github_user_id, _iso(now), _iso(now + SESSION_TTL)),
            )
            conn.executemany(
                "INSERT INTO session_access (token_sha256, tenant_id, role) VALUES (?, ?, ?)",
                [(digest, tenant, role) for tenant, role in sorted(access.items())],
            )
        conn.close()
        return token

    def revoke_session(self, token: str) -> None:
        conn = self._connect(create=False)
        if conn is None:
            return
        with conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_sha256 = ? AND revoked_at IS NULL",
                (_iso(_now()), token_hash(token)),
            )
        conn.close()

    def create_connector(
        self, tenant_id: str, *, label: str = "", created_by: int | None = None
    ) -> tuple[str, str]:
        token = CONNECTOR_PREFIX + secrets.token_urlsafe(32)
        connector_id = "conn_" + secrets.token_hex(8)
        conn = self._connect(create=True)
        with conn:
            conn.execute(
                """INSERT INTO connectors (connector_id, tenant_id, token_sha256, label, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (connector_id, tenant_id, token_hash(token), label, created_by, _iso(_now())),
            )
        conn.close()
        return connector_id, token

    def revoke_connector(self, tenant_id: str, connector_id: str) -> bool:
        conn = self._connect(create=False)
        if conn is None:
            return False
        with conn:
            cursor = conn.execute(
                """UPDATE connectors SET revoked_at = ?
                   WHERE tenant_id = ? AND connector_id = ? AND revoked_at IS NULL""",
                (_iso(_now()), tenant_id, connector_id),
            )
        conn.close()
        return cursor.rowcount == 1

    # Reads (used on every authenticated request).

    def session_principal(self, token: str, tenant_id: str | None) -> dict[str, Any] | None:
        """Return tenant, role and repositories for a live session, or None.

        ``tenant_id`` selects among the session's tenants; it may be omitted
        only when the session grants exactly one tenant.
        """
        conn = self._connect(create=False)
        if conn is None:
            return None
        try:
            rows = conn.execute(
                """SELECT a.tenant_id, a.role FROM sessions s
                   JOIN session_access a ON a.token_sha256 = s.token_sha256
                   JOIN tenants t ON t.tenant_id = a.tenant_id AND t.status = 'active'
                   WHERE s.token_sha256 = ? AND s.revoked_at IS NULL AND s.expires_at > ?""",
                (token_hash(token), _iso(_now())),
            ).fetchall()
            if tenant_id is None:
                if len(rows) != 1:
                    return None
                selected = rows[0]
            else:
                selected = next((row for row in rows if row["tenant_id"] == tenant_id), None)
                if selected is None:
                    return None
            repos = [
                row["repo_full_name"]
                for row in conn.execute(
                    "SELECT repo_full_name FROM tenant_repos WHERE tenant_id = ? ORDER BY repo_full_name",
                    (selected["tenant_id"],),
                )
            ]
        finally:
            conn.close()
        if not repos:
            return None
        return {"tenant_id": selected["tenant_id"], "role": selected["role"], "repositories": repos}

    def connector_principal(self, token: str) -> dict[str, str] | None:
        conn = self._connect(create=False)
        if conn is None:
            return None
        digest = token_hash(token)
        try:
            row = conn.execute(
                """SELECT c.connector_id, c.tenant_id FROM connectors c
                   JOIN tenants t ON t.tenant_id = c.tenant_id AND t.status = 'active'
                   WHERE c.token_sha256 = ? AND c.revoked_at IS NULL""",
                (digest,),
            ).fetchone()
            if row is not None:
                with conn:
                    conn.execute(
                        "UPDATE connectors SET last_used_at = ? WHERE token_sha256 = ?",
                        (_iso(_now()), digest),
                    )
        finally:
            conn.close()
        return None if row is None else {"tenant_id": row["tenant_id"], "connector_id": row["connector_id"]}
