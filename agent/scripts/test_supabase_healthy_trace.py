#!/usr/bin/env python3
"""Credential-gated Supabase smoke test for one fake healthy stack trace.

Required environment variables:
  SUPABASE_URL                  https://<project-ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY     legacy backend-only key; never expose to browsers
  SUPABASE_SECRET_KEY            preferred backend-only key (alternative)

Optional:
  RAPHAEL_CLIENT_ID             default: fake-client
  RAPHAEL_CLIENT_NAME           default: Fake Client
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def _request(
    base_url: str,
    service_role_key: str,
    method: str,
    path: str,
    body: dict | None = None,
    prefer: str | None = None,
) -> list[dict]:
    url = f"{base_url.rstrip('/')}/rest/v1/{path}"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except (HTTPError, URLError) as exc:
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, HTTPError) else str(exc)
        raise RuntimeError(f"Supabase request failed: {detail}") from exc
    return json.loads(raw) if raw else []


def main() -> int:
    base_url = os.environ.get("SUPABASE_URL")
    service_role_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SECRET_KEY")
    )
    if not base_url or not service_role_key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SECRET_KEY) first.", file=sys.stderr)
        return 2

    client_id = os.environ.get("RAPHAEL_CLIENT_ID", "fake-client")
    client_name = os.environ.get("RAPHAEL_CLIENT_NAME", "Fake Client")
    client_rows = _request(
        base_url,
        service_role_key,
        "POST",
        "raphael_clients?on_conflict=client_id",
        {"client_id": client_id, "client_name": client_name, "hosting_provider": "fake", "cluster_provider": "kubernetes"},
        "resolution=merge-duplicates,return=representation",
    )
    if not client_rows or not client_rows[0].get("company_id"):
        raise RuntimeError("Supabase did not return a company_id for the client")

    company_id = client_rows[0]["company_id"]
    stack_trace = (
        'Traceback (most recent call last):\n'
        '  File "/app/payment_client.py", line 84, in authorize\n'
        '    raise TimeoutError("payment gateway timeout")\n'
        'TimeoutError: payment gateway timeout'
    )
    normalized = "payment_client.py:84:authorize|timeouterror|post /orders"
    stack_fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    trace = {
        "company_id": company_id,
        "client_id": client_id,
        "service_name": "checkout-api",
        "environment": "staging",
        "repository": "example/checkout-api",
        "git_sha": "abcdef1234567890",
        "image_digest": "sha256:fake",
        "operation": "POST /orders",
        "trace_provider": "fake",
        "trace_id": "fake-trace-001",
        "stack_trace": stack_trace,
        "normalized_stack_trace": normalized,
        "stack_fingerprint": stack_fingerprint,
        "code_id": "checkout-api:payment_client.py:84:authorize",
        "source_file": "src/payment_client.py",
        "source_line": 84,
        "source_symbol": "authorize",
        "source_commit_sha": "abcdef1234567890",
        "span_sequence": ["POST /orders", "payment.authorize"],
        "runtime_identity": {"service.name": "checkout-api", "deployment.environment.name": "staging"},
        "invariants": [{"name": "payment_authorized", "passed": True}],
        "verified_healthy": True,
        "is_last_known_good": True,
    }
    conflict_columns = "company_id,client_id,service_name,environment,operation,stack_fingerprint,code_id,source_commit_sha"
    rows = _request(
        base_url,
        service_role_key,
        "POST",
        f"raphael_healthy_traces?on_conflict={quote(conflict_columns, safe=',')}",
        trace,
        "resolution=merge-duplicates,return=representation",
    )
    if not rows:
        raise RuntimeError("Supabase did not return the healthy trace row")

    lookup = _request(
        base_url,
        service_role_key,
        "GET",
        "raphael_healthy_traces?select=company_id,client_id,stack_fingerprint,code_id,source_file,source_line&"
        f"company_id=eq.{quote(company_id, safe='')}&client_id=eq.{quote(client_id, safe='')}",
    )
    assert any(row.get("stack_fingerprint") == stack_fingerprint for row in lookup)
    print(json.dumps({"company_id": company_id, "client_id": client_id, "healthy_trace_rows": len(lookup)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
