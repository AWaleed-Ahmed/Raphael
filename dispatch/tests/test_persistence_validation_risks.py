"""Connector result POST returns a terminal, not a schema-validation 500."""

import json
import sqlite3

import pytest
from starlette.testclient import TestClient

from raphael_agent.graph.nodes import _escalation
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore, SqliteRunStore
from raphael_dispatch.app import create_app
from raphael_dispatch.orchestrator import AgentHooks, Orchestrator
from tests.test_orchestrator import job_envelope, result_for, create_result, deploy_result, observe_result

SECRET = "UNREDACTED_API_SECRET_TOKEN"


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
def test_dispatch_invalid_report_returns_failed_terminal_and_persists(tmp_path, monkeypatch, store_type):
    store = store_type(tmp_path)
    def bad_diagnose(state):
        return {"status": "escalated", "escalation_report": _escalation(
            {}, reason_code=SECRET, summary=SECRET, what_happened=SECRET, why_no_fix=SECRET)}
    orchestrator = Orchestrator(store=store, hooks=AgentHooks(diagnose=bad_diagnose))
    monkeypatch.setenv("RAPHAEL_DISPATCH_TOKENS", json.dumps({
        "connector": {"tenant_id": "test", "role": "connector"}}))
    submitted = job_envelope()
    job_id = submitted["payload"]["job_id"]
    action = orchestrator.intake(submitted, tenant_id="test")["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job_id)))["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=deploy_result()))["messages"][0]
    with TestClient(create_app(orchestrator)) as client:
        response = client.post("/v1/results", headers={"Authorization": "Bearer connector"},
                               json=result_for(action, result=observe_result()))
    assert response.status_code == 200
    terminal = response.json()["messages"][0]
    assert terminal["kind"] == "terminal"
    assert terminal["payload"]["final_status"] == "failed"
    assert terminal["payload"]["instructions"] == "discard_local_copy"
    persisted = store.get_run(job_id)
    assert persisted["dispatch"]["stage"] == "terminal"
    assert persisted["dispatch"]["pending_action"] is None
    assert persisted["terminal_reason"] == "escalation_report_invalid"
    validate_agent("escalation_report.json", persisted["escalation_report"])
    assert persisted["audit_events"][-1]["detail"] == "contracts/agent/escalation_report.json#/properties/reason_code/enum"
    assert SECRET not in json.dumps(persisted)
    assert SECRET not in store._run_path(job_id).read_text()
    if isinstance(store, SqliteRunStore):
        with sqlite3.connect(store.db_path) as connection:
            payload = connection.execute("SELECT payload FROM runs WHERE run_id = ?", (job_id,)).fetchone()[0]
        assert SECRET not in payload
