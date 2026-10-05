"""Characterize current failure handling; do not alter production enforcement."""

from raphael_agent.graph import nodes
from raphael_agent.store import RunStore


def invalid_report():
    return nodes._escalation(
        {}, reason_code="future_unregistered_reason", summary="Review required",
        what_happened="A future reason was added without a matching schema update",
        why_no_fix="A safe repair is unavailable",
    )


def test_success_graph_can_return_without_persisting_when_report_validation_fails(tmp_path, monkeypatch):
    store = RunStore(tmp_path)
    prior = {"run_id": "validation-risk", "status": "pending", "audit_events": []}
    store.save_run(prior)
    state = {**prior, "escalation_report": invalid_report()}
    monkeypatch.setattr(nodes, "RunStore", lambda: store)
    monkeypatch.setattr(nodes, "publish", lambda state: {"ok": True, "dry_run": True})
    monkeypatch.setattr(nodes, "record_run_outcome", lambda state: None)
    monkeypatch.setattr(nodes, "_maybe_terminal_comment", lambda state, updates: None)
    updates = nodes.node_publish_or_escalate(state)
    assert updates["status"] == "success_draft_pr_ready"
    assert store.get_run(prior["run_id"]) == prior
