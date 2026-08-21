"""Supabase sink for the redacted local telemetry stream."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class SupabaseTelemetryError(RuntimeError):
    pass


TERMINAL_RUN_STATUSES = frozenset(
    {
        "success_draft_pr_ready",
        "success_fix_proposed",
        "escalated",
        "failed_closed",
        "cancelled",
    }
)
_LOG = logging.getLogger(__name__)


def _project_name(run: dict[str, Any]) -> str:
    repository = run.get("repository") or {}
    owner = str(repository.get("owner") or "").strip()
    name = str(repository.get("name") or "").strip()
    if owner and name:
        return f"{owner}/{name}"
    return name or owner or "unknown"


def _repository_identity(run: dict[str, Any]) -> dict[str, str]:
    repository = run.get("repository") or {}
    identity: dict[str, str] = {}
    for key in ("owner", "name"):
        value = str(repository.get(key) or "").strip()
        if value:
            identity[key] = value
    return identity


def _recorded_at(run: dict[str, Any]) -> str:
    value = run.get("updated_at") or run.get("created_at")
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()


def build_run_outcome_event(run: dict[str, Any]) -> dict[str, Any] | None:
    status = str(run.get("status") or "")
    run_id = str(run.get("run_id") or "")
    if status not in TERMINAL_RUN_STATUSES or not run_id:
        return None

    errors = run.get("errors") or []
    first_error = errors[0] if isinstance(errors, list) and errors else {}
    metadata = {
        "trigger_kind": (run.get("trigger") or {}).get("kind"),
        "delivery_mode": run.get("delivery_mode"),
        "sandbox_mode": run.get("sandbox_mode"),
        "terminal_reason": run.get("terminal_reason"),
    }
    metadata = {key: value for key, value in metadata.items() if value is not None}
    event: dict[str, Any] = {
        "event_id": f"{run_id}:run_outcome:{status}",
        "event_type": "run_outcome",
        "project_name": _project_name(run),
        "run_id": run_id,
        "recorded_at": _recorded_at(run),
        "repository": _repository_identity(run),
        "status": status,
        "success": status.startswith("success_"),
        "metadata": metadata,
    }
    if isinstance(first_error, dict) and first_error.get("code"):
        event["error_type"] = str(first_error["code"])
    token_usage = run.get("token_and_cost_usage")
    if isinstance(token_usage, dict):
        event["token_usage"] = token_usage
    return event


def resolve_company_id(
    client_id: str | None,
    explicit_company_id: str | None = None,
) -> str | None:
    """Resolve company scope from explicit config or the Supabase client catalog."""
    company_id = str(
        explicit_company_id or os.environ.get("RAPHAEL_COMPANY_ID") or ""
    ).strip()
    if company_id:
        return company_id
    normalized_client_id = str(client_id or os.environ.get("RAPHAEL_CLIENT_ID") or "").strip()
    if not normalized_client_id:
        return None
    base_url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    secret_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY") or ""
    if not base_url or not secret_key:
        return None
    request = Request(
        f"{base_url}/rest/v1/raphael_clients?select=company_id,client_id,status&client_id=eq."
        + quote(normalized_client_id, safe=""),
        headers={
            "apikey": secret_key,
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20.0) as response:
            rows = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — telemetry must remain fail-open
        _LOG.warning("company scope lookup skipped: %s", exc)
        return None
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return None
    return str(rows[0].get("company_id") or "").strip() or None


def record_run_outcome(run: dict[str, Any]) -> bool:
    """Best-effort upload of one redacted terminal outcome; never breaks a run."""
    event = build_run_outcome_event(run)
    if event is None:
        return False
    client_id = str(run.get("client_id") or os.environ.get("RAPHAEL_CLIENT_ID") or "").strip()
    company_id = resolve_company_id(client_id, str(run.get("company_id") or "").strip() or None)
    if not company_id or not client_id:
        return False
    try:
        SupabaseTelemetryStore().upload([event], company_id=company_id, client_id=client_id)
    except Exception as exc:  # noqa: BLE001 — telemetry must never break a run
        _LOG.warning("run outcome telemetry upload skipped: %s", exc)
        return False
    return True


class SupabaseTelemetryStore:
    def __init__(self, base_url: str | None = None, secret_key: str | None = None, timeout: float = 20.0) -> None:
        self.base_url = (base_url or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.secret_key = secret_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY") or ""
        self.timeout = timeout
        if not self.base_url or not self.secret_key:
            raise SupabaseTelemetryError("SUPABASE_URL and a backend-only Supabase secret key are required")

    def upload(self, events: list[dict[str, Any]], *, company_id: str, client_id: str) -> int:
        if not events:
            return 0
        rows = []
        for event in events:
            row = dict(event)
            row.update({"company_id": company_id, "client_id": client_id})
            rows.append(row)
        request = Request(
            f"{self.base_url}/rest/v1/raphael_telemetry_events?on_conflict=event_id",
            data=json.dumps(rows).encode("utf-8"),
            headers={
                "apikey": self.secret_key,
                "Authorization": f"Bearer {self.secret_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=ignore-duplicates,return=minimal",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout):
                return len(rows)
        except (HTTPError, URLError) as exc:
            detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
            raise SupabaseTelemetryError(f"Supabase telemetry upload failed: {detail}") from exc
