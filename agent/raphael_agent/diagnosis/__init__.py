"""Diagnosis stubs — Phase 2 will add deterministic analyzers + LLM."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def stub_diagnose(run: dict[str, Any]) -> dict[str, Any]:
    """Produce a structured diagnosis_result (no LLM)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    evidence_ids = [e["evidence_id"] for e in run.get("evidence") or []]
    hypothesis_id = "hyp-probe-port"
    return {
        "classification": {
            "category": "supported",
            "failure_class": "probe_misconfiguration",
            "blocked_reason": None,
        },
        "hypotheses": [
            {
                "hypothesis_id": hypothesis_id,
                "rank": 1,
                "statement": "Readiness probe targets wrong container port",
                "confidence": 0.92,
                "failure_class": "probe_misconfiguration",
                "expected_signature_key": "probe_port_mismatch:payments-api",
                "supporting_evidence_ids": evidence_ids,
                "contradicting_evidence_ids": [],
                "candidate_fix_hint": "deploy/manifests readinessProbe.port",
            }
        ],
        "selected_hypothesis_id": hypothesis_id,
        "confidence": 0.92,
        "confidence_threshold": 0.7,
        "supporting_evidence_ids": evidence_ids,
        "analyzer": {"name": "stub_probe_analyzer", "mode": "stub", "version": "0.1.0"},
        "notes": "Phase 0 stub diagnosis — not a real analyzer",
        "diagnosed_at": now,
    }
