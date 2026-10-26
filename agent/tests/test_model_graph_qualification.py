"""Real artifact/graph proofs; prediction replacements appear only in fault controls."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from raphael_agent.graph import nodes
from raphael_agent.model_gateway import ModelGateway, model_error
from scripts.qualify_model_graph import (
    OWNER,
    Catalog,
    baseline_for,
    configured,
    qualify,
    state_for,
)

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "agent/tests/fixtures/local_inference"


def test_public_fixtures_and_compiled_graph_use_real_models(tmp_path: Path) -> None:
    report = qualify(ROOT / "models", CASES, tmp_path / "proof")
    assert sum(row["cases"] for row in report["models"].values()) == 251
    assert all(row["learned_execution"] > 0 for row in report["models"].values())
    assert report["compiled_graph"]["status"] == "success_draft_pr_ready"
    outputs = report["compiled_graph"]["model_results"]
    assert outputs["trace_anomaly"]["baseline_status"] == "valid"
    assert outputs["patch_selector"]["requires_sandbox_validation"]
    records = [
        json.loads(line)
        for line in (tmp_path / "proof/cases.jsonl").read_text().splitlines()
    ]
    assert all(row["source"]["url"].startswith("https://") for row in records)
    assert all(
        row["audit"] for row in records if row["layer"] == "production_graph_node"
    )
    assert any(
        row["output"] and row["output"].get("execution_source") == "abstention"
        for row in records
    )


@pytest.mark.parametrize(
    "damage", ["missing", "valid", "foreign", "zero", "nan", "unhealthy", "unverified"]
)
def test_real_trace_baseline_handling(tmp_path: Path, damage: str) -> None:
    case = json.loads((CASES / "trace_anomaly.jsonl").read_text().splitlines()[0])
    with Catalog() as catalog, configured(catalog, ROOT / "models", tmp_path):
        state = state_for(case)
        baseline = baseline_for(state, 10)
        if damage == "foreign":
            baseline["company_id"] = "other-company"
        elif damage == "zero":
            baseline["latency_ms"] = 0
        elif damage == "nan":
            baseline["latency_ms"] = float("nan")
        elif damage == "unhealthy":
            baseline["status_code"] = 500
        elif damage == "unverified":
            baseline["verified_healthy"] = False
        result = ModelGateway().trace_anomaly(
            state, baseline=None if damage == "missing" else baseline
        )
        assert result and result["learned_execution"]
        assert result["baseline_status"] == (
            damage if damage in {"missing", "valid"} else "unsuitable"
        )
        state["healthy_trace_comparisons"] = [{**baseline, "same_scope": True}]
        assert ModelGateway().trace_anomaly(state)["baseline_status"] == "missing"


@pytest.mark.parametrize(
    "method,result",
    [
        (
            "classify_failure",
            {
                "confidence": float("nan"),
                "abstained": False,
                "failure_class": "probe_misconfiguration",
            },
        ),
        (
            "classify_failure",
            {"confidence": 0.9, "abstained": False, "failure_class": "invented"},
        ),
        (
            "classify_failure",
            {"confidence": 1.1, "abstained": False, "failure_class": "healthy"},
        ),
        ("classify_failure", []),
        (
            "detect_trace",
            {
                "is_anomaly": True,
                "abstained": False,
                "anomaly_probability": float("inf"),
                "threshold": 0.2,
            },
        ),
        (
            "detect_trace",
            {
                "is_anomaly": "true",
                "abstained": False,
                "anomaly_probability": 0.5,
                "threshold": 0.2,
            },
        ),
        (
            "rank_candidates",
            {
                "candidates": [
                    {
                        "candidate_path": "invented.py",
                        "model_score": 0.9,
                        "evidence_score": 0.9,
                        "learned_score": 0.9,
                    }
                ]
            },
        ),
        (
            "select_patch",
            {
                "policy_allowed": True,
                "safe_template": "restore_configmap_key",
                "allowed_probability": 0.9,
                "template_confidence": 0.9,
                "requires_sandbox_validation": False,
            },
        ),
        (
            "select_patch",
            {
                "policy_allowed": True,
                "safe_template": "restore_configmap_key",
                "allowed_probability": True,
                "template_confidence": 0.9,
                "requires_sandbox_validation": True,
            },
        ),
        (
            "retrieve_incidents",
            {"results": [{"similarity": 0.9, "company_id": "foreign"}]},
        ),
    ],
)
def test_bad_model_outputs_refuse_suggestions(
    monkeypatch: pytest.MonkeyPatch, method: str, result: Any
) -> None:
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway()
    gateway._predict_module = SimpleNamespace(
        **{method: lambda *args, **kwargs: result}
    )
    payload = [{"candidate_path": "actual.py"}] if method == "rank_candidates" else {}
    assert gateway._invoke(method, payload) is None
    assert model_error(gateway) == "invalid_model_output"


@pytest.mark.parametrize(
    "confidence", [float("nan"), float("inf"), -1, 1.01, True, "0.9"]
)
def test_merge_rejects_invalid_confidence(confidence: Any) -> None:
    diagnosis = {
        "classification": {"category": "unknown"},
        "selected_hypothesis_id": None,
    }
    before = deepcopy(diagnosis)
    result = ModelGateway.merge_diagnosis(
        diagnosis,
        {
            "confidence": confidence,
            "failure_class": "probe_misconfiguration",
            "abstained": False,
        },
        {},
    )
    assert result == before


def test_unknown_patch_family_cannot_reach_private_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway()
    gateway._predict_module = SimpleNamespace(
        select_patch=lambda *args: {
            "policy_allowed": True,
            "safe_template": "disable_authentication",
            "allowed_probability": 0.99,
            "template_confidence": 0.99,
            "requires_sandbox_validation": True,
            "learned_execution": True,
        }
    )
    result = gateway.select_patch({})
    assert result and not result["policy_allowed"]
    assert result["safe_template"] is None
    assert result["reason"] == "unsupported_template"


@pytest.mark.parametrize("mode", ["disabled", "missing"])
def test_graph_audit_distinguishes_disabled_and_unavailable(
    tmp_path: Path, mode: str
) -> None:
    case = json.loads((CASES / "trace_anomaly.jsonl").read_text().splitlines()[0])
    with Catalog() as catalog, configured(catalog, ROOT / "models", tmp_path):
        import os

        if mode == "disabled":
            os.environ["RAPHAEL_MODEL_ENABLED"] = "0"
        else:
            os.environ["RAPHAEL_MODEL_ROOT"] = str(tmp_path / "absent")
        state = state_for(case)
        events = state["audit_events"]
        source = "disabled" if mode == "disabled" else "unavailable_fallback"
        assert any("source=" + source in event.get("detail", "") for event in events)
        assert state["model_results"]["trace_anomaly"]["available"] is False


def test_real_classifier_ood_abstains_at_graph_gate(tmp_path: Path) -> None:
    case = {
        "input": {"evidence_text": "unrecognized observation", "fingerprint": "unseen"},
        "source": {
            "url": "https://example.invalid/fault-control",
            "dataset": "explicit OOD control",
        },
    }
    with Catalog() as catalog, configured(catalog, ROOT / "models", tmp_path):
        state = state_for(case)
        state["issue_title"] = "unrecognized observation"
        state["workspace_path"] = None
        updates = nodes.node_diagnose(state)
        prediction = updates["model_results"]["failure_classifier"]
        assert prediction["learned_execution"] and prediction["abstained"]
        assert prediction["execution_source"] == "abstention"
        assert updates["terminal_reason"] == "low_confidence"


def test_real_graph_ranking_preserves_generated_evidence(tmp_path: Path) -> None:
    import os

    from raphael_agent.graph import initial_run_state

    state = initial_run_state(
        {
            **OWNER,
            "run_id": "canonical-control",
            "trigger": {"kind": "fixture"},
            "repository": {"owner": "proof-source", "name": "raphael-e2e-fixture"},
            "commit_sha": "a" * 40,
            "workspace_path": str(
                ROOT / "agent/fixtures/scenarios/probe_port_mismatch"
            ),
            "manifests": {"path": "deploy/manifests"},
        },
        sandbox_mode="recorded_stub",
    )
    state.update(
        status="running",
        failure_signature={
            "class": "probe_misconfiguration",
            "key": "probe_port_mismatch",
            "normalized": {"reason": "ReadinessProbePortMismatch"},
        },
    )
    with Catalog() as catalog, configured(catalog, ROOT / "models", tmp_path):
        os.environ["RAPHAEL_MODEL_ENABLED"] = "0"
        deterministic = nodes.node_localize(state)["fault_candidates"]
        os.environ["RAPHAEL_MODEL_ENABLED"] = "1"
        learned = nodes.node_localize(state)["fault_candidates"]
        assert deterministic and learned
        without_score = lambda rows: sorted(
            [repr({k: v for k, v in row.items() if k != "score"}) for row in rows]
        )
        assert without_score(deterministic) == without_score(learned)


def test_runtime_error_falls_back_without_exposing_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")

    def broken(*args: Any) -> None:
        raise RuntimeError("private arbitrary details")

    gateway = ModelGateway()
    gateway._predict_module = SimpleNamespace(classify_failure=broken)
    assert gateway.classify_failure({}) is None
    assert model_error(gateway) == "RuntimeError"
