"""Provider-neutral healthy catalog comparison tests."""

from __future__ import annotations

from raphael_agent.localization.supabase_catalog import compare_trace_to_healthy


def test_compare_string_baseline_to_structured_error_span():
    healthy = {
        "healthy_trace_id": "healthy-1",
        "company_id": "company-a",
        "client_id": "client-a",
        "service_name": "checkout-api",
        "environment": "production",
        "operation": "POST /orders",
        "normalized_stack_trace": "payment_client.py:84:authorize|timeout",
        "stack_fingerprint": "healthy-fingerprint",
        "span_sequence": ["POST /orders", "payment.authorize"],
        "source_file": "src/payment_client.py",
        "source_line": 84,
        "source_symbol": "authorize",
    }
    unhealthy = {
        **{field: healthy[field] for field in (
            "company_id", "client_id", "service_name", "environment", "operation",
        )},
        "normalized_stack_trace": "payment_client.py:84:authorize|timeout|attempt=2",
        "stack_fingerprint": "unhealthy-fingerprint",
        "span_sequence": [
            {"name": "POST /orders"},
            {"name": "payment.authorize", "error": True},
        ],
        "source_file": "src/payment_client.py",
        "source_line": 84,
        "source_symbol": "authorize",
    }

    result = compare_trace_to_healthy(unhealthy, healthy)

    assert result.same_scope is True
    assert result.fingerprint_match is False
    assert result.stack_diverged is True
    assert result.span_diverged is True
    assert result.first_divergent_span_index == 1
    assert result.source_anchor_match is True
    assert result.confidence == 1.0


def test_compare_rejects_cross_client_baseline_as_same_scope():
    healthy = {
        "healthy_trace_id": "healthy-2",
        "company_id": "company-a",
        "client_id": "client-a",
        "service_name": "checkout-api",
        "environment": "production",
        "operation": "POST /orders",
        "normalized_stack_trace": "same",
        "stack_fingerprint": "same",
        "span_sequence": [],
    }
    unhealthy = {
        "company_id": "company-b",
        "client_id": "client-b",
        "service_name": "checkout-api",
        "environment": "production",
        "operation": "POST /orders",
        "normalized_stack_trace": "same",
        "stack_fingerprint": "same",
        "span_sequence": [],
    }

    result = compare_trace_to_healthy(unhealthy, healthy)

    assert result.same_scope is False
    assert "scope_mismatch" in result.reasons
    assert result.confidence == 0.0
