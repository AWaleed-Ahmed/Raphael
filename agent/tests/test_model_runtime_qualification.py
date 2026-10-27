"""Real-artifact runtime regression tests; injected controls are not accuracy cases."""

from __future__ import annotations

import copy
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from scripts import qualify_model_runtime as runtime
from scripts import qualify_model_runtime_faults as faults

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "agent/tests/fixtures/local_inference"
OWNER = {
    "tenant_id": "fixture-tenant-a",
    "company_id": "fixture-company-a",
    "client_id": "fixture-client-a1",
}


@pytest.fixture
def configured_runtime() -> Iterator[None]:
    with patch.dict(os.environ):
        runtime.configure(True)
        yield


def public_jobs() -> list[dict[str, Any]]:
    """Use existing source-linked projections only for operational regression."""
    from scripts.qualify_model_graph import canonical

    jobs = []
    for name in (
        "failure_classifier",
        "candidate_ranker",
        "incident_similarity",
        "trace_anomaly",
        "patch_selector",
    ):
        rows = (CASES / (name + ".jsonl")).read_text().splitlines()
        case = json.loads(rows[-1] if name == "patch_selector" else rows[0])
        payload = case["input"]
        state = {
            **OWNER,
            "runtime_observation": payload,
            "failure_fingerprint": payload.get("fingerprint"),
            "evidence": [
                {
                    "summary": payload.get("summary")
                    or payload.get("evidence_text")
                    or ""
                }
            ],
            "diagnosis": {
                "classification": {"failure_class": payload.get("failure_class")}
            },
            "fault_candidates": [
                {
                    "candidate_type": payload.get("candidate_type"),
                    "symbol": payload.get("manifest_field"),
                    "path": "",
                }
            ],
        }
        jobs.append(
            {
                "id": name,
                "capability": name,
                "state": state,
                "candidates": canonical(payload.get("candidates") or []),
            }
        )
    return jobs


def test_nearest_rank_tails_and_finite_hashes() -> None:
    assert runtime.quantiles(list(range(1, 101))) == {
        "p50": 50,
        "p95": 95,
        "p99": 99,
        "max": 100,
    }
    assert all(v is None for v in runtime.quantiles([]).values())
    assert runtime.digest({"b": 1, "a": 2}) == runtime.digest({"a": 2, "b": 1})
    with pytest.raises(ValueError):
        runtime.digest({"bad": float("nan")})


def test_all_five_real_gateway_calls_and_disabled_mode(configured_runtime) -> None:
    jobs = public_jobs()
    for job in jobs:
        result = runtime.execute(job, ROOT / "models")
        assert result["unavailable_reason"] is None
        assert result["learned_execution"], job["id"]
    with pytest.raises(ValueError, match="unknown_capability"):
        runtime.execute({**jobs[0], "capability": "unknown"}, ROOT / "models")
    runtime.configure(False)
    for job in jobs:
        result = runtime.execute(job, ROOT / "models")
        assert result["learned_execution"] is False
        assert result["unavailable_reason"] == "disabled_by_environment"


def test_bounded_load_has_no_loss_or_serial_mismatch(
    tmp_path: Path, configured_runtime
) -> None:
    report = runtime.load(
        public_jobs(),
        ROOT / "models",
        tmp_path / "load",
        concurrency=4,
        warmup=0,
        duration=0.25,
        period=0.00001,
    )
    counts = report["counts"]
    assert counts["steady_accepted_jobs"] == counts["steady_completed_jobs"] > 0
    assert counts["steady_output_mismatches"] == 0
    assert counts["steady_runtime_errors"] == 0
    assert counts["steady_missed_schedule_ticks"] > 0
    assert len((tmp_path / "load/resource-series.jsonl").read_text().splitlines()) > 0
    assert set(report["gateway_latency_ms"]) == {j["capability"] for j in public_jobs()}


