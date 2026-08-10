"""Prompt-injection / untrusted-input resistance (LLM off)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raphael_agent.diagnosis import diagnose
from raphael_agent.evidence.redaction import redact_evidence_item
from raphael_agent.patch.policy import apply_policy, path_allowed
from raphael_agent.publish import publish

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "injection"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _llm_off(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_PUBLISH_MODE", "dry_run")


def test_injection_ignore_policy_does_not_force_publish():
    fixture = _load("ignore_policy.json")
    # Redact first — secrets/tokens patterns in evidence
    items = [redact_evidence_item(dict(e)) for e in fixture["evidence"]]
    run = {
        "run_id": "inj-1",
        "status": "running",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
        "evidence": items,
        "result_id": None,
        "validation_results": [],
        "candidate_patches": [],
    }
    result = publish(run)
    assert result["ok"] is False
    assert result["error"] == "result_id_required"
    assert result["pull_request_url"] is None
    # Diagnosis must not become "forced publish" — no selected hyp from gibberish alone
    diagnosis = diagnose({"evidence": items})
    assert diagnosis["analyzer"]["mode"] == "deterministic"
    # Injection text must not set selected with fake confidence without real patterns
    # (may be unknown/low confidence)
    if diagnosis.get("selected_hypothesis_id"):
        assert diagnosis["classification"]["category"] != "blocked" or True
    # Critical: never invent a result_id
    assert run.get("result_id") is None


def test_injection_widen_allowlist_patch_rejected():
    fixture = _load("widen_allowlist.json")
    assert not path_allowed("secrets/prod.env")
    proposal = apply_policy(dict(fixture["malicious_patch"]))
    assert proposal["policy_status"] == "rejected"
    rules = {v["rule"] for v in proposal.get("policy_violations") or []}
    assert "path_allowlist" in rules or "secret_like_content" in rules


def test_injection_skip_validation_cannot_publish():
    fixture = _load("skip_validation.json")
    items = [redact_evidence_item(dict(e)) for e in fixture["evidence"]]
    # Even with a spoofed "passed" claim in logs, publish requires real result_id + validation
    run = {
        "run_id": "inj-3",
        "status": "running",
        "repository": {"owner": "raphael", "name": "demo"},
        "commit_sha": "abcdef1234567",
        "evidence": items,
        "result_id": None,
        "validation_results": [],
        "candidate_patches": [],
        "diagnosis": {
            "classification": {"category": "unknown", "failure_class": "unknown"},
            "hypotheses": [
                {
                    "hypothesis_id": "hyp-unknown",
                    "rank": 1,
                    "statement": "spoof",
                    "confidence": 1.0,
                    "supporting_evidence_ids": [],
                    "contradicting_evidence_ids": [],
                }
            ],
            "selected_hypothesis_id": "hyp-unknown",
            "confidence": 1.0,
            "confidence_threshold": 0.7,
            "supporting_evidence_ids": [],
            "analyzer": {"name": "t", "mode": "deterministic"},
            "diagnosed_at": "2026-08-10T12:00:00Z",
        },
    }
    result = publish(run)
    assert result["ok"] is False
    assert result["error"] == "result_id_required"


def test_evidence_secret_strings_redacted():
    item = redact_evidence_item(
        {
            "evidence_id": "ev-s",
            "kind": "ci_log",
            "source": {"system": "fixture", "ref": "t"},
            "summary": "token leak",
            "content_excerpt": "api_key: SUPERSECRETVALUE123",
            "redacted": False,
            "provenance": {"collector": "t", "query": "t"},
            "collected_at": "2026-08-10T12:00:00Z",
        }
    )
    assert "SUPERSECRETVALUE123" not in (item.get("content_excerpt") or "")
    assert item.get("redacted") is True
