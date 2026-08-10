"""Contract fixture smoke for agent schemas."""

from __future__ import annotations

from datetime import datetime, timezone

from raphael_agent.schema_util import validate_agent


def test_evidence_item_schema():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    validate_agent(
        "evidence_item.json",
        {
            "evidence_id": "ev-1",
            "kind": "ci_log",
            "source": {"system": "fixture", "ref": "job/1"},
            "redacted": True,
            "provenance": {"collector": "test", "query": "fixture"},
            "collected_at": now,
        },
    )


def test_diagnosis_result_schema():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    validate_agent(
        "diagnosis_result.json",
        {
            "classification": {
                "category": "supported",
                "failure_class": "probe_misconfiguration",
            },
            "hypotheses": [
                {
                    "hypothesis_id": "h1",
                    "rank": 1,
                    "statement": "probe port mismatch",
                    "confidence": 0.9,
                    "supporting_evidence_ids": ["ev-1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            "selected_hypothesis_id": "h1",
            "confidence": 0.9,
            "supporting_evidence_ids": ["ev-1"],
            "analyzer": {"name": "test", "mode": "stub"},
            "diagnosed_at": now,
        },
    )


def test_patch_proposal_schema():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    validate_agent(
        "patch_proposal.json",
        {
            "patch_id": "p1",
            "attempt": 1,
            "hypothesis_id": "h1",
            "files": [{"path": "deploy/app.yaml", "action": "modify", "content": "x: 1\n"}],
            "rationale": {"summary": "fix probe port", "evidence_ids": ["ev-1"]},
            "policy_status": "allowed",
            "created_at": now,
        },
    )


def test_escalation_report_schema():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    validate_agent(
        "escalation_report.json",
        {
            "reason_code": "low_confidence",
            "summary": "confidence below threshold",
            "what_happened": "diagnosed but uncertain",
            "evidence_ids": ["ev-1"],
            "hypotheses_considered": [
                {
                    "hypothesis_id": "h1",
                    "statement": "maybe probe",
                    "confidence": 0.4,
                }
            ],
            "attempts": [],
            "why_no_fix": "confidence too low",
            "recommended_next_checks": ["Inspect pod events"],
            "escalated_at": now,
        },
    )
