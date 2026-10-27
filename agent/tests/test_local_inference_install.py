"""A real installation replayed outside the source tree, with networking denied."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_clean_installed_runtime_outside_repository(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(ROOT / "agent" / "pyproject.toml", source)
    shutil.copytree(
        ROOT / "agent" / "raphael_agent",
        source / "raphael_agent",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(ROOT / "contracts", tmp_path / "contracts")
    target = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-build-isolation",
            "--target",
            str(target),
            str(source),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    # Wheel installation must preserve every public contract byte, including refs.
    for family in ("agent", "sandbox"):
        for original in (ROOT / "contracts" / family).glob("*.json"):
            assert (
                target / "share/raphael/contracts" / family / original.name
            ).read_bytes() == original.read_bytes()
    # Destroy the build source so an accidental editable/source import cannot pass.
    shutil.rmtree(source)
    shutil.rmtree(tmp_path / "contracts")
    shutil.copytree(ROOT / "models", tmp_path / "deployment-models")
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "local_inference", tmp_path / "cases"
    )
    shutil.copyfile(
        Path(__file__).parent / "fixtures/incident_isolation/public-sources.json",
        tmp_path / "cases/source-verification.json",
    )
    script = r"""
import json, os, pathlib, socket, sys

def offline(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.bind"}:
        raise AssertionError("runtime attempted networking")

sys.addaudithook(offline)
before = list(sys.path)
from raphael_agent.model_gateway import ModelGateway, model_error
from raphael_agent.local_inference import predict
from raphael_agent.incident_scope import configured_scope
assert pathlib.Path(predict.__file__).is_relative_to(pathlib.Path("installed").resolve())
from raphael_agent.schema_util import CONTRACTS_ROOT, validate_agent
assert CONTRACTS_ROOT.is_relative_to(pathlib.Path("installed").resolve())
# A schema lookup must succeed after both checkout/build sources are removed.
try:
    validate_agent("fault_candidate.json", {})
except Exception as exc:
    from jsonschema import ValidationError
    assert isinstance(exc, ValidationError), type(exc).__name__
else:
    raise AssertionError("installed schema accepted an invalid candidate")

gateway = ModelGateway()
assert not gateway.enabled
assert gateway.classify_failure({}) is None
os.environ["RAPHAEL_MODEL_ENABLED"] = "1"
methods = {
    "failure_classifier": "classify_failure", "candidate_ranker": "rank_candidates",
    "incident_similarity": "retrieve_incidents", "patch_selector": "select_patch",
    "trace_anomaly": "detect_trace",
}
for name, method in methods.items():
    results = []
    for line in pathlib.Path(f"cases/{name}.jsonl").read_text().splitlines():
        payload = json.loads(line)["input"]
        if name == "candidate_ranker":
            payload = payload["candidates"]
        result = gateway._invoke(method, payload, scope=configured_scope() if name == "incident_similarity" else None)
        assert result is not None, (name, model_error(gateway))
        results.append(result)
    assert any(r["learned_execution"] for r in results), name
# Exercise the public gateway authorization/projection after installation too.
available = {row["url"] for row in json.loads(pathlib.Path("cases/source-verification.json").read_text())["sources"] if row["verified"]}
for tenant, company, client in (
    ("fixture-tenant-a", "fixture-company-a", "fixture-client-a1"),
    ("fixture-tenant-a", "fixture-company-a", "fixture-client-a2"),
    ("fixture-tenant-b", "fixture-company-b", "fixture-client-b1"),
    ("fixture-tenant-b", "fixture-company-b", "fixture-client-b2"),
):
    os.environ.update(RAPHAEL_AGENT_TENANT_ID=tenant, RAPHAEL_COMPANY_ID=company, RAPHAEL_CLIENT_ID=client)
    for line in pathlib.Path("cases/incident_similarity.jsonl").read_text().splitlines():
        case = json.loads(line)
        payload = case["input"]
        state = {"tenant_id": tenant, "company_id": company, "client_id": client,
                 "failure_fingerprint": payload["fingerprint"],
                 "runtime_observation": {"normalized_reason": payload["normalized_reason"]},
                 "evidence": [{"summary": payload["summary"]}]}
        result = gateway.similar_incidents(state)
        assert result and result["learned_execution"]
        if case["source"]["url"] in available:
            assert result["results"]
        assert all(row["source_url"] in available for row in result["results"])
        assert all(row["client_id"] == client and row["company_id"] == company and row["tenant_id"] == tenant
                   for row in result["results"])
        assert gateway.similar_incidents({**state, "client_id": "forged"}) is None
        assert model_error(gateway) == "incident_scope_mismatch"
    assert gateway._invoke("retrieve_incidents", payload) is None
    assert model_error(gateway) == "incident_scope_unverified"
for key in ("RAPHAEL_AGENT_TENANT_ID", "RAPHAEL_COMPANY_ID", "RAPHAEL_CLIENT_ID"):
    os.environ.pop(key)
assert gateway.similar_incidents(state) is None
assert model_error(gateway) == "incident_scope_unverified"
assert sys.path == before
missing = ModelGateway("absent-models")
assert missing.classify_failure({}) is None
assert model_error(missing) == "artifact_files_unavailable"
print("251 public inputs passed through installed gateway; all five learned paths; offline")
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(target),
        "RAPHAEL_MODEL_ROOT": str(tmp_path / "deployment-models"),
        "RAPHAEL_AGENT_TENANT_ID": "fixture-tenant-a",
        "RAPHAEL_COMPANY_ID": "fixture-company-a",
        "RAPHAEL_CLIENT_ID": "fixture-client-a1",
    }
    env.pop("RAPHAEL_MODEL_ENABLED", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "251 public inputs" in result.stdout
