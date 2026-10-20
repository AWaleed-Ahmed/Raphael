"""Graph localization node tests."""

from __future__ import annotations

import pytest

from raphael_agent.graph import initial_run_state
from raphael_agent.graph.nodes import node_localize
from raphael_agent.localization.supabase_catalog import HealthyTraceComparison


@pytest.fixture(autouse=True)
def authorized_scope(monkeypatch):
    monkeypatch.setenv("RAPHAEL_HEALTHY_CATALOG_ENABLED", "1")
    monkeypatch.setenv("RAPHAEL_COMPANY_ID", "company-a")
    monkeypatch.setenv("RAPHAEL_CLIENT_ID", "client-a")
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "0")


class FakeCatalog:
    def get_client(self, client_id):
        return {"company_id": "company-a", "client_id": client_id, "client_name": "Acme", "status": "active"}

    def list_healthy_traces(self, **kwargs):
        return [{
            "healthy_trace_id": "healthy-1",
            "repository": "acme/checkout", "verified_healthy": True,
            "company_id": "company-a",
            "client_id": "client-a",
            "service_name": "checkout-api",
            "environment": "staging",
            "operation": "POST /orders",
            "normalized_stack_trace": "healthy",
            "stack_fingerprint": "healthy-fp",
            "span_sequence": ["POST /orders", "payment.authorize"],
            "source_file": "app/payment_client.py",
            "source_line": 84,
            "source_symbol": "authorize",
        }]

    def compare_unhealthy_trace(self, *args, **kwargs):
        return [HealthyTraceComparison(
            healthy_trace_id="healthy-1",
            same_scope=True,
            fingerprint_match=False,
            stack_diverged=True,
            span_diverged=True,
            first_divergent_span_index=1,
            source_anchor_match=True,
            confidence=1.0,
            reasons=["synthetic"],
        )]


class FakeImageCatalog(FakeCatalog):
    def list_healthy_traces(self, **kwargs):
        return [{
            "healthy_trace_id": "healthy-image-1",
            "company_id": "company-a",
            "client_id": "client-a",
            "service_name": "payments",
            "environment": "staging",
            "operation": "deploy",
            "repository": "acme/payments",
            "verified_healthy": True,
            "is_last_known_good": True,
            "source_commit_sha": "a" * 40,
            "runtime_identity": {
                "resource_kind": "Deployment",
                "resource_name": "payments-api",
                "container_images": {
                    "api": "ghcr.io/acme/payments-api@sha256:" + "b" * 64,
                },
            },
            "normalized_stack_trace": "healthy",
            "stack_fingerprint": "healthy-image-fp",
            "span_sequence": [],
        }]


def test_localize_node_reads_baseline_and_emits_candidates(monkeypatch):
    monkeypatch.delenv("RAPHAEL_MODEL_ENABLED", raising=False)
    import raphael_agent.graph.nodes as nodes

    monkeypatch.setattr(nodes, "SupabaseHealthyCatalogStore", lambda: FakeCatalog())
    state = initial_run_state({
        "run_id": "localize-test",
        "tenant_id": "local-dev",
        "client_id": "client-a",
        "trigger": {"kind": "fixture"},
        "repository": {"owner": "acme", "name": "checkout"},
        "commit_sha": "abcdef1234567",
        "target_environment": "staging",
        "runtime_observation": {
            "service_name": "checkout-api",
            "environment": "staging",
            "operation": "POST /orders",
            "stack_trace": 'File "/app/payment_client.py", line 84, in authorize',
            "span_sequence": [{"name": "POST /orders"}, {"name": "payment.authorize", "error": True}],
        },
        "changed_diff_hunks": [{"path": "app/payment_client.py", "start_line": 80, "end_line": 90, "diff_hunk": "- old\n+ new"}],
    }, sandbox_mode="recorded_stub")

    updates = node_localize(state)

    assert updates["localization_result"]["status"] == "completed"
    assert updates["localization_result"]["baseline_count"] == 1
    assert updates["healthy_trace_comparisons"][0]["source_anchor_match"] is True
    assert updates["fault_candidates"]
    assert updates["fault_candidates"][0]["path"] == "app/payment_client.py"
    for capability in ("incident_similarity", "candidate_ranker"):
        assert updates["model_results"][capability] == {
            "available": False, "reason": "disabled_by_environment",
        }


