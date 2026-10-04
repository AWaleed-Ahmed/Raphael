"""Graph-level Phase 2 behavior tests."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from raphael_agent.graph import initial_run_state, run_stub_graph
from raphael_agent.graph.nodes import node_diagnose, node_patch, node_reproduce, node_secret_coverage_gate, node_validate
from raphael_agent.ingest import normalize_failed_run_event
from raphael_agent.schema_util import for_run_record_validation, validate_agent

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
FIXTURE = AGENT_ROOT / "fixtures" / "failed_run_event.json"
WORKSPACE = REPO_ROOT / "agent" / "fixtures" / "scenarios" / "probe_port_mismatch"


def _seed(**overrides: Any) -> dict:
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["workspace_path"] = str(WORKSPACE)
    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = str(WORKSPACE)
    seed["manifests"] = event.get("manifests")
    seed.update(overrides)
    return seed


def test_happy_path_recorded_stub_probe(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    initial = initial_run_state(_seed(), sandbox_mode="recorded_stub")
    final = run_stub_graph(initial)
    validate_agent("run_record.json", for_run_record_validation(final))
    assert final["status"] == "success_draft_pr_ready"
    assert final["diagnosis"]["classification"]["failure_class"] == "probe_misconfiguration"
    assert final["result_id"]
    assert final["pull_request_url"]
    assert final.get("publish", {}).get("ok") is True
    patch_files = (final.get("candidate_patches") or [{}])[0].get("files") or []
    assert patch_files
    # Prefer real file fix when workspace is present
    assert any("port: 8080" in (f.get("content") or "") for f in patch_files)


def test_low_confidence_escalates(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD", "0.99")
    state = initial_run_state(_seed(), sandbox_mode="recorded_stub")
    # Replace evidence with vague content and clear workspace so analyzers miss
    state["workspace_path"] = None
    state["manifests"] = None
    state["evidence"] = [
        {
            "evidence_id": "ev-vague",
            "kind": "other",
            "source": {"system": "fixture", "ref": "t"},
            "summary": "unclear",
            "content_excerpt": "something odd happened",
            "redacted": True,
            "provenance": {"collector": "test", "query": "t"},
            "collected_at": "2026-08-10T12:00:00Z",
        }
    ]
    updates = node_diagnose(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "low_confidence"
    assert updates.get("escalation_report")


def test_secret_required_block_preserves_specific_terminal_reason(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    state = initial_run_state(_seed(), sandbox_mode="recorded_stub")
    state["workspace_path"] = None
    state["evidence"] = [
        {
            "evidence_id": "ev-block",
            "kind": "other",
            "source": {"system": "fixture", "ref": "t"},
            "summary": "secret",
            "content_excerpt": "This failure requires production secret values",
            "redacted": True,
            "provenance": {"collector": "test", "query": "t"},
            "collected_at": "2026-08-10T12:00:00Z",
        }
    ]
    updates = node_diagnose(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "production_secret_required"
    assert updates["escalation_report"]["reason_code"] == "production_secret_required"


def test_secret_coverage_gate_escalates_before_patch_for_required_gap():
    state = initial_run_state(_seed(), sandbox_mode="live")
    state["secret_coverage"] = {
        "format_version": 1,
        "complete": True,
        "truncated": False,
        "references": [{"workload_kind": "Deployment", "workload_name": "api", "namespace": "sandbox", "source": "secretKeyRef", "secret_name": "payments-db", "key": "PASSWORD", "optional": False, "status": "missing_key"}],
    }

    updates = node_secret_coverage_gate(state)

    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "unresolved_secret_dependency"
    assert updates["escalation_report"]["reason_code"] == "unresolved_secret_dependency"
    validate_agent("escalation_report.json", updates["escalation_report"])


def test_secret_coverage_gate_allows_covered_and_optional_missing_references():
    state = initial_run_state(_seed(), sandbox_mode="live")
    state["secret_coverage"] = {
        "format_version": 1,
        "complete": True,
        "truncated": False,
        "references": [
            {"workload_kind": "Deployment", "workload_name": "api", "namespace": "sandbox", "source": "secretKeyRef", "secret_name": "payments-db", "key": "DATABASE_URL", "optional": False, "status": "covered"},
            {"workload_kind": "Deployment", "workload_name": "api", "namespace": "sandbox", "source": "envFrom.secretRef", "secret_name": "optional-db", "optional": True, "status": "missing_object"},
        ],
    }

    assert node_secret_coverage_gate(state) == {}


def test_secret_coverage_gate_does_not_treat_unknown_as_a_missing_dependency():
    state = initial_run_state(_seed(), sandbox_mode="live")

    updates = node_secret_coverage_gate(state)

    assert updates == {}

    state["secret_coverage"] = {
        "format_version": 1,
        "complete": False,
        "truncated": True,
        "references": [{"namespace": "sandbox", "source": "secretKeyRef", "optional": False, "status": "unknown"}],
    }
    assert node_secret_coverage_gate(state) == {}

    state["secret_coverage"]["format_version"] = 2
    assert node_secret_coverage_gate(state) == {}


def test_live_reproduction_preserves_secret_coverage_report(monkeypatch):
    report = {"format_version": 1, "complete": True, "truncated": False, "references": []}

    class FakeClient:
        def create_sandbox(self, _body):
            return {"sandbox_id": "sb-secret"}

        def deploy_revision(self, _sandbox_id, _body):
            return {"fidelity": {"secret_coverage": report}}

        def observe_failure(self, _sandbox_id, _body):
            return {"signature": {"reproduced": True, "key": "fixture"}}

    monkeypatch.setattr("raphael_agent.graph.nodes.SandboxClient", FakeClient)
    monkeypatch.setattr("raphael_agent.graph.nodes.secret_fixture_args", lambda: {})
    state = initial_run_state(_seed(), sandbox_mode="live")

    updates = node_reproduce(state)

    assert updates["secret_coverage"] == report


@pytest.mark.parametrize("change", [
    {"truncated": True},
    {"format_version": True},
    {"references": [{"status": "missing_key"}]},
    {"references": [{"workload_kind": "Pod", "workload_name": "app", "namespace": "sandbox", "source": "secretKeyRef", "optional": False, "status": "unknown"}]},
])
def test_contradictory_or_malformed_coverage_cannot_trigger_refusal(change):
    state = initial_run_state(_seed(), sandbox_mode="live")
    state["secret_coverage"] = {
        "format_version": 1, "complete": True, "truncated": False,
        "references": [{"workload_kind": "Pod", "workload_name": "app", "namespace": "sandbox", "source": "secretKeyRef", "secret_name": "db", "key": "URL", "optional": False, "status": "missing_key"}],
        **change,
    }
    assert node_secret_coverage_gate(state) == {}


def test_direct_patch_entry_respects_secret_coverage_before_model_calls():
    state = initial_run_state(_seed(), sandbox_mode="live")
    state["secret_coverage"] = {
        "format_version": 1, "complete": True, "truncated": False,
        "references": [{"workload_kind": "Pod", "workload_name": "app", "namespace": "sandbox", "source": "secretKeyRef", "secret_name": "db", "key": "URL", "optional": False, "status": "missing_key"}],
    }
    with patch("raphael_agent.graph.nodes.ModelGateway") as gateway:
        updates = node_patch(state)
    assert updates["terminal_reason"] == "unresolved_secret_dependency"
    gateway.assert_not_called()
    assert state["attempt_count"]["patch"] == 0


def test_available_structural_coverage_precedes_classifier_and_low_confidence():
    state = initial_run_state(_seed(), sandbox_mode="connector")
    state["secret_coverage"] = {
        "format_version": 1, "complete": True, "truncated": False,
        "references": [{"workload_kind": "Pod", "workload_name": "app", "namespace": "sandbox", "source": "secretKeyRef", "secret_name": "db", "key": "URL", "optional": False, "status": "missing_key"}],
    }
    diagnosis = {"classification": {"category": "unsupported"}, "hypotheses": [], "confidence": 0.1}
    with patch("raphael_agent.graph.nodes.diagnose", return_value=diagnosis), patch("raphael_agent.graph.nodes.ModelGateway") as gateway:
        updates = node_diagnose(state)
    assert updates["terminal_reason"] == "unresolved_secret_dependency"
    gateway.assert_not_called()


def test_patch_budget_exhaust(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_MAX_PATCH_ATTEMPTS", "1")
    state = initial_run_state(_seed(), sandbox_mode="recorded_stub")
    state["status"] = "running"
    state["reproduction_result"] = {
        "reproduced": True,
        "signature_key": "probe_port_mismatch:payments-api:8080!=9090",
    }
    state["failure_signature"] = {
        "class": "probe_misconfiguration",
        "key": "probe_port_mismatch:payments-api:8080!=9090",
        "normalized": {
            "reason": "x",
            "resource_kind": "Deployment",
            "resource_name": "payments-api",
        },
        "reproduced": True,
        "evidence_refs": [{"kind": "k8s_event", "id": "e"}],
        "observed_at": "2026-08-10T12:00:00Z",
    }
    state["diagnosis"] = {
        "selected_hypothesis_id": "hyp-probe-port",
        "classification": {
            "category": "supported",
            "failure_class": "probe_misconfiguration",
        },
        "hypotheses": [
            {
                "hypothesis_id": "hyp-probe-port",
                "rank": 1,
                "statement": "probe",
                "confidence": 0.9,
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
            }
        ],
        "confidence": 0.9,
        "confidence_threshold": 0.7,
        "supporting_evidence_ids": [],
        "analyzer": {"name": "t", "mode": "deterministic"},
        "diagnosed_at": "2026-08-10T12:00:00Z",
    }
    state["attempt_count"] = {"diagnosis": 1, "patch": 1}
    updates = node_patch(state)
    assert updates["status"] == "escalated"
    assert updates["terminal_reason"] == "budget_exhausted"


def test_validate_retry_routes_to_patch(monkeypatch):
    monkeypatch.setenv("RAPHAEL_MAX_PATCH_ATTEMPTS", "3")
    state = initial_run_state(_seed(), sandbox_mode="live")
    state["status"] = "running"
    state["sandbox_id"] = "sb-test"
    state["failure_signature"] = {"normalized": {"resource_kind": "Deployment", "resource_name": "worker-api"}}
    state["attempt_count"] = {"diagnosis": 1, "patch": 1}
    state["active_patch_id"] = "patch-1"
    state["candidate_patches"] = [
        {
            "patch_id": "patch-1",
            "attempt": 1,
            "hypothesis_id": "hyp-probe-port",
            "files": [
                {
                    "path": "deploy/manifests/broken.yaml",
                    "action": "modify",
                    "content": "x: 1\n",
                }
            ],
            "rationale": {"summary": "t", "evidence_ids": []},
            "policy_status": "allowed",
            "created_at": "2026-08-10T12:00:00Z",
            "sandbox_deploy_hint": {
                "manifests_path": "deploy/manifests",
                "use_files_as_patch": True,
            },
        }
    ]
    state["reproduction_result"] = {
        "reproduced": True,
        "signature_key": "probe_port_mismatch:payments-api:8080!=9090",
    }
    state["fault_candidates"] = [
        {
            "path": "deploy/manifests/broken.yaml",
            "line": 12,
            "symbol": "readinessProbe.httpGet.port",
            "score": 0.95,
        }
    ]

    class FakeClient:
        def deploy_revision(self, *a, **k):
            return {"status": "deployed"}

        def observe_failure(self, *a, **k):
            return {
                "signature": {
                    "class": "probe_misconfiguration",
                    "key": "probe_port_mismatch:payments-api:8080!=9090",
                    "normalized": {
                        "reason": "x",
                        "resource_kind": "Deployment",
                        "resource_name": "payments-api",
                    },
                    "reproduced": True,
                    "evidence_refs": [{"kind": "k8s_event", "id": "e"}],
                    "observed_at": "2026-08-10T12:00:00Z",
                }
            }

        def run_validation(self, *a, **k):
            assert a[1]["plan"]["health_checks"][0]["resource"] == "deployment/worker-api"
            return {
                "sandbox_id": "sb-test",
                "passed": False,
                "fail_closed": False,
                "full_validation": False,
                "checks": [
                    {
                        "name": "signature_compare",
                        "kind": "signature_compare",
                        "status": "failed",
                        "duration_ms": 1,
                    }
                ],
                "completed_at": "2026-08-10T12:00:00Z",
            }

        def destroy_sandbox(self, *a, **k):
            return {"status": "destroyed"}

    with patch("raphael_agent.graph.nodes.SandboxClient", FakeClient):
        updates = node_validate(state)
    assert updates.get("validation_retryable") is True
    assert updates.get("status") != "escalated"
    assert any(
        event.get("event") == "localized_candidate_patch_match"
        for event in updates.get("audit_events") or []
    )


def test_live_validation_repeats_use_original_observed_resource(monkeypatch):
    monkeypatch.setenv('RAPHAEL_VALIDATION_REPEATS', '3')
    state = initial_run_state(_seed(), sandbox_mode='live')
    state.update(status='running', sandbox_id='sb-test', active_patch_id='patch-1',
                 candidate_patches=[{'patch_id': 'patch-1', 'policy_status': 'allowed',
                                     'files': [{'path': 'deploy/manifests/app.yaml', 'content': 'x: 1\n'}]}],
                 failure_signature={'key': 'before', 'normalized': {
                     'resource_kind': 'Deployment', 'resource_name': 'worker-api'}})
    resources = []

    class FakeClient:
        def deploy_revision(self, *args):
            return {}

        def observe_failure(self, *args):
            return {'signature': {'key': 'healthy', 'normalized': {
                'resource_kind': 'Pod', 'resource_name': 'worker-api-pod'}}}

        def run_validation(self, sandbox_id, body):
            resources.append(body['plan']['health_checks'][0]['resource'])
            return {'passed': True, 'fail_closed': False}

        def finalize_result(self, *args):
            return {'result_id': 'result-1', 'record': {}}

        def destroy_sandbox(self, *args):
            return {}

    monkeypatch.setattr('raphael_agent.graph.nodes.SandboxClient', FakeClient)
    updates = node_validate(state)
    assert resources == ['deployment/worker-api'] * 3
    assert updates['result_id'] == 'result-1'
