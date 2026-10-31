"""Interface bearer auth for I0 agent HTTP APIs."""

from __future__ import annotations

import hmac
import json
import os
from typing import Any

from raphael_agent.access import InterfacePrincipal

from starlette.requests import Request
from starlette.responses import JSONResponse


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def _error(code: str, message: str, *, status: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "retryable": False}},
        status_code=status,
    )


def interface_token() -> str:
    return os.environ.get("RAPHAEL_INTERFACE_TOKEN", "").strip()


def client_host(request: Request) -> str:
    if request.client is None:
        return ""
    return (request.client.host or "").strip().lower()


def is_loopback_host(host: str) -> bool:
    return host in LOOPBACK_HOSTS


def bearer_from_request(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def insecure_local(request: Request) -> bool:
    # Explicit development opt-in: reverse proxies often connect over loopback.
    return os.environ.get("RAPHAEL_ALLOW_INSECURE_LOCAL") == "1" and is_loopback_host(
        client_host(request)
    )


def principal(request: Request) -> InterfacePrincipal | None:
    identity = getattr(request.state, "principal", None)
    return identity if isinstance(identity, InterfacePrincipal) else None


def check_interface_auth(
    request: Request, role: str | None = None
) -> JSONResponse | None:
    raw = os.environ.get("RAPHAEL_INTERFACE_TOKENS", "").strip()
    token = interface_token()
    bearer = bearer_from_request(request)
    identity = None
    if raw:
        try:
            mapping = json.loads(raw)
            claims = (
                mapping.get(bearer) if bearer and isinstance(mapping, dict) else None
            )
            if not isinstance(claims, dict):
                raise ValueError
            tenant = claims.get("tenant_id")
            assigned_role = claims.get("role")
            repos = claims.get("repositories")
            if (
                not isinstance(tenant, str)
                or not tenant.strip()
                or assigned_role not in {"reader", "producer", "operator"}
                or not isinstance(repos, list)
                or not repos
                or not all(
                    isinstance(repo, str) and repo.count("/") == 1 for repo in repos
                )
                or any(
                    key in claims
                    and (not isinstance(claims[key], str) or not claims[key].strip())
                    for key in ("company_id", "client_id")
                )
            ):
                raise ValueError
            identity = InterfacePrincipal(
                tenant,
                assigned_role,
                tuple(repo.lower() for repo in repos),
                claims.get("company_id"),
                claims.get("client_id"),
            )
        except (ValueError, TypeError):
            return _error(
                "unauthorized", "invalid credentials or scope configuration", status=401
            )
    elif token:
        tenant = os.environ.get("RAPHAEL_AGENT_TENANT_ID", "").strip()
        if (
            not tenant
            or not bearer
            or not hmac.compare_digest(bearer.encode(), token.encode())
        ):
            return _error(
                "unauthorized",
                "invalid credentials or missing deployment tenant",
                status=401,
            )
        identity = InterfacePrincipal(tenant, "operator")
    elif not insecure_local(request):
        return _error(
            "unauthorized", "interface credentials are not configured", status=401
        )
    request.state.principal = identity
    if identity is not None and role is not None:
        allowed = {"producer", "operator"} if role == "producer" else {role}
        if identity.role not in allowed:
            return _error(
                "forbidden", "role is not permitted for this endpoint", status=403
            )
    return None


def scoped_run(request: Request, run: dict[str, Any] | None) -> bool:
    identity = principal(request)
    return run is not None and (identity is None or identity.allows(run))


def scope_key(request: Request) -> str | None:
    identity = principal(request)
    return identity.key if identity else None


def bind_ingest_scope(request: Request, seed: dict[str, Any]) -> JSONResponse | None:
    identity = principal(request)
    if identity is None:
        return None
    seed.update(identity.ownership)
    if not identity.allows(seed):
        return error_envelope("forbidden", "repository is not permitted", status=403)
    repo = seed["repository"]
    if repo.get("clone_url"):
        repo["clone_url"] = f"https://github.com/{repo['owner']}/{repo['name']}.git"
    seed["trigger"]["event_id"] = f"{identity.namespace}:{seed['trigger']['event_id']}"
    from raphael_agent.ingest.fingerprint import build_fingerprint

    seed["failure_fingerprint"] = build_fingerprint(seed)
    return None


def error_envelope(
    code: str, message: str, *, status: int, retryable: bool = False
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message, "retryable": retryable}
    }
    return JSONResponse(body, status_code=status)
