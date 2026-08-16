"""Unit tests for the Fault Localization Engine (FLE), Healthy Catalog Store, and Interventions."""

from __future__ import annotations

import pytest

from raphael_agent.localization import (
    CandidateScorer,
    HealthyCatalogStore,
    SandboxInterventionController,
    extract_kubernetes_manifest_anchors,
    extract_route_to_handler_anchor,
    extract_stack_trace_anchors,
    extract_trace_divergence_anchor,
    resolve_deployment_identity,
)
from raphael_agent.schema_util import validate_agent


def test_multi_tenant_catalog_partitioning(tmp_path):
    """Verify that different companies and tenants querying the catalog get isolated baselines."""
    store = HealthyCatalogStore(storage_dir=tmp_path)

    # 1. Register baseline for Company A (Acme Corp)
    store.record_healthy_release(
        company_id="comp_100",
        client_id="cli_101",
        client_name="Acme Corp",
        tenant_id="acme-prod",
        service_name="checkout",
        environment="production",
        git_sha="111111111111",
        route_handler_maps={"POST /orders": {"path": "src/orders.py", "symbol": "create_order", "line": 50}},
        golden_trace_spans={"POST /orders": ["http_in", "validate", "charge", "persist"]},
    )

    # 2. Register baseline for Company B (Beta Inc)
    store.record_healthy_release(
        company_id="comp_200",
        client_id="cli_201",
        client_name="Beta Inc",
        tenant_id="beta-prod",
        service_name="checkout",
        environment="production",
        git_sha="222222222222",
        golden_trace_spans={"POST /orders": ["http_in", "auth", "dispatch"]},
    )

    # 3. Retrieve and assert isolation
    acme_entry = store.get_catalog_entry(
        company_id="comp_100",
        client_id="cli_101",
        tenant_id="acme-prod",
        service_name="checkout",
        environment="production",
    )
    assert acme_entry is not None
    assert acme_entry.git_sha == "111111111111"
    assert acme_entry.golden_trace_spans["POST /orders"] == ["http_in", "validate", "charge", "persist"]

    beta_entry = store.get_catalog_entry(
        company_id="comp_200",
        client_id="cli_201",
        tenant_id="beta-prod",
        service_name="checkout",
        environment="production",
    )
    assert beta_entry is not None
    assert beta_entry.git_sha == "222222222222"
    assert beta_entry.golden_trace_spans["POST /orders"] == ["http_in", "auth", "dispatch"]


def test_resolve_deployment_identity_from_oci_and_otel():
    """Verify OCI labels and OpenTelemetry resources are resolved into exact deployment identity."""
    labels = {
        "org.opencontainers.image.source": "acme/checkout-service",
        "org.opencontainers.image.revision": "7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b",
        "container.image.id": "sha256:4f89b1c2d3e4f5a6b7c8d9e0f1a2b3c4",
        "service.name": "checkout-api",
        "deployment.environment.name": "production",
    }
    identity = resolve_deployment_identity(labels)
    assert identity.service_name == "checkout-api"
    assert identity.environment == "production"
    assert identity.repository == "acme/checkout-service"
    assert identity.git_sha == "7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b"
    assert identity.image_digest == "sha256:4f89b1c2d3e4f5a6b7c8d9e0f1a2b3c4"


def test_stack_trace_framework_filtering_and_deepest_frame_priority():
    """Verify framework frames are stripped and deepest application frame gets highest confidence."""
    raw_trace = """
Traceback (most recent call last):
  File "/usr/lib/python3.12/site-packages/starlette/routing.py", line 62, in app
    response = await f(request)
  File "/usr/lib/python3.12/site-packages/uvicorn/protocols/http.py", line 120, in run
    await self.handle()
  File "/app/src/routes.py", line 51, in post_order
    return create_order(req)
  File "/app/src/checkout.py", line 122, in create_order
    return payment_authorize(req.body)
  File "/app/src/payment_client.py", line 84, in payment_authorize
    raise TimeoutError("Payment gateway timed out")
"""
    anchors = extract_stack_trace_anchors(raw_trace, evidence_ref="ev-stack-01")
    assert len(anchors) == 3  # Only the 3 app frames!
    # Rank 1: Deepest application frame
    assert anchors[0].file_path == "app/src/payment_client.py"
    assert anchors[0].line_number == 84
    assert anchors[0].symbol_name == "payment_authorize"
    assert anchors[0].confidence == 1.0

    # Rank 2: Caller
    assert anchors[1].file_path == "app/src/checkout.py"
    assert anchors[1].line_number == 122

    # Rank 3: Route entrypoint
    assert anchors[2].file_path == "app/src/routes.py"
    assert anchors[2].line_number == 51


