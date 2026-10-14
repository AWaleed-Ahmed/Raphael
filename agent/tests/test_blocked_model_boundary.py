"""Deterministic safety stops cannot be replaced by model predictions."""

from copy import deepcopy
from unittest.mock import Mock

import pytest

import raphael_agent.diagnosis as diagnosis_module
import raphael_agent.diagnosis.llm as llm_module
from raphael_agent.diagnosis.analyzers import analyze_run
from raphael_agent.graph import nodes
from raphael_agent.graph.state import initial_run_state
from raphael_agent.model_gateway import ModelGateway


BLOCK_CASES = [
    ("production_secret_required", "Failure requires production secret values"),
    ("privileged_or_host_access", "privileged host access is blocked"),
]
PROBE_PREDICTION = {
    "failure_class": "probe_misconfiguration",
    "confidence": 0.95,
    "abstained": False,
}


def blocked_state(reason, signal):
    state = initial_run_state(
        {
            "run_id": "blocked-model-test",
            "tenant_id": "test-tenant",
            "trigger": {"kind": "fixture", "event_id": "test"},
            "repository": {"owner": "test", "name": "fixture"},
            "commit_sha": "a" * 40,
        },
        sandbox_mode="recorded_stub",
    )
    state.update(
        status="running",
        evidence=[{"evidence_id": "ev-block", "summary": signal}],
        reproduction_result={"reproduced": True},
    )
    assert analyze_run(state)[0].blocked_reason == reason
    return state


@pytest.mark.parametrize("reason,signal", BLOCK_CASES)
def test_node_diagnose_preserves_analyzer_block_with_nonabstaining_model(
    monkeypatch, reason, signal
):
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "1")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")
    state = blocked_state(reason, signal)
    before = deepcopy(state)
    now = state["updated_at"]
    monkeypatch.setattr(nodes, "utc_now", lambda: now)
    monkeypatch.setattr(diagnosis_module, "utc_now", lambda: now)
    external_refine = Mock(side_effect=AssertionError("blocked diagnosis reached LLM"))
    monkeypatch.setattr(diagnosis_module, "try_llm_diagnosis", external_refine)
    gateway = Mock(spec=ModelGateway)
    gateway._load_error = None
    gateway.classify_failure.return_value = None
    gateway.merge_diagnosis.side_effect = ModelGateway.merge_diagnosis
    monkeypatch.setattr(nodes, "ModelGateway", lambda: gateway)
    baseline = nodes.node_diagnose(deepcopy(state))
    gateway.reset_mock()
    gateway.classify_failure.return_value = deepcopy(PROBE_PREDICTION)

    result = nodes.node_diagnose(state)

    assert result["diagnosis"]["classification"] == {
        "category": "blocked", "failure_class": "policy_blocked", "blocked_reason": reason
    }
    assert result["status"] == "escalated"
    assert result["terminal_reason"] == reason
    assert result["escalation_report"]["reason_code"] == reason
    assert result["diagnosis"] == baseline["diagnosis"]
    assert result["terminal_reason"] == baseline["terminal_reason"]
    assert result["escalation_report"] == baseline["escalation_report"]
    gateway.classify_failure.assert_not_called()
    gateway.merge_diagnosis.assert_not_called()
    external_refine.assert_not_called()
    assert state == before


@pytest.mark.parametrize("reason,signal", BLOCK_CASES)
@pytest.mark.parametrize("selected", [None, "hyp-blocked"])
def test_merge_diagnosis_cannot_replace_blocked_result(monkeypatch, reason, signal, selected):
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")
    deterministic = diagnosis_module.diagnose(blocked_state(reason, signal))
    deterministic["selected_hypothesis_id"] = selected
    before = deepcopy(deterministic)
    result = ModelGateway.merge_diagnosis(deterministic, deepcopy(PROBE_PREDICTION), {})
    assert result is deterministic
    assert result == before