def test_localize_node_records_image_provenance_from_matching_last_good(monkeypatch):
    import raphael_agent.graph.nodes as nodes

    monkeypatch.setattr(nodes, "SupabaseHealthyCatalogStore", lambda: FakeImageCatalog())
    state = initial_run_state({
        "run_id": "image-provenance-localize",
        "tenant_id": "local-dev",
        "client_id": "client-a",
        "trigger": {"kind": "fixture"},
        "repository": {"owner": "acme", "name": "payments"},
        "commit_sha": "c" * 40,
        "target_environment": "staging",
        "runtime_observation": {"service_name": "payments", "environment": "staging", "operation": "deploy"},
    }, sandbox_mode="recorded_stub")
    state["failure_signature"] = {
        "class": "bad_image_reference",
        "key": "bad_image:payments-api:ghcr.io/acme/payments-api:does-not-exist",
        "normalized": {
            "resource_kind": "Deployment",
            "resource_name": "payments-api",
            "container": "api",
            "attributes": {"image": "ghcr.io/acme/payments-api:does-not-exist", "image_pull_cause": "not_found", "evidence_source": "runtime", "owner_verified": True, "container_type": "regular"},
        },
    }

    updates = node_localize(state)

    replacement = updates["localization_result"]["approved_image_replacement"]
    assert replacement["container_name"] == "api"
    assert replacement["source"]["healthy_trace_id"] == "healthy-image-1"


def test_localize_node_rejects_baseline_when_observation_and_target_environments_conflict(monkeypatch):
    import raphael_agent.graph.nodes as nodes

    class ProductionCatalog(FakeImageCatalog):
        def list_healthy_traces(self, **kwargs):
            rows = super().list_healthy_traces(**kwargs)
            rows[0]["environment"] = kwargs["environment"]
            return rows

    monkeypatch.setattr(nodes, "SupabaseHealthyCatalogStore", lambda: ProductionCatalog())
    state = initial_run_state({
        "run_id": "image-provenance-environment-mismatch",
        "tenant_id": "local-dev",
        "client_id": "client-a",
        "trigger": {"kind": "fixture"},
        "repository": {"owner": "acme", "name": "payments"},
        "commit_sha": "c" * 40,
        "target_environment": "staging",
        "runtime_observation": {
            "service_name": "payments",
            "environment": "production",
            "operation": "deploy",
        },
    }, sandbox_mode="recorded_stub")
    state["failure_signature"] = {
        "class": "bad_image_reference",
        "key": "bad_image:payments-api:ghcr.io/acme/payments-api:does-not-exist",
        "normalized": {
            "resource_kind": "Deployment",
            "resource_name": "payments-api",
            "container": "api",
            "attributes": {"image": "ghcr.io/acme/payments-api:does-not-exist", "image_pull_cause": "not_found", "evidence_source": "runtime", "owner_verified": True, "container_type": "regular"},
        },
    }

    updates = nodes.node_localize(state)

    assert updates["localization_result"]["environment"] == "production"
    assert "approved_image_replacement" not in updates["localization_result"]


def _scoped_state():
    return initial_run_state({
        'run_id': 'scope-control', 'tenant_id': 'test', 'client_id': 'client-a',
        'company_id': 'company-a', 'trigger': {'kind': 'fixture'},
        'repository': {'owner': 'acme', 'name': 'checkout'}, 'commit_sha': 'a' * 40,
        'target_environment': 'staging',
        'runtime_observation': {'service_name': 'checkout-api', 'environment': 'staging', 'operation': 'POST /orders'},
    }, sandbox_mode='recorded_stub')