def test_trace_divergence_identifies_first_erroneous_span():
    """Verify trace diffing identifies first divergent span, not the final propagated symptom."""
    golden_spans = ["http_route", "validate", "inventory_reserve", "payment_authorize", "persist_order"]
    
    # Failing trace where payment_authorize failed, so persist_order was never reached or errored
    failing_spans = [
        {"attributes": {"name": "http_route", "code.file.path": "src/routes.py", "code.line.number": 20}},
        {"attributes": {"name": "validate", "code.file.path": "src/validator.py", "code.line.number": 15}},
        {"attributes": {"name": "inventory_reserve", "code.file.path": "src/inventory.py", "code.line.number": 40}},
        {
            "attributes": {
                "name": "payment_authorize",
                "error": 1,
                "error.type": "TimeoutError",
                "code.file.path": "src/payment_client.py",
                "code.line.number": 84,
                "code.function.name": "payment_authorize",
            }
        },
        {"attributes": {"name": "error_handler", "error": 1, "code.file.path": "src/errors.py", "code.line.number": 10}},
    ]

    divergent_anchor = extract_trace_divergence_anchor(failing_spans, golden_spans)
    assert divergent_anchor is not None
    assert divergent_anchor.symbol_name == "payment_authorize"
    assert divergent_anchor.file_path == "src/payment_client.py"
    assert divergent_anchor.line_number == 84


def test_deterministic_candidate_scoring_and_schema_validation():
    """Verify deterministic candidate ranking formula and JSON schema validity."""
    scorer = CandidateScorer()

    anchors = [
        extract_stack_trace_anchors(
            'File "/app/src/payment_client.py", line 84, in payment_authorize\n  raise TimeoutError()',
            evidence_ref="ev-stack-01",
        )[0]
    ]

    changed_hunks = [
        {
            "path": "app/src/payment_client.py",
            "start_line": 80,
            "end_line": 95,
            "diff_hunk": "- timeout=10\n+ timeout=0.1",
        },
        {
            "path": "deploy/manifests/deployment.yaml",
            "start_line": 40,
            "end_line": 45,
            "diff_hunk": "- port: 80\n+ port: 8080",
        },
    ]

    candidates = scorer.generate_and_rank_candidates(
        repository="acme/checkout",
        git_sha="abcdef123456",
        anchors=anchors,
        changed_diff_hunks=changed_hunks,
        failure_class="dependency_timeout",
        first_divergent_anchor=anchors[0],
    )

    assert len(candidates) >= 1
    top = candidates[0]
    assert top.path == "app/src/payment_client.py"
    assert top.symbol == "payment_authorize"
    assert top.score >= 0.85  # Strong score from Anchor + Diff + Trace
    assert "stack_trace" in top.mapping_methods
    assert "deployment_diff" in top.mapping_methods
    assert "trace_divergence" in top.mapping_methods

    # Validate against JSON schema in contracts/agent/fault_candidate.json
    validate_agent("fault_candidate.json", top.to_dict())


def test_counterfactual_sandbox_intervention_and_delta_debugging():
    """Verify counterfactual candidate reversion proves causality across 3 validation runs."""
    controller = SandboxInterventionController(repeat_count=3)

    candidate = CandidateScorer().generate_and_rank_candidates(
        repository="acme/checkout",
        git_sha="abcdef123456",
        anchors=extract_stack_trace_anchors(
            'File "/app/src/payment_client.py", line 84, in payment_authorize\n  raise TimeoutError()'
        ),
        changed_diff_hunks=[{"path": "app/src/payment_client.py", "start_line": 80, "end_line": 95}],
    )[0]

    # Mock sandbox deploy function: fails on unpatched revision, succeeds when candidate patch applied
    def mock_sandbox_deploy(opts: dict) -> bool:
        patch = opts.get("patch")
        if patch and "revert:" in patch:
            return False  # Failure cured!
        return True  # Fails without patch

    res = controller.evaluate_candidate_causality(
        candidate,
        sandbox_deploy_fn=mock_sandbox_deploy,
    )

    assert res.is_causal is True
    assert res.runs_passed == 3
    assert res.final_state == "confirmed_fix"
    assert candidate.state == "confirmed_fix"

    # Delta debugging test: reduce 4 hunks to the single causal one
    all_hunks = ["hunk_1", "hunk_2", "hunk_causal", "hunk_4"]

    def delta_deploy(hunks: list[str]) -> bool:
        return "hunk_causal" in hunks  # only hunk_causal fixes the bug

    minimal = controller.delta_debug_minimize_hunks(all_hunks, delta_deploy)
    assert minimal == ["hunk_causal"]
