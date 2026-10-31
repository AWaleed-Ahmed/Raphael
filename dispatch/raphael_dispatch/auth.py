from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass
from typing import Any


class AuthError(ValueError):
    status_code: int = 401


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    role: str
    connector_id: str
    company_id: str | None = None
    client_id: str | None = None

    @property
    def ownership(self) -> dict[str, str]:
        return {
            key: value
            for key in ("tenant_id", "company_id", "client_id")
            if (value := getattr(self, key)) is not None
        }

    def allows(self, state: dict[str, Any]) -> bool:
        return all(state.get(key) == value for key, value in self.ownership.items())


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
    claims = mapping.get(token) if isinstance(mapping, dict) else None
    if (
        not isinstance(claims, dict)
        or not isinstance(claims.get("tenant_id"), str)
        or not claims["tenant_id"].strip()
        or any(
            key in claims
            and (not isinstance(claims[key], str) or not claims[key].strip())
            for key in ("company_id", "client_id", "connector_id")
        )
    ):
        raise AuthError("invalid token or role")
    if claims.get("role") != role:
        error = AuthError("token role is not permitted for this endpoint")
        error.status_code = 403
        raise error
    connector_id = str(claims.get("connector_id") or hashlib.sha256(token.encode()).hexdigest())
    return Principal(
        claims["tenant_id"],
        str(claims["role"]),
        connector_id,
        claims.get("company_id"),
        claims.get("client_id"),
    )
