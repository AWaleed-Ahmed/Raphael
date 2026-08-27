"""Unit tests for deterministic analyzers and diagnosis."""

from __future__ import annotations

from pathlib import Path

from raphael_agent.diagnosis import diagnose
from raphael_agent.diagnosis.analyzers import analyze_run
from raphael_agent.schema_util import validate_agent

REPO = Path(__file__).resolve().parents[2]
PROBE_WS = REPO / "agent" / "fixtures" / "scenarios" / "probe_port_mismatch"
BAD_IMAGE_WS = REPO / "agent" / "fixtures" / "scenarios" / "bad_image"
MISSING_CM_WS = REPO / "agent" / "fixtures" / "scenarios" / "missing_configmap_key"


def _run(workspace: Path, evidence_excerpt: str, manifests_path: str = "deploy/manifests") -> dict:
    return {
        "workspace_path": str(workspace),
        "manifests": {"type": "yaml", "path": manifests_path},
        "evidence": [
            {
                "evidence_id": "ev-1",
                "kind": "ci_log",
                "source": {"system": "fixture", "ref": "t"},
                "summary": "failed",
                "content_excerpt": evidence_excerpt,
                "redacted": True,
                "provenance": {"collector": "test", "query": "t"},
                "collected_at": "2026-08-10T12:00:00Z",
            }
        ],
    }


def test_analyzer_probe_port_from_manifest():
    hits = analyze_run(_run(PROBE_WS, "deployment failed"))
    assert hits
    assert hits[0].failure_class == "probe_misconfiguration"
    assert hits[0].category == "supported"
    assert hits[0].confidence >= 0.9


def test_diagnose_probe_without_llm(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    result = diagnose(_run(PROBE_WS, "Readiness probe failed for payments-api"))
    validate_agent("diagnosis_result.json", result)
    assert result["classification"]["failure_class"] == "probe_misconfiguration"
    assert result["selected_hypothesis_id"] == "hyp-probe-port"
    assert result["analyzer"]["mode"] == "deterministic"
    assert result["confidence"] >= 0.7


def test_diagnose_bad_image(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    result = diagnose(_run(BAD_IMAGE_WS, "ImagePullBackOff: manifest unknown"))
    assert result["classification"]["failure_class"] == "bad_image_reference"
    assert result["selected_hypothesis_id"] == "hyp-bad-image"


def test_diagnose_missing_configmap(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    result = diagnose(
        _run(MISSING_CM_WS, "CreateContainerConfigError: key DATABASE_URL not found")
    )
    assert result["classification"]["failure_class"] == "invalid_missing_config"


def test_diagnose_blocked_secret(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    result = diagnose(
        {
            "evidence": [
                {
                    "evidence_id": "ev-s",
                    "kind": "other",
                    "source": {"system": "fixture", "ref": "t"},
                    "summary": "needs secret",
                    "content_excerpt": "Failure requires production secret values to reproduce",
                    "redacted": True,
                    "provenance": {"collector": "test", "query": "t"},
                    "collected_at": "2026-08-10T12:00:00Z",
                }
            ]
        }
    )
    assert result["classification"]["category"] == "blocked"
    assert result["selected_hypothesis_id"] is None


def test_diagnose_low_confidence_threshold(monkeypatch):
    monkeypatch.setenv("RAPHAEL_LLM_DIAGNOSIS", "0")
    monkeypatch.setenv("RAPHAEL_DIAGNOSIS_CONFIDENCE_THRESHOLD", "0.99")
    result = diagnose(
        {
            "evidence": [
                {
                    "evidence_id": "ev-1",
                    "kind": "ci_log",
                    "source": {"system": "fixture", "ref": "t"},
                    "summary": "vague failure",
                    "content_excerpt": "something broke in the cluster",
                    "redacted": True,
                    "provenance": {"collector": "test", "query": "t"},
                    "collected_at": "2026-08-10T12:00:00Z",
                }
            ]
        }
    )
    assert result["selected_hypothesis_id"] is None
    assert result["classification"]["category"] in {"unknown", "supported"}
