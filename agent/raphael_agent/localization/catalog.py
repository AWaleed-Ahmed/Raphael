"""Multi-Tenant Healthy Catalog Store (FLE / Layer 2 Catalog).

Maintains a unified catalog across all companies/clients tracking:
- Deployed release metadata (git_sha, image_digest, OCI labels)
- Route-to-handler maps
- Golden trace execution baselines
- Known stack trace signatures
- Business invariants
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from raphael_agent.timeutil import utc_now


@dataclass
class CatalogEntry:
    company_id: str
    client_id: str
    client_name: str
    tenant_id: str
    service_name: str
    environment: str
    git_sha: str
    image_digest: str | None = None
    route_handler_maps: dict[str, dict[str, Any]] = field(default_factory=dict)
    stack_trace_signatures: list[str] = field(default_factory=list)
    golden_trace_spans: dict[str, list[str]] = field(default_factory=dict)
    invariants: list[dict[str, Any]] = field(default_factory=list)
    last_known_good_sha: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CatalogEntry:
        return cls(
            company_id=str(data.get("company_id") or "default_comp"),
            client_id=str(data.get("client_id") or "default_cli"),
            client_name=str(data.get("client_name") or "Acme Corp"),
            tenant_id=str(data.get("tenant_id") or "local-dev"),
            service_name=str(data.get("service_name") or "workload"),
            environment=str(data.get("environment") or "staging"),
            git_sha=str(data.get("git_sha") or "0000000"),
            image_digest=data.get("image_digest"),
            route_handler_maps=dict(data.get("route_handler_maps") or {}),
            stack_trace_signatures=list(data.get("stack_trace_signatures") or []),
            golden_trace_spans=dict(data.get("golden_trace_spans") or {}),
            invariants=list(data.get("invariants") or []),
            last_known_good_sha=data.get("last_known_good_sha"),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
        )


class HealthyCatalogStore:
    """Multi-tenant catalog manager for healthy baseline traces, route maps, and release identities."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            base = os.environ.get("RAPHAEL_AGENT_DATA_DIR", "/tmp/raphael_agent_dev")
            self.root = Path(base) / "catalogs"
        else:
            self.root = Path(storage_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, CatalogEntry] = {}

    def _key(self, company_id: str, client_id: str, tenant_id: str, service_name: str, environment: str) -> str:
        return f"{company_id}|{client_id}|{tenant_id}|{service_name}|{environment}".lower()

    def _file_path(
        self,
        company_id: str,
        client_id: str,
        tenant_id: str,
        service_name: str,
        environment: str,
    ) -> Path:
        # Keep client_id in the persisted path too; otherwise two clients in
        # one company can overwrite baselines with the same service/env names.
        safe_dir = self.root / f"comp_{company_id}" / f"client_{client_id}" / f"tenant_{tenant_id}"
        safe_dir.mkdir(parents=True, exist_ok=True)
        return safe_dir / f"{service_name}_{environment}.json"

    def record_healthy_release(
        self,
        *,
        company_id: str,
        client_id: str,
        client_name: str,
        tenant_id: str,
        service_name: str,
        environment: str,
        git_sha: str,
        image_digest: str | None = None,
        route_handler_maps: dict[str, dict[str, Any]] | None = None,
        stack_trace_signatures: list[str] | None = None,
        golden_trace_spans: dict[str, list[str]] | None = None,
        invariants: list[dict[str, Any]] | None = None,
    ) -> CatalogEntry:
        """Register or update a verified healthy release baseline."""
        key = self._key(company_id, client_id, tenant_id, service_name, environment)
        entry = CatalogEntry(
            company_id=company_id,
            client_id=client_id,
            client_name=client_name,
            tenant_id=tenant_id,
            service_name=service_name,
            environment=environment,
            git_sha=git_sha,
            image_digest=image_digest,
            route_handler_maps=route_handler_maps or {},
            stack_trace_signatures=stack_trace_signatures or [],
            golden_trace_spans=golden_trace_spans or {},
            invariants=invariants or [],
            last_known_good_sha=git_sha,
            updated_at=utc_now(),
        )
        self._memory[key] = entry
        file_path = self._file_path(company_id, client_id, tenant_id, service_name, environment)
        file_path.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")
        return entry

    def get_catalog_entry(
        self,
        *,
        company_id: str,
        client_id: str,
        tenant_id: str,
        service_name: str,
        environment: str,
    ) -> CatalogEntry | None:
        """Retrieve baseline for a specific tenant and service."""
        key = self._key(company_id, client_id, tenant_id, service_name, environment)
        if key in self._memory:
            return self._memory[key]

        file_path = self._file_path(company_id, client_id, tenant_id, service_name, environment)
        if file_path.is_file():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                entry = CatalogEntry.from_dict(data)
                self._memory[key] = entry
                return entry
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def get_last_known_good_sha(
        self,
        *,
        company_id: str,
        client_id: str,
        tenant_id: str,
        service_name: str,
        environment: str,
    ) -> str | None:
        """Fetch the last verified healthy Git SHA."""
        entry = self.get_catalog_entry(
            company_id=company_id,
            client_id=client_id,
            tenant_id=tenant_id,
            service_name=service_name,
            environment=environment,
        )
        return entry.last_known_good_sha if entry else None

    def get_golden_trace(
        self,
        *,
        company_id: str,
        client_id: str,
        tenant_id: str,
        service_name: str,
        environment: str,
        operation: str,
    ) -> list[str]:
        """Fetch the expected sequence of span names for an operation."""
        entry = self.get_catalog_entry(
            company_id=company_id,
            client_id=client_id,
            tenant_id=tenant_id,
            service_name=service_name,
            environment=environment,
        )
        if not entry:
            return []
        return entry.golden_trace_spans.get(operation, [])
