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


def test_wrong_scope_never_gains_confidence_from_divergence():
    wrong = dict(company_id='other', client_id='b', service_name='s', environment='e', operation='o',
                 normalized_stack_trace='a', stack_fingerprint='a', span_sequence=['a'])
    current = {**wrong, 'company_id': 'correct', 'normalized_stack_trace': 'b',
               'stack_fingerprint': 'b', 'span_sequence': [{'name': 'b', 'error': True}]}
    assert compare_trace_to_healthy(current, wrong).confidence == 0


def test_backend_key_header_formats(monkeypatch):
    import io
    from raphael_agent.localization import supabase_catalog as catalog
    for key in ('sb_secret_fixture_only', 'eyJ.legacy.fixture'):
        seen = []
        def open_fixture(request, timeout):
            seen.append(request)
            return io.BytesIO(b'[]')
        monkeypatch.setattr(catalog, 'urlopen', open_fixture)
        catalog.SupabaseHealthyCatalogStore('https://project.example', key)._request('GET', 'raphael_clients')
        assert seen[0].get_header('Apikey') == key
        assert seen[0].get_header('Authorization') == (None if key.startswith('sb_secret_') else f'Bearer {key}')
        assert key not in seen[0].full_url


def test_error_bodies_and_transport_secrets_are_not_exposed(monkeypatch):
    import io
    import pytest
    from urllib.error import HTTPError, URLError
    from raphael_agent.localization import supabase_catalog as catalog
    for error, code in [(HTTPError('https://project.example', 403, 'private-body', {}, io.BytesIO(b'private-body')), 'supabase_http_403'),
                        (URLError('private-body'), 'supabase_transport_error')]:
        def fail(*args, **kwargs):
            raise error
        monkeypatch.setattr(catalog, 'urlopen', fail)
        with pytest.raises(catalog.SupabaseCatalogError, match=code) as caught:
            catalog.SupabaseHealthyCatalogStore('https://project.example', 'fixture')._request('GET', 'raphael_clients')
        assert 'private-body' not in str(caught.value)


def test_malformed_and_oversized_catalog_responses_fail_closed(monkeypatch):
    import io
    import pytest
    from raphael_agent.localization import supabase_catalog as catalog
    for raw in (b'not-json', b'{}', b'[null]', b'x' * (catalog.MAX_CATALOG_BYTES + 1)):
        monkeypatch.setattr(catalog, 'urlopen', lambda *a, **kw: io.BytesIO(raw))
        with pytest.raises(catalog.SupabaseCatalogError):
            catalog.SupabaseHealthyCatalogStore('https://project.example', 'fixture')._request('GET', 'raphael_clients')


def test_service_role_rows_are_rechecked_for_scope(monkeypatch):
    import pytest
    from raphael_agent.localization import supabase_catalog as catalog
    good = dict(company_id='a', client_id='a1', service_name='s', environment='test', operation='o', verified_healthy=True)
    store = catalog.SupabaseHealthyCatalogStore('https://project.example', 'fixture')
    monkeypatch.setattr(store, '_request', lambda *a: [good, {**good, 'client_id': 'a2'}, {**good, 'company_id': 'b'},
                                                     {**good, 'operation': 'other'}, {**good, 'verified_healthy': False}])
    assert store.list_healthy_traces(company_id='a', client_id='a1', service_name='s', environment='test', operation='o') == [good]
    with pytest.raises(catalog.SupabaseCatalogError, match='catalog_scope_missing'):
        store.list_healthy_traces(company_id='', client_id='a1', service_name='s', environment='test')
