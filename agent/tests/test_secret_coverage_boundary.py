"""Structural Secret coverage survives safe evidence and durable boundaries."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from raphael_agent.evidence.boundary import redact_value
from raphael_agent.graph import initial_run_state
from raphael_agent.graph.nodes import node_diagnose, node_patch, node_secret_coverage_gate
from raphael_agent.ingest import normalize_failed_run_event
from raphael_agent.store.run_store import RunStore
from raphael_agent.store.sqlite_run_store import SqliteRunStore


def coverage(status: str = "missing_key", optional: bool = False) -> dict[str, Any]:
    return {
        "format_version": 1, "complete": True, "truncated": False,
        "references": [{"workload_kind": "Deployment", "workload_name": "api",
                        "namespace": "sandbox", "source": "secretKeyRef",
                        "secret_name": "payments-db", "key": "PASSWORD",
                        "optional": optional, "status": status}],
    }


def state_with_coverage() -> dict[str, Any]:
    event = json.loads((Path(__file__).parents[1] / "fixtures/failed_run_event.json").read_text())
    state = initial_run_state(normalize_failed_run_event(event), sandbox_mode="live")
    state["secret_coverage"] = coverage()
    return state


def test_metadata_survives_without_whitelisting_arbitrary_secret_fields() -> None:
    report = coverage()
    assert redact_value({"secret_coverage": report, "password": "VALUE_SENTINEL"}) == {
        "secret_coverage": report, "password": "[REDACTED]"}
    assert report == coverage()  # The caller's object is not mutated.
    unsafe = {**report, "values": {"PASSWORD": "VALUE_SENTINEL"}}
    assert redact_value({"secret_coverage": unsafe}) == {"secret_coverage": "[REDACTED]"}


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
def test_coverage_survives_store_reopen_and_rejected_payload_is_omitted(
    tmp_path: Path, store_type: type[RunStore],
) -> None:
    state = state_with_coverage()
    store_type(root=tmp_path).save_run(state)
    restored = store_type(root=tmp_path).get_run(state["run_id"])
    assert restored is not None
    assert restored["secret_coverage"] == coverage()
    assert node_secret_coverage_gate(restored)["terminal_reason"] == "unresolved_secret_dependency"
    state["secret_coverage"]["values"] = {"PASSWORD": "VALUE_SENTINEL"}
    store_type(root=tmp_path).save_run(state)
    assert store_type(root=tmp_path).get_run(state["run_id"])["secret_coverage"] is None
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"VALUE_SENTINEL" not in path.read_bytes()


@pytest.mark.parametrize("status", ["missing_key", "missing_object"])
def test_undecorated_required_reference_stops_patch_and_names_next_check(status: str) -> None:
    state = state_with_coverage()
    state["secret_coverage"] = coverage(status)
    with patch("raphael_agent.graph.nodes.ModelGateway") as gateway:
        updates = node_patch(state)
    gateway.assert_not_called()
    assert updates["terminal_reason"] == "unresolved_secret_dependency"
    assert "sandbox/payments-db[PASSWORD]" in updates["escalation_report"]["recommended_next_checks"][0]
    assert state["attempt_count"]["patch"] == 0


def test_textual_production_block_keeps_precedence_over_structural_gap() -> None:
    state = state_with_coverage()
    state["evidence"] = [{"evidence_id": "text", "kind": "other", "summary": "Requires production secret values",
                          "content_excerpt": "Requires production secret values", "redacted": True}]
    with patch("raphael_agent.graph.nodes.ModelGateway") as gateway:
        updates = node_diagnose(state)
    gateway.assert_not_called()
    assert updates["terminal_reason"] == "production_secret_required"


@pytest.mark.parametrize("change", [{"complete": False}, {"truncated": True}, {"format_version": 2}, {"references": []}])
def test_unknown_or_empty_coverage_cannot_invent_a_production_dependency(change: dict[str, Any]) -> None:
    state = state_with_coverage()
    state["secret_coverage"].update(change)
    assert node_secret_coverage_gate(state) == {}


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_live_graph_obtains_structural_coverage_before_diagnosis_and_cleans_up(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cleanup_fails: bool,
) -> None:
    from raphael_agent.graph.graph import run_stub_graph

    calls: list[str] = []

    class Client:
        def create_sandbox(self, _body: dict[str, Any]) -> dict[str, Any]:
            calls.append("create")
            return {"sandbox_id": "sb-structural", "cluster_backend": "kind"}

        def deploy_revision(self, _sid: str, _body: dict[str, Any]) -> dict[str, Any]:
            calls.append("deploy")
            return {"fidelity": {"secret_coverage": coverage()}}

        def observe_failure(self, _sid: str, _body: dict[str, Any]) -> dict[str, Any]:
            calls.append("observe")
            return {"signature": {"class": "config_missing_key", "key": "missing:db",
                                  "reproduced": True, "normalized": {}}}

        def destroy_sandbox(self, _sid: str, _body: dict[str, Any]) -> dict[str, Any]:
            calls.append("destroy")
            if cleanup_fails:
                raise OSError("cleanup fixture failure")
            return {}

    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "0")
    monkeypatch.setattr("raphael_agent.graph.graph.node_evidence", lambda _state: {})
    monkeypatch.setattr("raphael_agent.graph.nodes.SandboxClient", Client)
    state = state_with_coverage()
    state.pop("secret_coverage")
    state["workspace_path"] = None
    state["evidence"] = []
    with patch("raphael_agent.graph.nodes.ModelGateway") as gateway, patch(
        "raphael_agent.diagnosis.llm.complete_json"
    ) as provider:
        final = run_stub_graph(state)
    assert final["terminal_reason"] == "unresolved_secret_dependency"
    assert final["attempt_count"]["patch"] == 0
    assert calls == ["create", "deploy", "observe", "destroy"]
    if cleanup_fails:
        assert final["errors"][-1]["code"] == "sandbox_cleanup_failed"
        assert final["errors"][-1]["retryable"] is True
        assert final["sandbox_id"] == "sb-structural"
    gateway.assert_not_called()
    provider.assert_not_called()
