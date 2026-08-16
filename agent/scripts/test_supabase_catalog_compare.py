#!/usr/bin/env python3
"""Live healthy-vs-unhealthy Supabase catalog comparison smoke test."""

from __future__ import annotations

import json
import os
import sys

from raphael_agent.localization.supabase_catalog import SupabaseCatalogError, SupabaseHealthyCatalogStore


def main() -> int:
    try:
        store = SupabaseHealthyCatalogStore()
        client_id = os.environ.get("RAPHAEL_CLIENT_ID", "demo-client")
        client = store.get_client(client_id)
        if not client:
            raise SupabaseCatalogError(f"client not found: {client_id}")
        company_id = str(client["company_id"])
        baselines = store.list_healthy_traces(
            company_id=company_id,
            client_id=client_id,
            service_name=os.environ.get("RAPHAEL_TEST_SERVICE", "checkout-api"),
            environment=os.environ.get("RAPHAEL_TEST_ENVIRONMENT", "staging"),
            operation=os.environ.get("RAPHAEL_TEST_OPERATION", "POST /orders"),
        )
        if not baselines:
            raise SupabaseCatalogError("no healthy baseline found for the requested scope")
        healthy = baselines[0]
        unhealthy = {
            "operation": healthy.get("operation"),
            "normalized_stack_trace": str(healthy.get("normalized_stack_trace") or "") + "|unhealthy",
            "stack_fingerprint": "synthetic-unhealthy-fingerprint",
            "span_sequence": [
                {"name": "POST /orders"},
                {"name": "payment.authorize", "error": True},
            ],
            "source_file": healthy.get("source_file"),
            "source_line": healthy.get("source_line"),
            "source_symbol": healthy.get("source_symbol"),
        }
        comparisons = store.compare_unhealthy_trace(
            unhealthy,
            company_id=company_id,
            client_id=client_id,
            service_name=str(healthy["service_name"]),
            environment=str(healthy["environment"]),
            operation=str(healthy["operation"]),
        )
        result = comparisons[0] if comparisons else None
        if not result or not result.same_scope or not result.stack_diverged or not result.span_diverged:
            raise SupabaseCatalogError(f"comparison did not detect the synthetic failure: {result}")
        print(json.dumps({
            "healthy_trace_id": result.healthy_trace_id,
            "same_scope": result.same_scope,
            "stack_diverged": result.stack_diverged,
            "span_diverged": result.span_diverged,
            "first_divergent_span_index": result.first_divergent_span_index,
            "source_anchor_match": result.source_anchor_match,
        }, indent=2))
        return 0
    except SupabaseCatalogError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
