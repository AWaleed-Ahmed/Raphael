"""Invalid reports stop publication and persist a content-free terminal."""

import json
import logging
import sqlite3

import pytest

from raphael_agent.graph import nodes
from raphael_agent.escalation_validation import escalation_report_boundary
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore, SqliteRunStore

SECRET = "UNREDACTED_API_SECRET_TOKEN"


def invalid_report():
    return nodes._escalation(
        {}, reason_code=SECRET, summary=SECRET,
        what_happened=SECRET, why_no_fix=SECRET,
    )


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
@pytest.mark.parametrize("status", ["running", "escalated", "failed_closed"])
def test_graph_invalid_report_fails_closed_and_persists(tmp_path, monkeypatch, caplog, store_type, status):
    store = store_type(tmp_path)
    state = {"run_id": "validation-risk", "status": status, "audit_events": [],
             "escalation_report": invalid_report()}
    monkeypatch.setattr(nodes, "RunStore", lambda: store)
    def forbidden_publish(state):
        pytest.fail("Invalid reports must never reach publish")
    monkeypatch.setattr(nodes, "publish", forbidden_publish)
    with caplog.at_level(logging.ERROR):
        updates = nodes.node_publish_or_escalate(state)
    assert updates["status"] == "failed_closed"
    assert updates["terminal_reason"] == "escalation_report_invalid"
    persisted = store.get_run(state["run_id"])
    validate_agent("escalation_report.json", persisted["escalation_report"])
    assert persisted["audit_events"][-1]["detail"] == "contracts/agent/escalation_report.json#/properties/reason_code/enum"
    assert SECRET not in json.dumps(persisted)
    assert SECRET not in caplog.text
    assert "Escalation report rejected" in caplog.text
    assert SECRET not in store._run_path(state["run_id"]).read_text()
    if isinstance(store, SqliteRunStore):
        with sqlite3.connect(store.db_path) as connection:
            payload = connection.execute("SELECT payload FROM runs WHERE run_id = ?", (state["run_id"],)).fetchone()[0]
        assert SECRET not in payload


def test_node_boundary_rejects_report_immediately_after_construction():
    @escalation_report_boundary
    def producer(state):
        return {"status": "escalated", "escalation_report": invalid_report()}
    updates = producer({})
    assert updates["status"] == "failed_closed"
    assert updates["terminal_reason"] == "escalation_report_invalid"
    assert SECRET not in json.dumps(updates)
    validate_agent("escalation_report.json", updates["escalation_report"])


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
def test_publication_budget_report_is_validated_before_persistence(tmp_path, monkeypatch, store_type):
    store = store_type(tmp_path)
    monkeypatch.setattr(nodes, "RunStore", lambda: store)
    monkeypatch.setattr(nodes, "_budget_halt_updates", lambda *args: {
        "status": "escalated", "escalation_report": invalid_report(),
    })
    monkeypatch.setattr(nodes, "record_run_outcome", lambda state: None)
    monkeypatch.setattr(nodes, "_maybe_terminal_comment", lambda state, updates: None)
    updates = nodes.node_publish_or_escalate({"run_id": "budget-report-invalid"})
    assert updates["status"] == "failed_closed"
    persisted = store.get_run("budget-report-invalid")
    assert persisted["terminal_reason"] == "escalation_report_invalid"
    assert SECRET not in json.dumps(persisted)
    validate_agent("escalation_report.json", persisted["escalation_report"])
