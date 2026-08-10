"""Post-MVP learning loop tests."""

from __future__ import annotations

import json
from pathlib import Path

from raphael_agent.diagnosis import diagnose
from raphael_agent.learning import (
    apply_learning_to_diagnosis,
    build_learning_snapshot,
    save_learning_snapshot,
)
from raphael_agent.schema_util import validate_agent


def test_build_snapshot_from_feedback_min_samples():
    rows = [
        {
            "outcome": "merged",
            "failure_class": "probe_misconfiguration",
            "repository": {"owner": "raphael", "name": "demo"},
        },
        {
            "outcome": "accepted",
            "failure_class": "probe_misconfiguration",
            "repository": {"owner": "raphael", "name": "demo"},
        },
        {
            "outcome": "merged",
            "failure_class": "probe_misconfiguration",
            "repository": {"owner": "raphael", "name": "demo"},
        },
        {
            "outcome": "rejected",
            "failure_class": "bad_image_reference",
            "repository": {"owner": "raphael", "name": "demo"},
        },
        {
            "outcome": "closed_unmerged",
            "failure_class": "bad_image_reference",
            "repository": {"owner": "raphael", "name": "demo"},
        },
        {
            "outcome": "deploy_failed",
            "failure_class": "bad_image_reference",
            "repository": {"owner": "raphael", "name": "demo"},
        },
    ]
    snap = build_learning_snapshot(feedback_rows=rows, runs=[], min_n=3)
    validate_agent("learning_snapshot.json", snap)
    by_class = {c["failure_class"]: c for c in snap["classes"] if c["repository"] is None}
    assert "probe_misconfiguration" in by_class
    assert by_class["probe_misconfiguration"]["confidence_delta"] > 0
    assert "bad_image_reference" in by_class
    assert by_class["bad_image_reference"]["prefer_escalate"] is True
    assert by_class["bad_image_reference"]["confidence_delta"] < 0


def test_apply_learning_boosts_and_demotes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_LEARNING", "1")
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    rows = [
        {"outcome": "merged", "failure_class": "probe_misconfiguration"},
        {"outcome": "accepted", "failure_class": "probe_misconfiguration"},
        {"outcome": "merged", "failure_class": "probe_misconfiguration"},
    ]
    snap = build_learning_snapshot(feedback_rows=rows, runs=[], min_n=3)
    save_learning_snapshot(snap, tmp_path / "learning_snapshot.json")
    monkeypatch.setenv(
        "RAPHAEL_LEARNING_SNAPSHOT", str(tmp_path / "learning_snapshot.json")
    )

    diagnosis = {
        "classification": {
            "category": "supported",
            "failure_class": "probe_misconfiguration",
            "blocked_reason": None,
        },
        "hypotheses": [
            {
                "hypothesis_id": "h1",
                "rank": 1,
                "statement": "probe",
                "confidence": 0.72,
                "failure_class": "probe_misconfiguration",
                "supporting_evidence_ids": ["e1"],
                "contradicting_evidence_ids": [],
            }
        ],
        "selected_hypothesis_id": "h1",
        "confidence": 0.72,
        "confidence_threshold": 0.7,
        "supporting_evidence_ids": ["e1"],
        "analyzer": {"name": "t", "mode": "deterministic"},
        "notes": "base",
        "diagnosed_at": "2026-08-10T00:00:00Z",
    }
    run = {"repository": {"owner": "raphael", "name": "demo"}}
    out = apply_learning_to_diagnosis(run, diagnosis)
    assert out["confidence"] > 0.72
    assert out.get("learning", {}).get("snapshot_id") == snap["snapshot_id"]
    validate_agent("diagnosis_result.json", out)


def test_learning_off_is_noop(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LEARNING", "0")
    diagnosis = {
        "classification": {
            "category": "supported",
            "failure_class": "probe_misconfiguration",
        },
        "hypotheses": [
            {
                "hypothesis_id": "h1",
                "rank": 1,
                "statement": "probe",
                "confidence": 0.8,
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
            }
        ],
        "selected_hypothesis_id": "h1",
        "confidence": 0.8,
        "supporting_evidence_ids": [],
        "analyzer": {"name": "t", "mode": "deterministic"},
        "diagnosed_at": "2026-08-10T00:00:00Z",
    }
    out = apply_learning_to_diagnosis({}, diagnosis)
    assert out["confidence"] == 0.8
    assert "learning" not in out


def test_diagnose_with_learning_snapshot(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RAPHAEL_LEARNING", "1")
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_AGENT_DATA_DIR", str(tmp_path))
    rows = [
        {"outcome": "rejected", "failure_class": "probe_misconfiguration"},
        {"outcome": "rejected", "failure_class": "probe_misconfiguration"},
        {"outcome": "closed_unmerged", "failure_class": "probe_misconfiguration"},
    ]
    snap = build_learning_snapshot(feedback_rows=rows, runs=[], min_n=3)
    path = tmp_path / "learning_snapshot.json"
    save_learning_snapshot(snap, path)
    monkeypatch.setenv("RAPHAEL_LEARNING_SNAPSHOT", str(path))

    run = {
        "evidence": [
            {
                "evidence_id": "ev-1",
                "kind": "ci_log",
                "source": {"system": "fixture", "ref": "x"},
                "summary": "Readiness probe failed HTTP probe",
                "content_excerpt": "Readiness probe failed: HTTP probe failed with statuscode: 503",
                "redacted": True,
                "provenance": {"collector": "t", "query": "t"},
                "collected_at": "2026-08-10T00:00:00Z",
            }
        ],
        "repository": {"owner": "raphael", "name": "demo"},
        "workspace_path": None,
    }
    result = diagnose(run)
    assert result.get("learning") is not None
    # Heavy rejects → prefer escalate / low selection
    assert result.get("selected_hypothesis_id") is None or result["confidence"] < 0.7
