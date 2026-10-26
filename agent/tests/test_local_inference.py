"""Real public-input replay and pre-deserialization trust boundary controls."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import joblib
import pytest
from raphael_agent.incident_scope import configured_scope
from raphael_agent.local_inference import artifacts, predict
from raphael_agent.model_gateway import ModelGateway, model_error

ROOT = Path(__file__).resolve().parents[2]
CASES = Path(__file__).parent / "fixtures" / "local_inference"
METHODS = {
    "failure_classifier": "classify_failure",
    "candidate_ranker": "rank_candidates",
    "incident_similarity": "retrieve_incidents",
    "patch_selector": "select_patch",
    "trace_anomaly": "detect_trace",
}


def replay(name: str, root: Path = ROOT / "models") -> list[dict[str, Any]]:
    """Replay public cases without replacing estimators or predictions."""
    results = []
    for line in (CASES / f"{name}.jsonl").read_text().splitlines():
        case = json.loads(line)
        assert case["source"]["url"].startswith("https://")
        payload = case["input"]
        function = getattr(predict, METHODS[name])
        if name == "candidate_ranker":
            result = function(root, payload["candidates"])
            assert {row["candidate_path"] for row in result["candidates"]} == {
                row["candidate_path"] for row in payload["candidates"]
            }
            assert all(0 <= row["learned_score"] <= 1 for row in result["candidates"])
        elif name == "incident_similarity":
            result = function(root, payload, 5, scope=configured_scope())
            sources = json.loads(
                (
                    Path(__file__).parent
                    / "fixtures/incident_isolation/public-sources.json"
                ).read_text()
            )
            available = {item["url"] for item in sources["sources"] if item["verified"]}
            if case["source"]["url"] in available:
                assert result["results"]
            assert all(row["source_url"] in available for row in result["results"])
            assert all(0 <= row["similarity"] <= 1.000001 for row in result["results"])
        else:
            result = function(root, payload)
        if name == "failure_classifier":
            assert result["model_failure_class"]
            assert result["alternatives"]
        if name == "trace_anomaly":
            assert 0 <= result["learned_anomaly_probability"] <= 1
        if name == "patch_selector" and result.get("policy_allowed"):
            assert result["requires_sandbox_validation"]
        results.append(result)
    return results


@pytest.mark.parametrize("name", METHODS)
def test_public_inputs_execute_real_learned_paths(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAPHAEL_AGENT_TENANT_ID", "fixture-tenant-a")
    monkeypatch.setenv("RAPHAEL_COMPANY_ID", "fixture-company-a")
    monkeypatch.setenv("RAPHAEL_CLIENT_ID", "fixture-client-a1")
    results = replay(name)
    assert len(results) >= 50
    assert any(result["learned_execution"] for result in results)
    if name in {"failure_classifier", "patch_selector", "trace_anomaly"}:
        assert any(result.get("rule_based") for result in results)
    if name == "patch_selector":
        assert results[-1]["learned_execution"]
        assert not results[-1]["rule_based"]


def test_verified_estimators_are_reused() -> None:
    artifacts._load_bundle.cache_clear()
    first = artifacts.load_bundle(ROOT / "models", "failure_classifier")
    second = artifacts.load_bundle(ROOT / "models", "failure_classifier")
    assert first is second
    assert artifacts._load_bundle.cache_info().hits == 1


@pytest.mark.parametrize("name", ["failure_classifier", "incident_similarity"])
@pytest.mark.parametrize(
    "damage", ["missing", "corrupt", "manifest", "forged_pair", "oversized"]
)
def test_untrusted_files_never_reach_deserializer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, damage: str, name: str
) -> None:
    model = tmp_path / name
    shutil.copytree(ROOT / "models" / name, model)
    expected = "artifact_hash_mismatch"
    if damage == "missing":
        (model / "model.joblib").unlink()
        expected = "artifact_files_unavailable"
    elif damage == "manifest":
        (model / "manifest.json").write_text("{}")
        expected = "manifest_hash_mismatch"
    else:
        malicious = b"unapproved pickle bytes"
        if damage == "oversized":
            malicious = b"x" * (artifacts.TRUSTED_ARTIFACTS[name][2] + 1)
        (model / "model.joblib").write_bytes(malicious)
        if damage == "forged_pair":
            manifest = json.loads((model / "manifest.json").read_text())
            manifest["artifact_sha256"] = hashlib.sha256(malicious).hexdigest()
            manifest["artifact_bytes"] = len(malicious)
            (model / "manifest.json").write_text(json.dumps(manifest))
            expected = "manifest_hash_mismatch"

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("untrusted bytes reached joblib.load")

    monkeypatch.setattr(joblib, "load", forbidden)
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway(tmp_path)
    if name == "incident_similarity":
        monkeypatch.setenv("RAPHAEL_AGENT_TENANT_ID", "fixture-tenant-a")
        monkeypatch.setenv("RAPHAEL_COMPANY_ID", "fixture-company-a")
        monkeypatch.setenv("RAPHAEL_CLIENT_ID", "fixture-client-a1")
        assert gateway.similar_incidents({"tenant_id": "fixture-tenant-a"}) is None
    else:
        assert gateway.classify_failure({}) is None
    assert model_error(gateway) == expected


def test_incompatible_versions_rejected_before_deserialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifacts._load_bundle.cache_clear()
    monkeypatch.setattr(artifacts, "version", lambda name: "unqualified")
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway(ROOT / "models")
    assert gateway.classify_failure({}) is None
    assert model_error(gateway) == "incompatible_runtime_dependencies"
    monkeypatch.setattr(sys, "version_info", (3, 13))
    with pytest.raises(
        artifacts.ArtifactUnavailable, match="unsupported_python_version"
    ):
        artifacts.check_compatibility()


def test_deserialization_failure_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    artifacts._load_bundle.cache_clear()

    def broken(*args: Any, **kwargs: Any) -> None:
        raise ValueError("sensitive arbitrary file contents")

    monkeypatch.setattr(joblib, "load", broken)
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway(ROOT / "models")
    assert gateway.classify_failure({}) is None
    assert model_error(gateway) == "artifact_deserialization_failed"


@pytest.mark.parametrize(
    "name,legacy_format", [("failure_classifier", 999), ("incident_similarity", 1)]
)
def test_unsupported_bundle_format_is_bounded(
    monkeypatch: pytest.MonkeyPatch, name: str, legacy_format: int
) -> None:
    artifacts._load_bundle.cache_clear()
    monkeypatch.setattr(joblib, "load", lambda *args: {"format_version": legacy_format})
    with pytest.raises(
        artifacts.ArtifactUnavailable, match="unsupported_artifact_format"
    ):
        artifacts.load_bundle(ROOT / "models", name)


def test_unknown_model_is_rejected() -> None:
    with pytest.raises(artifacts.ArtifactUnavailable, match="unknown_model"):
        artifacts.load_bundle(ROOT / "models", "../../customer")


def test_default_off_does_not_import_prediction_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAPHAEL_MODEL_ENABLED", raising=False)
    gateway = ModelGateway(ROOT / "models")
    assert gateway.classify_failure({}) is None
    assert gateway._predict_module is None
    assert model_error(gateway) == "disabled_by_environment"


def test_unknown_failure_abstains_and_unknown_patch_is_denied() -> None:
    assert predict.classify_failure(ROOT / "models", {"evidence_text": "unrecognized"})[
        "abstained"
    ]
    patch = predict.select_patch(ROOT / "models", {"failure_class": "unknown"})
    assert not patch["policy_allowed"]
    assert not patch["learned_execution"]


def test_import_failure_diagnostic_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(name: str) -> None:
        raise ImportError("sensitive environment path")

    monkeypatch.setattr("raphael_agent.model_gateway.importlib.import_module", broken)
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway()
    assert gateway.classify_failure({}) is None
    assert model_error(gateway) == "ImportError"


def test_patch_policy_estimator_on_public_probe_evidence() -> None:
    """Exercise policy probabilities separately when runtime confidence abstains."""
    case = json.loads((CASES / "patch_selector.jsonl").read_text().splitlines()[-1])
    bundle = artifacts.load_bundle(ROOT / "models", "patch_selector")
    template = bundle["template"]
    probabilities = template["classifier"].predict_proba(
        predict.matrix(bundle, [case["input"]], template)
    )[0]
    selected = str(template["classifier"].classes_[probabilities.argmax()])
    policy = bundle["policy"]
    policy_probabilities = policy["classifier"].predict_proba(
        predict.matrix(bundle, [{**case["input"], "safe_template": selected}], policy)
    )[0]
    assert all(0 <= value <= 1 for value in policy_probabilities)
    assert sum(policy_probabilities) == pytest.approx(1)
    # This component test does not override the runtime's low-confidence refusal.
    assert not predict.select_patch(ROOT / "models", case["input"])["policy_allowed"]


def test_missing_deployment_can_recover_without_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "1")
    gateway = ModelGateway(tmp_path)
    assert gateway.classify_failure({}) is None
    assert model_error(gateway) == "artifact_files_unavailable"
    shutil.copytree(
        ROOT / "models" / "failure_classifier", tmp_path / "failure_classifier"
    )
    result = gateway.classify_failure({"evidence": [{"summary": "OOMKilled"}]})
    assert result is not None and result["learned_execution"]
    assert model_error(gateway) is None


def test_scoped_fixture_reproduces_release_bytes(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "agent/scripts/build_scoped_incident_fixture.py"),
            "--source",
            str(CASES / "incident_similarity.jsonl"),
            "--source-verification",
            str(CASES.parent / "incident_isolation/public-sources.json"),
            "--output",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
    )
    for filename in ("manifest.json", "model.joblib"):
        assert (tmp_path / filename).read_bytes() == (
            ROOT / "models/incident_similarity" / filename
        ).read_bytes()
