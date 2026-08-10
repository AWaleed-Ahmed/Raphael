"""Optional GitHub App JWT → installation access token (Option B).

PAT (``RAPHAEL_GITHUB_TOKEN`` / ``GITHUB_TOKEN``) remains the default pilot path.
When App env vars are set and PAT is absent, mint a short-lived installation token.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx

from raphael_agent.publish.config import github_api_base


def app_id() -> str | None:
    raw = os.environ.get("RAPHAEL_GITHUB_APP_ID", "").strip()
    return raw or None


def installation_id() -> str | None:
    raw = os.environ.get("RAPHAEL_GITHUB_INSTALLATION_ID", "").strip()
    return raw or None


def private_key_pem() -> str | None:
    inline = os.environ.get("RAPHAEL_GITHUB_APP_PRIVATE_KEY", "").strip()
    if inline:
        return inline.replace("\\n", "\n")
    path = os.environ.get("RAPHAEL_GITHUB_APP_PRIVATE_KEY_PATH", "").strip()
    if path and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8")
    return None


def app_auth_configured() -> bool:
    return bool(app_id() and installation_id() and private_key_pem())


def _b64url(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_app_jwt(*, now: int | None = None) -> str:
    """HS-free RS256 JWT for GitHub App authentication.

    Uses cryptography if available; otherwise raises with a clear message.
    """
    aid = app_id()
    pem = private_key_pem()
    if not aid or not pem:
        raise RuntimeError("GitHub App id/private key not configured")
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "cryptography package required for GitHub App JWT "
            "(pip install cryptography)"
        ) from exc

    issued = int(now if now is not None else time.time()) - 60
    expires = issued + 9 * 60
    header = _b64url(b'{"alg":"RS256","typ":"JWT"}')
    payload = _b64url(
        (
            f'{{"iat":{issued},"exp":{expires},"iss":"{aid}"}}'
        ).encode("ascii")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64url(signature)}"


def fetch_installation_token(
    *,
    client: httpx.Client | None = None,
) -> str:
    """Exchange App JWT for an installation access token."""
    inst = installation_id()
    if not inst:
        raise RuntimeError("RAPHAEL_GITHUB_INSTALLATION_ID not set")
    jwt = build_app_jwt()
    url = f"{github_api_base()}/app/installations/{inst}/access_tokens"
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "raphael-agent",
    }
    if client is not None:
        response = client.post(url, headers=headers)
    else:
        with httpx.Client(timeout=30.0) as http:
            response = http.post(url, headers=headers)
    if response.status_code >= 400:
        raise RuntimeError(
            f"GitHub App installation token failed HTTP {response.status_code}: "
            f"{response.text[:200]}"
        )
    data: dict[str, Any] = response.json()
    token = data.get("token")
    if not token:
        raise RuntimeError("GitHub App token response missing token")
    return str(token)


def resolve_github_token() -> str | None:
    """PAT first; else App installation token when configured."""
    pat = (
        os.environ.get("RAPHAEL_GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or None
    )
    if pat:
        return pat
    if not app_auth_configured():
        return None
    try:
        return fetch_installation_token()
    except Exception:  # noqa: BLE001 — fail closed to None (caller treats as missing)
        return None
