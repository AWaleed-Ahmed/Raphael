from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass
from typing import Any


class AuthError(ValueError):
    pass


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    role: str
    connector_id: str


def principal_from_request(authorization: str | None, role: str) -> Principal:
    raw = os.environ.get("RAPHAEL_DISPATCH_TOKENS", "").strip()
    if not raw:
        raise AuthError("RAPHAEL_DISPATCH_TOKENS is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthError("missing bearer token")
    try:
        mapping: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthError("RAPHAEL_DISPATCH_TOKENS must be valid JSON") from exc
    token = authorization[7:]
    claims = mapping.get(token)
    if not isinstance(claims, dict) or not claims.get("tenant_id"):
        raise AuthError("invalid token or role")
    if claims.get("role") != role:
        error = AuthError("token role is not permitted for this endpoint")
        error.status_code = 403
        raise error
    connector_id = str(claims.get("connector_id") or hashlib.sha256(token.encode()).hexdigest())
    return Principal(str(claims["tenant_id"]), str(claims["role"]), connector_id)