@pytest.mark.parametrize(
    "settings", [{"concurrency": 0}, {"duration": 0}, {"warmup": -1}, {"period": 0}]
)
def test_invalid_load_profiles_refuse_before_execution(
    tmp_path: Path, settings: dict[str, Any]
) -> None:
    profile = {
        "concurrency": 1,
        "duration": 0.01,
        "warmup": 0,
        "period": 0.001,
        **settings,
    }
    with pytest.raises(ValueError, match="invalid_load_profile"):
        runtime.load(public_jobs(), ROOT / "models", tmp_path / "invalid", **profile)


def test_warm_measurement_keeps_execution_and_availability_counts(
    configured_runtime,
) -> None:
    report = runtime.warm(public_jobs(), ROOT / "models", 3)
    assert all(r["calls"] == 3 and r["learned_calls"] == 3 for r in report.values())
    assert all(r["unavailable"] == {None: 3} for r in report.values())


@pytest.mark.parametrize("mode", ["probe", "warm", "load", "hold", "oom"])
def test_cli_modes_write_no_false_success_on_interruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps({"jobs": public_jobs()}))
    output = tmp_path / "output"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runtime",
            mode,
            "--jobs",
            str(jobs),
            "--model-root",
            str(ROOT / "models"),
            "--output",
            str(output),
            "--enabled",
            "--warmup",
            "0",
            "--duration",
            ".02",
            "--repeats",
            "1",
        ],
    )
    # Unit-control dispatcher test; installed-process probes enforce the real hook.
    monkeypatch.setattr(sys, "addaudithook", lambda hook: None)
    with patch.dict(os.environ):
        if mode == "hold":
            monkeypatch.setattr(
                runtime,
                "mixed_job",
                lambda *args: (_ for _ in ()).throw(InterruptedError("control")),
            )
        elif mode == "oom":
            monkeypatch.setattr(
                runtime,
                "bytearray",
                lambda *args: (_ for _ in ()).throw(MemoryError("control")),
                raising=False,
            )
        if mode in {"hold", "oom"}:
            with pytest.raises((InterruptedError, MemoryError)):
                runtime.main()
            assert json.loads(output.read_text())["status"] == "started_not_completed"
        else:
            runtime.main()


def test_real_fault_and_concurrent_isolation_controls(configured_runtime) -> None:
    job = next(j for j in public_jobs() if j["capability"] == "failure_classifier")
    # Original public input; repetitions exercise operational controls only.
    cases = [{"id": str(i), "state": copy.deepcopy(job["state"])} for i in range(3)]
    report = faults.controls(cases, ROOT / "models")
    assert len(report) == 38
    assert all(r.get("deserializer_calls_for_invalid_bytes", 0) == 0 for r in report)
    isolated = faults.isolation(cases, ROOT / "models")
    assert len(isolated) == 96 and not any(r["ownership_violation"] for r in isolated)
    concurrent = faults.concurrent_faults(cases, ROOT / "models")
    assert len(concurrent["denied"]) == 24
    assert all(concurrent["subsequent_real_predictions_available"])


def test_real_report_graph_and_network_refusal_controls(
    tmp_path: Path, configured_runtime, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAPHAEL_MODEL_ROOT", str(ROOT / "models"))
    original = json.loads(
        (CASES / "failure_classifier.jsonl").read_text().splitlines()[0]
    )
    state = {
        **OWNER,
        "trigger": {"kind": "github_issue"},
        "repository": {"owner": "public-source", "name": "operational-control"},
        "commit_sha": "operational-control",
        "issue_body": original["input"].get("evidence_text")
        or original["source"].get("body_excerpt", ""),
    }
    result = faults.graph_guards([{"id": "public-report", "state": state}])
    assert len(result) == 2 and result[0]["patch_proposals"] == 0
    assert result[1]["healthy_baselines_fabricated"] == 0


def test_fault_cli_serializes_bounded_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = {"id": "original-public", "state": public_jobs()[0]["state"]}
    source = tmp_path / "cases.json"
    source.write_text(json.dumps({"faults": [case], "safety": [case]}))
    out = tmp_path / "faults.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "faults",
            "--cases",
            str(source),
            "--model-root",
            str(ROOT / "models"),
            "--output",
            str(out),
        ],
    )
    monkeypatch.setattr(
        faults, "graph_guards", lambda cases: []
    )  # Only serializer branch; real graph test above.
    with patch.dict(os.environ):
        faults.main()
    assert json.loads(out.read_text())["kind"] == "operational_controls_not_accuracy"


