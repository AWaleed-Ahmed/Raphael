"""Interface bearer auth for I0 agent HTTP APIs."""

from __future__ import annotations

import os
from typing import Any

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


def check_interface_auth(request: Request) -> JSONResponse | None:
    """Return an error response if auth fails; None if OK.

    Loopback may omit token when ``RAPHAEL_INTERFACE_TOKEN`` is unset.
    Non-loopback always requires a configured matching bearer token.
    """
    token = interface_token()
    host = client_host(request)
    loopback = is_loopback_host(host)
    bearer = bearer_from_request(request)

    if not loopback:
        if not token:
            return _error(
                "unauthorized",
                "RAPHAEL_INTERFACE_TOKEN must be set for non-loopback clients",
                status=401,
            )
        if bearer != token:
            return _error("unauthorized", "invalid or missing bearer token", status=401)
        return None

    if token and bearer != token:
        return _error("unauthorized", "invalid or missing bearer token", status=401)
    return None


def error_envelope(
    code: str, message: str, *, status: int, retryable: bool = False
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {"code": code, "message": message, "retryable": retryable}
    }
    return JSONResponse(body, status_code=status)
