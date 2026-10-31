"""Trusted tenant and repository scope shared by HTTP and GitHub ingestion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InterfacePrincipal:
    tenant_id: str
    role: str
    repositories: tuple[str, ...] = ()
    company_id: str | None = None
    client_id: str | None = None

    @property
    def ownership(self) -> dict[str, str]:
        return {
            key: value
            for key in ("tenant_id", "company_id", "client_id")
            if (value := getattr(self, key)) is not None
        }

    @property
    def key(self) -> str:
        return json.dumps([self.ownership, self.repositories], sort_keys=True)

    @property
    def namespace(self) -> str:
        return hashlib.sha256(self.key.encode()).hexdigest()[:20]

    def allows(self, run: dict[str, Any]) -> bool:
        repo = run.get("repository") or {}
        name = f"{repo.get('owner')}/{repo.get('name')}".lower()
        return all(run.get(key) == value for key, value in self.ownership.items()) and (
            not self.repositories or name in self.repositories
        )
