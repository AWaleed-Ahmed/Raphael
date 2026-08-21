"""Credential-gated smoke test for one fake redacted telemetry outcome.

Required environment variables:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY

Optional environment variables:
  RAPHAEL_CLIENT_ID       default: fake-telemetry-client
  RAPHAEL_CLIENT_NAME     default: Fake Telemetry Client
  RAPHAEL_FAKE_RUN_ID     default: fake-telemetry-run-001
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from raphael_agent.telemetry_supabase import SupabaseTelemetryStore


def _request(
    base_url: str,
    secret_key: str,
    method: str,
    path: str,
    body: dict | None = None,
    prefer: str | None = None,
) -> list[dict]:
    headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"{base_url.rstrip('/')}/rest/v1/{path}",
        data=payload,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
        raise RuntimeError(f"Supabase request failed: {detail}") from exc
    decoded = json.loads(raw) if raw else []
    return decoded if isinstance(decoded, list) else []


def main() -> int:
    base_url = os.environ.get("SUPABASE_URL")
    secret_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
    if not base_url or not secret_key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SECRET_KEY) first.", file=sys.stderr)
        return 2

    client_id = os.environ.get("RAPHAEL_CLIENT_ID", "fake-telemetry-client")
    client_name = os.environ.get("RAPHAEL_CLIENT_NAME", "Fake Telemetry Client")
    run_id = os.environ.get("RAPHAEL_FAKE_RUN_ID", "fake-telemetry-run-001")
    project_name = "fake-telemetry-project"
    repository = {"owner": "raphael-fake", "name": "telemetry-demo"}

    client_rows = _request(
        base_url,
        secret_key,
        "POST",
        "raphael_clients?on_conflict=client_id",
        {"client_id": client_id, "client_name": client_name, "hosting_provider": "fake", "cluster_provider": "fake"},
        "resolution=merge-duplicates,return=representation",
    )
    if not client_rows or not client_rows[0].get("company_id"):
        raise RuntimeError("Supabase did not return a company_id for the fake client")
    company_id = str(client_rows[0]["company_id"])

    event = {
        "event_id": f"{run_id}:run_outcome:success_draft_pr_ready",
        "event_type": "run_outcome",
        "project_name": project_name,
        "run_id": run_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "repository": repository,
        "status": "success_draft_pr_ready",
        "success": True,
        "metadata": {"source": "fake_supabase_telemetry_smoke"},
    }
    uploaded = SupabaseTelemetryStore(base_url, secret_key).upload(
        [event], company_id=company_id, client_id=client_id
    )
    if uploaded != 1:
        raise RuntimeError(f"Expected one uploaded telemetry event, got {uploaded}")

    query = (
        "raphael_telemetry_events?select=company_id,client_id,project_name,run_id,repository,event_type,status&"
        f"company_id=eq.{quote(company_id, safe='')}&"
        f"client_id=eq.{quote(client_id, safe='')}&"
        f"project_name=eq.{quote(project_name, safe='')}&"
        f"run_id=eq.{quote(run_id, safe='')}"
    )
    rows = _request(base_url, secret_key, "GET", query)
    matching = [
        row for row in rows
        if row.get("repository") == repository and row.get("event_type") == "run_outcome"
    ]
    if not matching:
        raise RuntimeError("Scoped telemetry query did not return the inserted repository/run row")

    print(
        json.dumps(
            {
                "company_id": company_id,
                "client_id": client_id,
                "project_name": project_name,
                "repository": repository,
                "run_id": run_id,
                "matching_rows": len(matching),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
