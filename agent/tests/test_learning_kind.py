"""Learning-loop scenario tests + kind-gated live sandbox run.

Unit path always runs. Live/kind path skips unless the sandbox controller
is reachable (typically kind + ``RAPHAEL_LISTEN=127.0.0.1:8090``).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from raphael_agent.diagnosis import diagnose
from raphael_agent.feedback import JsonlFeedbackRecorder
from raphael_agent.graph import initial_run_state, run_stub_graph
from raphael_agent.ingest import normalize_failed_run_event
from raphael_agent.learning import (
    build_learning_snapshot,
    save_learning_snapshot,
)
from raphael_agent.sandbox_client import SandboxClient
from raphael_agent.schema_util import for_run_record_validation, validate_agent

AGENT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENT_ROOT.parent
FIXTURE = AGENT_ROOT / "fixtures" / "failed_run_event.json"
WORKSPACE = REPO_ROOT / "sandbox" / "harness" / "scenarios" / "probe_port_mismatch"


def _probe_evidence_run() -> dict:
    return {
        "repository": {"owner": "raphael", "name": "payments"},
        "evidence": [
            {
                "evidence_id": "ev-probe-1",
                "kind": "ci_log",
                "source": {"system": "fixture", "ref": "deploy/1"},
                "summary": "Readiness probe failed",
                "content_excerpt": (
                    "Readiness probe failed: HTTP probe failed with statuscode: 503 "
                    "probe port mismatch containerPort 8080"
                ),
                "redacted": True,
                "provenance": {"collector": "test", "query": "ci"},
                "collected_at": "2026-08-10T12:00:00Z",
            }
        ],
        "workspace_path": str(WORKSPACE),
        "manifests": {
            "type": "yaml",
            "path": "deploy/manifests",
            "fixed_path": "deploy/manifests_fixed",
        },
    }


def test_real_life_learning_scenario_reject_then_escalate(tmp_path, monkeypatch):
    """Scenario: three human rejects of probe fixes → next diagnose escalates.

    Mirrors: week-1 partner rejects bad probe PRs → learn → week-2 Raphael
    stops auto-selecting that class until confidence recovers.
    """
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")

    # Week 1: diagnose without learning — probe is selected.
    before = diagnose(_probe_evidence_run())
    assert before["classification"]["failure_class"] == "probe_misconfiguration"
    assert before.get("selected_hypothesis_id")

    # Humans reject those drafts three times (FR-065).
    recorder = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl")
    for i in range(3):
        recorder.record(
            {
                "outcome": "rejected",
                "failure_class": "probe_misconfiguration",
                "repository": {"owner": "raphael", "name": "payments"},
                "run_id": f"run-reject-{i}",
                "source": "manual",
                "notes": "wrong port again — not the real root cause",
            }
        )

    snap = build_learning_snapshot(
        feedback_rows=recorder.read_all(), runs=[], min_n=3
    )
    save_learning_snapshot(snap, tmp_path / "learning_snapshot.json")
    monkeypatch.setenv(
        "RAPHAEL_LEARNING_SNAPSHOT", str(tmp_path / "learning_snapshot.json")
    )
    monkeypatch.setenv("RAPHAEL_LEARNING", "1")

    # Week 2: same signal, learning prefer_escalate → no auto-selected fix.
    after = diagnose(_probe_evidence_run())
    assert after["classification"]["failure_class"] == "probe_misconfiguration"
    assert after.get("learning") is not None
    assert after.get("selected_hypothesis_id") is None
    assert after.get("confidence", 1) < float(after.get("confidence_threshold") or 0.7)


def test_real_life_learning_scenario_accept_boosts(tmp_path, monkeypatch):
    """Scenario: three merges of probe fixes → confidence boosted on next diagnose."""
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")

    baseline = diagnose(_probe_evidence_run())
    base_conf = float(baseline.get("confidence") or 0)

    recorder = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl")
    for i in range(3):
        recorder.record(
            {
                "outcome": "merged",
                "failure_class": "probe_misconfiguration",
                "repository": {"owner": "raphael", "name": "payments"},
                "run_id": f"run-merge-{i}",
                "source": "github_webhook",
            }
        )
    snap = build_learning_snapshot(
        feedback_rows=recorder.read_all(), runs=[], min_n=3
    )
    save_learning_snapshot(snap, tmp_path / "learning_snapshot.json")
    monkeypatch.setenv(
        "RAPHAEL_LEARNING_SNAPSHOT", str(tmp_path / "learning_snapshot.json")
    )
    monkeypatch.setenv("RAPHAEL_LEARNING", "1")

    boosted = diagnose(_probe_evidence_run())
    assert boosted.get("selected_hypothesis_id")
    assert float(boosted["confidence"]) >= base_conf
    assert float(boosted["learning"]["confidence_delta"]) > 0


def test_learning_full_graph_recorded_stub_after_rejects(tmp_path, monkeypatch):
    """Graph terminal becomes escalated when learning demotes the probe class."""
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")

    recorder = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl")
    for i in range(3):
        recorder.record(
            {
                "outcome": "rejected",
                "failure_class": "probe_misconfiguration",
                "repository": {"owner": "raphael", "name": "demo"},
                "source": "manual",
            }
        )
    snap = build_learning_snapshot(
        feedback_rows=recorder.read_all(), runs=[], min_n=3
    )
    save_learning_snapshot(snap, tmp_path / "learning_snapshot.json")
    monkeypatch.setenv(
        "RAPHAEL_LEARNING_SNAPSHOT", str(tmp_path / "learning_snapshot.json")
    )
    monkeypatch.setenv("RAPHAEL_LEARNING", "1")

    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["workspace_path"] = str(WORKSPACE)
    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = str(WORKSPACE)
    seed["manifests"] = event.get("manifests")
    final = run_stub_graph(initial_run_state(seed, sandbox_mode="recorded_stub"))
    validate_agent("run_record.json", for_run_record_validation(final))
    assert final["status"] == "escalated"
    assert final.get("terminal_reason") in {"low_confidence", "blocked_category"}


@pytest.mark.kind
def test_learning_loop_against_live_sandbox_kind(tmp_path, monkeypatch):
    """Kind/controller live path: learning-boosted probe run through real sandbox.

    Requires:
      - kind cluster bootstrapped
      - sandbox controller: RAPHAEL_CLUSTER_BACKEND=kind RAPHAEL_LISTEN=127.0.0.1:8090
    """
    client = SandboxClient(validate=False)
    if not client.is_reachable():
        pytest.skip(
            "sandbox controller not reachable — start kind + controller on :8090"
        )

    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("RAPHAEL_PARTNER_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")

    recorder = JsonlFeedbackRecorder(tmp_path / "feedback.jsonl")
    for i in range(3):
        recorder.record(
            {
                "outcome": "merged",
                "failure_class": "probe_misconfiguration",
                "repository": {"owner": "raphael", "name": "demo"},
                "source": "manual",
            }
        )
    snap = build_learning_snapshot(
        feedback_rows=recorder.read_all(), runs=[], min_n=3
    )
    save_learning_snapshot(snap, tmp_path / "learning_snapshot.json")
    monkeypatch.setenv(
        "RAPHAEL_LEARNING_SNAPSHOT", str(tmp_path / "learning_snapshot.json")
    )
    monkeypatch.setenv("RAPHAEL_LEARNING", "1")

    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    event["workspace_path"] = str(WORKSPACE)
    event["run_id"] = f"learn-kind-{uuid.uuid4().hex[:10]}"
    seed = normalize_failed_run_event(event)
    seed["workspace_path"] = str(WORKSPACE)
    seed["manifests"] = event.get("manifests")
    seed["run_id"] = event["run_id"]

    final = run_stub_graph(initial_run_state(seed, sandbox_mode="live"))
    validate_agent("run_record.json", for_run_record_validation(final))
    assert final["sandbox_mode"] == "live"
    assert final["status"] in {
        "success_draft_pr_ready",
        "escalated",
        "failed_closed",
    }
    # Learning applied during diagnose when class matched.
    diagnosis = final.get("diagnosis") or {}
    if diagnosis.get("classification", {}).get("failure_class") == "probe_misconfiguration":
        assert diagnosis.get("learning") is not None
    if final["status"] == "success_draft_pr_ready":
        assert final.get("result_id")
        assert final.get("sandbox_id")