def test_preparation_refuses_missing_original_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import prepare_model_runtime as preparation

    output = tmp_path / "private"
    monkeypatch.setattr(
        sys,
        "argv",
        ["prepare", "--cache-root", str(tmp_path / "missing"), "--output", str(output)],
    )
    with pytest.raises(SystemExit) as error:
        preparation.main()
    assert error.value.code == 1
    assert "runtime_preparation_input_invalid" in capsys.readouterr().err
    assert not output.exists()


def test_optional_preparation_from_original_sources(tmp_path: Path) -> None:
    from scripts import prepare_model_runtime as preparation

    cache = os.environ.get("RAPHAEL_READINESS_CACHE")
    if not cache:
        pytest.skip("Original multi-GB source cache is not redistributed")
    output = tmp_path / "private"
    metadata = preparation.prepare(Path(cache), output)
    assert len(metadata["jobs"]) == 24
    assert {row["id"] for row in metadata["excluded"]} == {"B02", "O01", "O02", "O03"}
    assert all(
        "state" not in row and "candidates" not in row for row in metadata["jobs"]
    )
    bundle = json.loads((output / "fault-cases.json").read_text())
    assert [row["id"] for row in bundle["faults"]] == ["K01", "B02", "O03"]
    assert {row["id"] for row in bundle["safety"]} == {"K01", "K03", "K04"}
    with pytest.raises(preparation.ReadinessError, match="output_directory_not_empty"):
        preparation.prepare(Path(cache), output)


def test_committed_runtime_evidence_preserves_failed_gate() -> None:
    """Audit recorded denominators and memory growth, without claiming a new run."""
    import gzip
    import hashlib
    import statistics
    from collections import Counter

    evidence = ROOT / "docs/evidence/issue-78/phase-3"
    seal = json.loads((evidence / "seal.json").read_text())
    for name, expected in seal["files"].items():
        assert (
            hashlib.sha256((evidence / name).read_bytes()).hexdigest() == expected
        ), name
    for name, expected in seal["harness_sources"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    counts: Counter[str] = Counter()
    with gzip.open(evidence / "soak-calls.jsonl.gz", "rt") as source:
        for line in source:
            row = json.loads(line)
            if row["phase"] == "steady":
                counts[row["capability"]] += 1
                assert row["serial_match"] and row["unavailable_reason"] is None
    report = json.loads((evidence / "soak-summary.json").read_text())
    completed = report["counts"]["steady_completed_jobs"]
    assert completed == report["counts"]["steady_accepted_jobs"] == 28788
    assert len(counts) == 5 and set(counts.values()) == {completed}
    with gzip.open(evidence / "soak-resources.jsonl.gz", "rt") as source:
        rows = [json.loads(line) for line in source]
    first = [
        int(r["memory.current"])
        for r in rows
        if r["phase"] == "steady" and r["elapsed_seconds"] < 1200
    ]
    last = [
        int(r["memory.current"])
        for r in rows
        if r["phase"] == "steady" and r["elapsed_seconds"] >= 7200
    ]
    growth = 100 * (statistics.median(last) / statistics.median(first) - 1)
    assessment = json.loads((evidence / "memory-assessment.json").read_text())
    assert (
        growth
        == assessment["memory_growth_percent"]
        > assessment["growth_gate_percent"]
    )
    assert assessment["decision"] == "fail"
    assert (
        json.loads((evidence / "assessment.json").read_text())["status"] == "deferred"
    )
