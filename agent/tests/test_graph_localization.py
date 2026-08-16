"""Graph localization node tests."""

from __future__ import annotations

from raphael_agent.graph import initial_run_state
from raphael_agent.graph.nodes import node_localize
from raphael_agent.localization.supabase_catalog import HealthyTraceComparison


class FakeCatalog:
    def get_client(self, client_id):
        return {"company_id": "company-a", "client_id": client_id, "client_name": "Acme"}

    def list_healthy_traces(self, **kwargs):
        return [{
            "healthy_trace_id": "healthy-1",
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


def test_localize_node_reads_baseline_and_emits_candidates(monkeypatch):
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
