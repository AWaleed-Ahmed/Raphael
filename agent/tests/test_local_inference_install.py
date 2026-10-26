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
    # Destroy the build source so an accidental editable/source import cannot pass.
    shutil.rmtree(source)
    shutil.copytree(ROOT / "models", tmp_path / "deployment-models")
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "local_inference", tmp_path / "cases"
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
assert pathlib.Path(predict.__file__).is_relative_to(pathlib.Path("installed").resolve())
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
        result = gateway._invoke(method, payload)
        assert result is not None, (name, model_error(gateway))
        results.append(result)
    assert any(r["learned_execution"] for r in results), name
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
