"""Characterize the current report-validation exception boundary."""

import pytest
from jsonschema import ValidationError

from raphael_agent.graph.nodes import _escalation
from raphael_agent.store import RunStore
from raphael_dispatch.orchestrator import Orchestrator


def test_dispatch_save_propagates_report_validation_error_without_overwriting(tmp_path):
    store = RunStore(tmp_path)
    prior = {"run_id": "dispatch-validation-risk", "status": "running"}
    store.save_run(prior)
    report = _escalation(
        {}, reason_code="future_unregistered_reason", summary="Review required",
        what_happened="A future reason lacks a matching schema update",
        why_no_fix="No safe repair is available",
    )
    orchestrator = Orchestrator(store=store)
    with pytest.raises(ValidationError):
        orchestrator._save({**prior, "escalation_report": report})
    assert store.get_run(prior["run_id"]) == prior