@pytest.mark.parametrize('field,value', [('company_id', 'other'), ('client_id', 'client-b')])
def test_request_scope_cannot_override_backend_scope(monkeypatch, field, value):
    import raphael_agent.graph.nodes as nodes
    def forbidden():
        raise AssertionError('scope rejection must precede catalog access')
    monkeypatch.setattr(nodes, 'SupabaseHealthyCatalogStore', forbidden)
    state = _scoped_state()
    state[field] = value
    result = nodes.node_localize(state)
    assert result['localization_result']['reason'] == 'catalog_scope_rejected'
    assert not result['fault_candidates']
    assert 'model_results' not in result


@pytest.mark.parametrize('field,value', [('company_id', 'other'), ('client_id', 'client-b'),
    ('service_name', 'other'), ('environment', 'production'), ('operation', 'other'), ('repository', 'other/repo')])
def test_wrong_scope_rows_cannot_enter_graph_outputs(monkeypatch, field, value):
    import json
    import raphael_agent.graph.nodes as nodes
    class PoisonedCatalog(FakeCatalog):
        def list_healthy_traces(self, **kwargs):
            return [{**super().list_healthy_traces(**kwargs)[0], field: value,
                     'healthy_trace_id': 'rejected-private-trace',
                     'route_handler_map': {'/': {'path': 'rejected-private-source.py'}}}]
    monkeypatch.setattr(nodes, 'SupabaseHealthyCatalogStore', PoisonedCatalog)
    result = nodes.node_localize(_scoped_state())
    assert result['localization_result']['baseline_count'] == 0
    assert 'rejected-private' not in json.dumps(result)
    assert not result['healthy_trace_comparisons']


def test_catalog_default_off_and_missing_scope_are_zero_access(monkeypatch):
    import raphael_agent.graph.nodes as nodes
    def forbidden():
        raise AssertionError('catalog reached')
    monkeypatch.setattr(nodes, 'SupabaseHealthyCatalogStore', forbidden)
    monkeypatch.delenv('RAPHAEL_HEALTHY_CATALOG_ENABLED')
    assert nodes.node_localize(_scoped_state())['localization_result']['reason'] == 'catalog_disabled'
    monkeypatch.setenv('RAPHAEL_HEALTHY_CATALOG_ENABLED', '1')
    monkeypatch.delenv('RAPHAEL_COMPANY_ID')
    assert nodes.node_localize(_scoped_state())['localization_result']['reason'] == 'catalog_scope_rejected'


@pytest.mark.parametrize('registry_change', [{'company_id': 'other'}, {'client_id': 'other'}, {'status': 'suspended'}])
def test_registry_ownership_and_active_status_are_required(monkeypatch, registry_change):
    import raphael_agent.graph.nodes as nodes
    class RejectedRegistry(FakeCatalog):
        def get_client(self, client_id):
            return {**super().get_client(client_id), **registry_change}
        def list_healthy_traces(self, **kwargs):
            raise AssertionError('rejected registry must not query baselines')
    monkeypatch.setattr(nodes, 'SupabaseHealthyCatalogStore', RejectedRegistry)
    result = nodes.node_localize(_scoped_state())
    assert result['localization_result']['status'] == 'error'
    assert not result['fault_candidates'] and not result['healthy_trace_comparisons']


@pytest.mark.parametrize('field', ['company_id', 'client_id'])
def test_nested_observation_scope_cannot_spoof_tenant(monkeypatch, field):
    import raphael_agent.graph.nodes as nodes
    state = _scoped_state()
    state['runtime_observation'][field] = 'other'
    def forbidden():
        raise AssertionError('catalog reached')
    monkeypatch.setattr(nodes, 'SupabaseHealthyCatalogStore', forbidden)
    assert nodes.node_localize(state)['localization_result']['reason'] == 'catalog_scope_rejected'
