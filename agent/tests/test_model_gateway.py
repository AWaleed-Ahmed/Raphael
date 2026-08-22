"""Model input/output adapter tests."""

from __future__ import annotations

from raphael_agent.model_gateway import ModelGateway


def _state():
    return {
        "failure_fingerprint": "probe_port_mismatch:checkout:8080!=9090",
        "failure_signature": {
            "class": "probe_misconfiguration",
            "key": "probe_port_mismatch:checkout:8080!=9090",
            "normalized": {"reason": "ReadinessProbePortMismatch"},
        },
        "runtime_observation": {
            "service_name": "checkout",
            "operation": "GET /healthz",
            "span_sequence": ["request", "health"],
        },
        "evidence": [{"evidence_id": "ev-1", "summary": "probe port mismatch"}],
        "diagnosis": {"classification": {"failure_class": "probe_misconfiguration"}},
    }


def test_failure_input_adapter_and_diagnosis_merge():
    state = _state()
    gateway = ModelGateway()
    record = gateway._failure_record(state)
    assert record["normalized_reason"] == "ReadinessProbePortMismatch"
    assert record["fingerprint"].startswith("probe_port_mismatch:")
    prediction = {
        "failure_class": "probe_misconfiguration",
        "confidence": 0.93,
        "abstained": False,
        "rule_evidence": "normalized_reason:ReadinessProbePortMismatch",
    }
    merged = gateway.merge_diagnosis(
        {
            "classification": {"category": "unknown", "failure_class": "unknown"},
            "hypotheses": [], "selected_hypothesis_id": None, "confidence": 0.0,
            "confidence_threshold": 0.7, "supporting_evidence_ids": [],
            "analyzer": {"name": "test", "mode": "deterministic"},
            "diagnosed_at": "2026-08-16T00:00:00Z",
        },
        prediction, state,
    )
    assert merged["classification"]["failure_class"] == "probe_misconfiguration"
    assert merged["selected_hypothesis_id"] == "hyp-model-probe_misconfiguration"
    assert merged["analyzer"]["mode"] == "hybrid"


def test_candidate_output_adapter_preserves_fault_candidate_contract(monkeypatch):
    gateway = ModelGateway()
    candidates = [{
        "repository": "acme/checkout", "git_sha": "abcdef1234567",
        "path": "deploy/deployment.yaml", "line": 42,
        "symbol": "readinessProbe.httpGet.port",
        "candidate_type": "kubernetes_manifest", "score": 0.7,
        "mapping_methods": ["deployment_diff"], "evidence_refs": [],
        "diff_hunk": "- port: 9090\n+ port: 8080", "state": "localized",
    }]
    monkeypatch.setattr(gateway, "_invoke", lambda *args, **kwargs: {
        "candidates": [{
            "candidate_path": "deploy/deployment.yaml", "candidate_line": 42,
            "candidate_symbol": "readinessProbe.httpGet.port",
            "model_score": 0.88, "evidence_score": 0.75,
        }]
    })
    result = gateway.rank_candidates(_state(), candidates, [])
    assert result is not None
    assert result["candidates"][0]["score"] == 0.88
    assert result["candidates"][0]["path"] == "deploy/deployment.yaml"
    assert "historical_similarity" in result["candidates"][0]["mapping_methods"]


def test_patch_input_adapter_selects_bounded_template(monkeypatch):
    gateway = ModelGateway()
    monkeypatch.setattr(gateway, "_invoke", lambda *args, **kwargs: {
        "policy_allowed": True, "safe_template": "fix_probe_port_mismatch",
        "requires_sandbox_validation": True,
    })
    result = gateway.select_patch(_state())
    assert result["safe_template"] == "fix_probe_port_mismatch"
    assert result["requires_sandbox_validation"] is True