@pytest.mark.parametrize("reason,signal", BLOCK_CASES)
def test_diagnose_never_refines_blocked_result_with_external_llm(monkeypatch, reason, signal):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "1")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")
    refine = Mock(side_effect=AssertionError("external LLM reached"))
    monkeypatch.setattr(diagnosis_module, "try_llm_diagnosis", refine)
    result = diagnosis_module.diagnose(blocked_state(reason, signal))
    assert result["classification"]["category"] == "blocked"
    assert result["classification"]["blocked_reason"] == reason
    assert result["selected_hypothesis_id"] is None
    refine.assert_not_called()


@pytest.mark.parametrize("reason,signal", BLOCK_CASES)
def test_external_llm_helper_rejects_blocked_seed_without_transport(monkeypatch, reason, signal):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "1")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")
    state = blocked_state(reason, signal)
    deterministic = diagnosis_module.diagnose(state)
    before = deepcopy(deterministic)
    transport = Mock(side_effect=AssertionError("blocked evidence sent to external LLM"))
    monkeypatch.setattr(llm_module, "complete_json", transport)
    key_lookup = Mock(return_value="unit-test-only-key")
    monkeypatch.setattr(llm_module.BYOKConfig, "from_env", key_lookup)
    assert llm_module.try_llm_diagnosis(state, deterministic) is None
    assert deterministic == before
    key_lookup.assert_not_called()
    transport.assert_not_called()


@pytest.mark.parametrize("reason,signal", BLOCK_CASES)
@pytest.mark.parametrize("status", ["running", "blocked", "escalated", "failed_closed"])
def test_node_patch_never_selects_model_after_safety_block(monkeypatch, reason, signal, status):
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    monkeypatch.setenv("RAPHAEL_LLM_PATCH", "1")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")
    state = blocked_state(reason, signal)
    state.update(
        diagnosis=diagnosis_module.diagnose(state),
        status=status,
        terminal_reason=reason,
        escalation_report=nodes._escalation(
            {}, reason_code=reason, summary="original safety stop",
            what_happened="A deterministic safety signal blocked this run",
            why_no_fix="Safety policy forbids automatic patching",
        ),
    )
    before = deepcopy(state)
    gateway = Mock(side_effect=AssertionError("blocked run reached patch model"))
    proposal = Mock(side_effect=AssertionError("blocked run generated a patch"))
    monkeypatch.setattr(nodes, "ModelGateway", gateway)
    monkeypatch.setattr(nodes, "propose_patch", proposal)
    updates = nodes.node_patch(state)
    merged = {**state, **updates}
    assert merged["diagnosis"] == before["diagnosis"]
    assert merged["terminal_reason"] == reason
    assert merged["escalation_report"] == before["escalation_report"]
    assert not merged.get("candidate_patches")
    gateway.assert_not_called()
    proposal.assert_not_called()
    assert state == before


@pytest.mark.parametrize("status", ["blocked", "escalated", "failed_closed"])
def test_node_patch_terminal_status_guard_is_independent_of_diagnosis(monkeypatch, status):
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    state = {
        "status": status,
        "diagnosis": {"classification": {"category": "supported"}},
        "terminal_reason": "original_stop",
        "escalation_report": nodes._escalation(
            {}, reason_code="policy_blocked", summary="original safety stop",
            what_happened="A pre-existing terminal state blocked this run",
            why_no_fix="Terminal state forbids automatic patching",
        ),
    }
    before = deepcopy(state)
    gateway = Mock(side_effect=AssertionError("terminal run reached patch model"))
    proposal = Mock(side_effect=AssertionError("terminal run generated a patch"))
    monkeypatch.setattr(nodes, "ModelGateway", gateway)
    monkeypatch.setattr(nodes, "propose_patch", proposal)
    result = {**state, **nodes.node_patch(state)}
    assert result["terminal_reason"] == before["terminal_reason"]
    assert result["escalation_report"] == before["escalation_report"]
    gateway.assert_not_called()
    proposal.assert_not_called()
    assert state == before


def test_model_enabled_default_remains_on(monkeypatch):
    monkeypatch.delenv("RAPHAEL_MODEL_ENABLED", raising=False)
    assert ModelGateway().enabled is True
