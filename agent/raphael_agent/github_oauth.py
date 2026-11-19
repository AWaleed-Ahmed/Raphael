"""GitHub App user authorization (docs/auth-tenancy-design-2026-11-18.md, decision 2).

Core exchanges the OAuth code itself, so the app's client secret never leaves
core. The user token is used only during login to read the user and their
installations, then dropped; it is never stored.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx

from raphael_agent.identity import IdentityStore
from raphael_agent.publish.config import github_api_base

MAX_INSTALLATION_PAGES = 10


class OAuthError(Exception):
    """Login failed; the message is safe to log but responses stay generic."""


def _web_base() -> str:
    return os.environ.get("RAPHAEL_GITHUB_WEB_BASE", "https://github.com").rstrip("/")


def _settings() -> tuple[str, str, str]:
    client_id = os.environ.get("RAPHAEL_GITHUB_APP_CLIENT_ID", "").strip()
    secret = os.environ.get("RAPHAEL_GITHUB_APP_CLIENT_SECRET", "").strip()
    redirect = os.environ.get("RAPHAEL_GITHUB_OAUTH_REDIRECT_URI", "").strip()
    return client_id, secret, redirect


def oauth_configured() -> bool:
    return all(_settings())


def authorize_url(state: str) -> str:
    client_id, _, redirect = _settings()
    query = urlencode({"client_id": client_id, "redirect_uri": redirect, "state": state})
    return f"{_web_base()}/login/oauth/authorize?{query}"


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "raphael-agent",
    }


def exchange_code(code: str) -> str:
    client_id, secret, redirect = _settings()
    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            f"{_web_base()}/login/oauth/access_token",
            headers={"Accept": "application/json", "User-Agent": "raphael-agent"},
            data={"client_id": client_id, "client_secret": secret, "code": code, "redirect_uri": redirect},
        )
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    token = body.get("access_token") if isinstance(body, dict) else None
    if response.status_code != 200 or not isinstance(token, str) or not token:
        raise OAuthError(f"code exchange failed: {body.get('error') if isinstance(body, dict) else response.status_code}")
    return token


def fetch_user(token: str) -> tuple[int, str]:
    with httpx.Client(timeout=15.0) as client:
        response = client.get(f"{github_api_base()}/user", headers=_api_headers(token))
    body = response.json() if response.status_code == 200 else {}
    if not isinstance(body.get("id"), int) or not isinstance(body.get("login"), str):
        raise OAuthError(f"user lookup failed: {response.status_code}")
    return body["id"], body["login"]


def fetch_installations(token: str) -> list[dict[str, Any]]:
    installations: list[dict[str, Any]] = []
    with httpx.Client(timeout=15.0) as client:
        for page in range(1, MAX_INSTALLATION_PAGES + 1):
            response = client.get(
                f"{github_api_base()}/user/installations",
                params={"per_page": 100, "page": page},
                headers=_api_headers(token),
            )
            if response.status_code != 200:
                raise OAuthError(f"installation lookup failed: {response.status_code}")
            batch = response.json().get("installations") or []
            installations.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100:
                break
    return installations


def is_org_admin(token: str, org_login: str) -> bool:
    """Best effort: any error means not an admin, so access degrades to reader."""
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"{github_api_base()}/user/memberships/orgs/{org_login}", headers=_api_headers(token)
            )
        body = response.json() if response.status_code == 200 else {}
        return body.get("role") == "admin" and body.get("state") == "active"
    except (httpx.HTTPError, ValueError):
        return False


def access_for_user(token: str, github_user_id: int, store: IdentityStore) -> dict[str, str]:
    """Map the user's GitHub-visible installations to tenant roles."""
    installations = fetch_installations(token)
    tenants = store.tenant_ids_for_installations(
        [item["id"] for item in installations if isinstance(item.get("id"), int)]
    )
    access: dict[str, str] = {}
    for item in installations:
        tenant = tenants.get(item.get("id"))
        account = item.get("account") or {}
        if tenant is None or not isinstance(account, dict):
            continue
        if account.get("type") == "User":
            access[tenant] = "operator" if account.get("id") == github_user_id else "reader"
        else:
            access[tenant] = "operator" if is_org_admin(token, str(account.get("login"))) else "reader"
    return access
