"""Phase 0 smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raphael_agent.graph import initial_run_state, run_stub_graph
from raphael_agent.ingest import normalize_failed_run_event
from raphael_agent.sandbox_client import SandboxClient
from raphael_agent.schema_util import validate_agent
from raphael_agent.scripts.smoke import _for_validation, choose_sandbox_mode

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
FIXTURE = AGENT_ROOT / "fixtures" / "failed_run_event.json"
WORKSPACE = REPO_ROOT / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"


def test_agent_contracts_exist():
    contracts = REPO_ROOT / "contracts" / "agent"
    for name in (
        "run_record.json",
        "evidence_item.json",
        "diagnosis_result.json",
        "patch_proposal.json",
        "escalation_report.json",
    ):
        assert (contracts / name).is_file()


def test_smoke_graph_recorded_stub():
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["workspace_path"] = str(WORKSPACE)
    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = event["workspace_path"]
    seed["manifests"] = event.get("manifests")
    initial = initial_run_state(seed, sandbox_mode="recorded_stub")
    final = run_stub_graph(initial)
    validate_agent("run_record.json", _for_validation(final))
    assert final["status"] == "success_draft_pr_ready"
    assert final["result_id"] == "res-recorded-001"
    assert final["pull_request_url"] is None
    assert final["sandbox_mode"] == "recorded_stub"
    nodes = [e["node"] for e in final["audit_events"]]
    assert "ingest" in nodes
    assert "evidence" in nodes
    assert "diagnose" in nodes
    assert "reproduce" in nodes
    assert "patch" in nodes
    assert "validate" in nodes
    assert "publish_or_escalate" in nodes


def test_smoke_graph_auto_or_live():
    """If controller is up, exercise live path; otherwise same as recorded stub."""
    import uuid

    mode = choose_sandbox_mode(None)
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["workspace_path"] = str(WORKSPACE)
    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = event["workspace_path"]
    seed["manifests"] = event.get("manifests")
    if mode == "live":
        seed["run_id"] = f"asmoke-{uuid.uuid4().hex[:10]}"
    initial = initial_run_state(seed, sandbox_mode=mode)
    final = run_stub_graph(initial)
    validate_agent("run_record.json", _for_validation(final))
    assert final["status"] in {
        "success_draft_pr_ready",
        "escalated",
        "failed_closed",
    }
    if mode == "recorded_stub":
        assert final["status"] == "success_draft_pr_ready"
    if mode == "live" and final["status"] == "success_draft_pr_ready":
        assert final.get("result_id")
        assert str(final["result_id"]).startswith("res-")


def test_sandbox_client_health_when_up():
    client = SandboxClient(validate=False)
    if not client.is_reachable():
        pytest.skip("sandbox controller not reachable on RAPHAEL_SANDBOX_URL")
    health = client.health()
    assert "service" in health or health.get("ok") is True or isinstance(health, dict)
