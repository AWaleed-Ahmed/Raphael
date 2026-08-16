"""Supabase-backed healthy trace catalog and provider-neutral comparison helpers.

The adapter intentionally uses Supabase REST with the backend-only key so the
localization engine can run without coupling itself to a particular Python SDK.
All queries carry company/client/service/environment scope explicitly.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class SupabaseCatalogError(RuntimeError):
    """Raised when the catalog API cannot be read or written safely."""


@dataclass(frozen=True)
class HealthyTraceComparison:
    """Comparison between an unhealthy observation and one healthy baseline."""

    healthy_trace_id: str | None
    same_scope: bool
    fingerprint_match: bool
    stack_diverged: bool
    span_diverged: bool
    first_divergent_span_index: int | None
    source_anchor_match: bool
    confidence: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _span_attributes(span: Any) -> dict[str, Any]:
    if not isinstance(span, dict):
        return {}
    attrs = span.get("attributes")
    return attrs if isinstance(attrs, dict) else span


def _span_name(span: Any) -> str:
    if isinstance(span, str):
        return span.strip()
    attrs = _span_attributes(span)
    return str(
        attrs.get("name")
        or attrs.get("span.name")
        or attrs.get("operation_name")
        or attrs.get("resource")
        or ""
    ).strip()


def _span_is_error(span: Any) -> bool:
    attrs = _span_attributes(span)
    status = str(attrs.get("status_code") or attrs.get("status") or "").lower()
    return bool(
        attrs.get("error")
        or attrs.get("error.type")
        or attrs.get("exception.type")
        or status in {"error", "failed", "failure"}
        or status.startswith("5")
    )


def _span_sequence(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value


def _first_span_divergence(healthy: list[Any], unhealthy: list[Any]) -> int | None:
    limit = max(len(healthy), len(unhealthy))
    for index in range(limit):
        if index >= len(healthy) or index >= len(unhealthy):
            return index
        current = unhealthy[index]
        if _span_is_error(current):
            return index
        if _span_name(healthy[index]) != _span_name(current):
            return index
    return None


def compare_trace_to_healthy(
    unhealthy: dict[str, Any], healthy: dict[str, Any]
) -> HealthyTraceComparison:
    """Compare a runtime failure to one baseline without provider assumptions."""

    scope_fields = ("company_id", "client_id", "service_name", "environment", "operation")
    same_scope = all(
        unhealthy.get(field) is not None
        and healthy.get(field) is not None
        and str(unhealthy.get(field)) == str(healthy.get(field))
        for field in scope_fields
    )
    fingerprint_match = bool(
        unhealthy.get("stack_fingerprint")
        and healthy.get("stack_fingerprint")
        and unhealthy.get("stack_fingerprint") == healthy.get("stack_fingerprint")
    )
    normalized_unhealthy = str(unhealthy.get("normalized_stack_trace") or "")
    normalized_healthy = str(healthy.get("normalized_stack_trace") or "")
    stack_diverged = bool(normalized_unhealthy and normalized_healthy and normalized_unhealthy != normalized_healthy)

    span_index = _first_span_divergence(
        _span_sequence(healthy.get("span_sequence")),
        _span_sequence(unhealthy.get("span_sequence")),
    )
    span_diverged = span_index is not None

    source_fields = ("source_file", "source_line", "source_symbol")
    source_values_present = all(
        unhealthy.get(field) is not None and healthy.get(field) is not None
        for field in source_fields
    )
    if source_values_present:
        # Runtime paths often carry container/workspace prefixes while the
        # catalog stores repository-relative paths. Compare normalized suffixes
        # so `/app/src/payments.py` and `src/payments.py` resolve identically.
        unhealthy_path = str(unhealthy["source_file"]).replace("\\", "/").lstrip("/")
        healthy_path = str(healthy["source_file"]).replace("\\", "/").lstrip("/")
        path_match = (
            unhealthy_path == healthy_path
            or unhealthy_path.endswith("/" + healthy_path)
            or healthy_path.endswith("/" + unhealthy_path)
        )
        try:
            line_match = int(unhealthy["source_line"]) == int(healthy["source_line"])
        except (TypeError, ValueError):
            line_match = str(unhealthy["source_line"]) == str(healthy["source_line"])
        source_anchor_match = path_match and line_match and str(
            unhealthy["source_symbol"]
        ) == str(healthy["source_symbol"])
    else:
        source_anchor_match = False

    reasons: list[str] = []
    if not same_scope:
        reasons.append("scope_mismatch")
    if fingerprint_match:
        reasons.append("fingerprint_matches_healthy_baseline")
    else:
        reasons.append("fingerprint_differs_from_healthy_baseline")
    if stack_diverged:
        reasons.append("normalized_stack_differs")
    if span_diverged:
        reasons.append(f"first_span_divergence={span_index}")
    if source_anchor_match:
        reasons.append("source_anchor_matches")

    score = 0.0
    if same_scope:
        score += 0.45
    if stack_diverged or not fingerprint_match:
        score += 0.25
    if span_diverged:
        score += 0.20
    if source_anchor_match:
        score += 0.10

    return HealthyTraceComparison(
        healthy_trace_id=str(healthy.get("healthy_trace_id")) if healthy.get("healthy_trace_id") else None,
        same_scope=same_scope,
        fingerprint_match=fingerprint_match,
        stack_diverged=stack_diverged,
        span_diverged=span_diverged,
        first_divergent_span_index=span_index,
        source_anchor_match=source_anchor_match,
        confidence=round(min(1.0, score), 4),
        reasons=reasons,
    )


class SupabaseHealthyCatalogStore:
    """REST-backed healthy trace store for the Raphael backend."""

    def __init__(self, base_url: str | None = None, service_role_key: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = (base_url or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.service_role_key = service_role_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY") or ""
        self.timeout = timeout
        if not self.base_url or not self.service_role_key:
            raise SupabaseCatalogError("SUPABASE_URL and a backend-only Supabase secret key are required")

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None, prefer: str | None = None
    ) -> list[dict[str, Any]]:
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            f"{self.base_url}/rest/v1/{path}",
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except (HTTPError, URLError) as exc:
            detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
            raise SupabaseCatalogError(f"Supabase catalog request failed: {detail}") from exc
        decoded = json.loads(raw) if raw else []
        if not isinstance(decoded, list):
            raise SupabaseCatalogError("Supabase catalog returned a non-list response")
        return decoded

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        """Return one client registry row by its stable client id."""
        rows = self._request(
            "GET",
            "raphael_clients?select=company_id,client_id,client_name,status&client_id=eq."
            + quote(client_id, safe=""),
        )
        return rows[0] if rows else None

    def list_healthy_traces(
        self,
        *,
        company_id: str,
        client_id: str,
        service_name: str,
        environment: str,
        operation: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        filters = {
            "select": "*",
            "company_id": f"eq.{company_id}",
            "client_id": f"eq.{client_id}",
            "service_name": f"eq.{service_name}",
            "environment": f"eq.{environment}",
            "verified_healthy": "eq.true",
            "order": "is_last_known_good.desc,verified_at.desc",
            "limit": str(max(1, min(limit, 500))),
        }
        if operation:
            filters["operation"] = f"eq.{operation}"
        query = urlencode(filters, quote_via=quote)
        return self._request("GET", f"raphael_healthy_traces?{query}")

    def record_healthy_trace(self, trace: dict[str, Any]) -> dict[str, Any]:
        required = (
            "company_id", "client_id", "service_name", "environment",
            "normalized_stack_trace", "stack_fingerprint",
        )
        missing = [field for field in required if not trace.get(field)]
        if missing:
            raise SupabaseCatalogError(f"healthy trace missing required fields: {', '.join(missing)}")
        rows = self._request(
            "POST",
            "raphael_healthy_traces?on_conflict=company_id,client_id,service_name,environment,operation,stack_fingerprint,code_id,source_commit_sha",
            trace,
            "resolution=merge-duplicates,return=representation",
        )
        if not rows:
            raise SupabaseCatalogError("Supabase did not return the upserted healthy trace")
        return rows[0]

    def compare_unhealthy_trace(
        self,
        unhealthy: dict[str, Any],
        *,
        company_id: str,
        client_id: str,
        service_name: str,
        environment: str,
        operation: str | None = None,
    ) -> list[HealthyTraceComparison]:
        scoped = {
            **unhealthy,
            "company_id": company_id,
            "client_id": client_id,
            "service_name": service_name,
            "environment": environment,
            "operation": operation or unhealthy.get("operation") or "unknown",
        }
        baselines = self.list_healthy_traces(
            company_id=company_id,
            client_id=client_id,
            service_name=service_name,
            environment=environment,
            operation=operation,
        )
        return [compare_trace_to_healthy(scoped, baseline) for baseline in baselines]
