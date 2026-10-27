"""Metric/integrity controls. Synthetic controls are never model quality evidence."""

from __future__ import annotations

import copy
import io
import json
import sys
import tarfile
from pathlib import Path
from typing import Any

import pytest
from raphael_agent.readiness import ReadinessError, canonical_digest, digest_file
from raphael_agent.readiness_metrics import file_rank, ranking_metrics, wilson
from scripts import evaluate_model_readiness as evaluation


@pytest.mark.parametrize("hits,total", [(0, 0), (0, 3), (1, 3), (3, 3), (50, 100)])
def test_wilson_known_coverage(hits: int, total: int) -> None:
    interval = wilson(hits, total)
    if total == 0:
        assert interval is None
    else:
        assert interval is not None
        assert interval[0] - 1e-12 <= hits / total <= interval[1] + 1e-12
        if total == 100:
            assert interval == pytest.approx([0.40383153, 0.59616847])


def test_invalid_metric_counts_and_empty_samples() -> None:
    with pytest.raises(ValueError, match="invalid_rate_counts"):
        wilson(4, 3)
    assert file_rank(["a", "a", "b"], ["b"]) == 2
    assert file_rank([], ["b"]) is None
    result = ranking_metrics([])
    assert result["arms"]["model"]["mrr"] is None
    assert result["paired_top_1"]["bootstrap_95"] is None


def test_paired_metrics_count_generation_misses_and_cluster_repetitions() -> None:
    # Metric arithmetic controls, not a model inference test.
    cases = [
        {
            "incident_group": "one",
            "relevant_files": ["b"],
            "baseline": ["a", "b"],
            "model": ["b", "a"],
        },
        {
            "incident_group": "one",
            "relevant_files": ["b"],
            "baseline": ["a", "b"],
            "model": ["b", "a"],
        },
        {
            "incident_group": "two",
            "relevant_files": ["b"],
            "baseline": ["b", "a"],
            "model": ["a", "b"],
        },
        {
            "incident_group": "three",
            "relevant_files": ["b"],
            "baseline": [],
            "model": [],
        },
    ]
    result = ranking_metrics(cases)
    assert result["arms"]["baseline"]["top_1"] == 0.25
    assert result["arms"]["model"]["top_1"] == 0.5
    assert result["arms"]["model"]["candidate_generation_hits"] == 3
    assert result["arms"]["model"]["conditional_top_1"] == 2 / 3
    assert result["paired_top_1"]["wins"] == 2
    assert result["paired_top_1"]["regressions"] == 1
    assert result["paired_top_1"]["ties"] == 1
    assert result["paired_top_1"]["incident_clusters"] == 3
    assert ranking_metrics(cases) == result
    cases[0]["model"].append("injected")
    with pytest.raises(ValueError, match="ranking_candidate_paths_differ"):
        ranking_metrics(cases)


def test_real_protocol_and_input_selection(tmp_path: Path) -> None:
    manifest, _ = evaluation.context()
    assert len(manifest["cases"]) == 12
    case = manifest["cases"][0]
    assert (
        evaluation.input_file(case, tmp_path, "buggy-source.tar.gz").name
        == "buggy-source.tar.gz"
    )
    with pytest.raises(ReadinessError, match="input_selection_ambiguous"):
        evaluation.input_file(case, tmp_path, "fixed-source.tar.gz")
    evaluation.write_json(tmp_path / "new.json", {"a": 1})
    with pytest.raises(FileExistsError):
        evaluation.write_json(tmp_path / "new.json", {})


def make_tar(path: Path, members: list[tuple[str, bytes | None]]) -> None:
    """Build malformed archive controls; no downloaded code is executed."""
    with tarfile.open(path, "w:gz") as archive:
        for name, body in members:
            entry = tarfile.TarInfo(name)
            if body is None:
                entry.type = tarfile.SYMTYPE
                entry.linkname = "/etc/passwd"
                archive.addfile(entry)
            else:
                entry.size = len(body)
                archive.addfile(entry, io.BytesIO(body))


def test_archive_and_stack_projection_exclude_test_oracle(tmp_path: Path) -> None:
    archive = tmp_path / "source.tar.gz"
    make_tar(
        archive,
        [
            ("original/src/app.py", b"# existence control"),
            ("original/tests/test_app.py", b"# test control"),
        ],
    )
    workspace = evaluation.buggy_workspace(archive, tmp_path / "tree")
    log = "\n".join(  # noqa: FLY002 - readable attack-control lines
        [
            '  File "/old/original/src/app.py", line 5, in fail',
            "    expected_fix_is_here()",
            '  File "/old/original/tests/test_app.py", line 6, in test_fix',
            '  File "/old/original/../escape.py", line 7, in escape',
            '  File "/old/original/missing.py", line 8, in missing',
            '  File "/outside/wrong.py", line 9, in outside',
            "src/app.py:4: AssertionError",
        ]
    )
    assert (
        evaluation.application_stack(log, workspace)
        == '  File "src/app.py", line 5, in fail'
    )
    assert evaluation.application_stack("pytest assertion only", workspace) == ""
    make_tar(archive, [("original/link", None)])
    with pytest.raises(ReadinessError, match="links_or_special"):
        evaluation.buggy_workspace(archive, tmp_path / "linked")
    make_tar(archive, [("one/a.py", b""), ("two/a.py", b"")])
    with pytest.raises(ReadinessError, match="root_invalid"):
        evaluation.buggy_workspace(archive, tmp_path / "two-roots")


@pytest.mark.parametrize(
    "header,count",
    [("timestamp,duration", 3), ("service_name,operation,latency_ms", 1005)],
)
def test_telemetry_prefix_does_not_invent_units_or_baselines(
    tmp_path: Path, header: str, count: int
) -> None:
    path = tmp_path / "native.csv"
    path.write_text(header + "\n" + "a,b,1\n" * count)
    result = evaluation.telemetry_contract(path)
    assert result["prefix_rows_inspected"] == min(count, 1000)
    assert result["compatible"] == (count == 1005)
    assert result["prediction_executed"] is False
    assert result["verified_healthy_baseline"] is False


@pytest.fixture
def control_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """Sealing controls with original source identities but no positive ML claims."""
    manifest, protocol = evaluation.context()
    manifest = copy.deepcopy(manifest)
    manifest["cases"] = [c for c in manifest["cases"] if c["id"].startswith("K")]
    monkeypatch.setattr(evaluation, "context", lambda: (manifest, protocol))
    monkeypatch.setattr(evaluation, "verify_evidence", lambda *args: {"verified": True})

    def control_rows(case: dict[str, Any], *_: Any) -> list[dict[str, Any]]:
        inputs = [
            {k: f[k] for k in ("path", "sha256", "bytes")}
            for f in case["files"]
            if f["role"] == "input"
        ]
        return [
            {
                "case_id": case["id"],
                "capability": capability,
                "model_enabled": mode,
                "split": case["split"],
                "incident_group": case["incident_group"],
                "inputs": inputs,
                "input_sha256": canonical_digest(inputs),
                "adapter_input_sha256": "control",
                "candidate_input_sha256": "control",
                "output": {"model_result": None, "fault_candidates": []},
            }
            for capability in case["capabilities"]
            for mode in (False, True)
        ]

    monkeypatch.setattr(evaluation, "run_case", control_rows)
    directory = tmp_path / "sealed"
    evaluation.predict(tmp_path, directory)
    return manifest, protocol, directory


def test_seal_control_round_trip_and_no_invented_quality(
    control_snapshot: tuple[dict[str, Any], dict[str, Any], Path], tmp_path: Path
) -> None:
    manifest, protocol, directory = control_snapshot
    rows, seal = evaluation.validate_predictions(directory, manifest, protocol)
    assert len(rows) == 36
    assert seal["status"] == "development_predictions_sealed_not_scored"
    summary = evaluation.score(directory, tmp_path, tmp_path / "score")
    assert all(
        c["final_quality_metrics"] is None for c in summary["capabilities"].values()
    )
    assert summary["validated_raphael_repairs"] == 0
    with pytest.raises(ReadinessError, match="not_empty"):
        evaluation.predict(tmp_path, directory)


@pytest.mark.parametrize(
    "damage",
    [
        "bytes",
        "manifest",
        "protocol",
        "policy",
        "runtime",
        "source",
        "reproduction",
        "count",
        "duplicate",
        "mode",
        "input",
        "digest",
        "split",
        "group",
        "paired",
    ],
)
def test_tampered_or_incomplete_experiments_refuse(
    control_snapshot: tuple[dict[str, Any], dict[str, Any], Path], damage: str
) -> None:
    manifest, protocol, directory = control_snapshot
    seal = json.loads((directory / "seal.json").read_text())
    path = directory / "predictions.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if damage == "bytes":
        path.write_text(path.read_text() + "\n")
    elif damage in {
        "manifest",
        "protocol",
        "policy",
        "runtime",
        "source",
        "reproduction",
        "count",
    }:
        key = {
            "manifest": "manifest_sha256",
            "protocol": "protocol_sha256",
            "policy": "policy",
            "runtime": "runtime_sources",
            "source": "verifier_sources",
            "reproduction": "reproductions_sha256",
            "count": "row_count",
        }[damage]
        seal[key] = "tampered"
    else:
        if damage == "duplicate":
            rows[1] = rows[0]
        elif damage == "mode":
            rows[0]["model_enabled"] = 0
        elif damage == "input":
            rows[0]["inputs"][0]["path"] = "oracle.json"
        elif damage == "digest":
            rows[0]["input_sha256"] = "tampered"
        elif damage == "split":
            rows[0]["split"] = "final_test"
        elif damage == "group":
            rows[0]["incident_group"] = "other"
        else:
            rows[1]["candidate_input_sha256"] = "tampered"
            # Order permutation must not avoid checking every pair.
            rows = rows[::2] + rows[1::2]
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        seal["predictions_sha256"] = digest_file(path)
    (directory / "seal.json").write_text(json.dumps(seal))
    with pytest.raises(ReadinessError):
        evaluation.validate_predictions(directory, manifest, protocol)


def test_development_runner_never_accepts_final_test(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest, protocol = evaluation.context()
    manifest["cases"][0]["split"] = "final_test"
    monkeypatch.setattr(evaluation, "context", lambda: (manifest, protocol))
    monkeypatch.setattr(evaluation, "verify_evidence", lambda *args: {})
    with pytest.raises(ReadinessError, match="rejects_final_test"):
        evaluation.predict(tmp_path, tmp_path / "out")


def test_cli_score_requires_predictions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate", "score", "--cache-root", str(tmp_path), "--output", str(tmp_path)],
    )
    with pytest.raises(SystemExit) as result:
        evaluation.main()
    assert result.value.code == 2


def test_cli_bounded_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate",
            "predict",
            "--cache-root",
            str(tmp_path),
            "--output",
            str(tmp_path),
        ],
    )
    monkeypatch.setattr(
        evaluation,
        "predict",
        lambda *args: (_ for _ in ()).throw(ReadinessError("sensitive raw evidence")),
    )
    with pytest.raises(SystemExit) as result:
        evaluation.main()
    assert result.value.code == 1
    assert "sensitive" not in capsys.readouterr().err


def test_optional_original_cache_replay(tmp_path: Path) -> None:
    """Run original public bytes only when explicitly supplied; never synthesize them."""
    import os

    cache_value = os.environ.get("RAPHAEL_READINESS_CACHE")
    if not cache_value:
        pytest.skip("Original multi-GB cache not redistributed in unit tests")
    cache = Path(cache_value)
    predicted = tmp_path / "original-predictions"
    evaluation.predict(cache, predicted)
    summary = evaluation.score(predicted, cache, tmp_path / "original-score")
    assert len(summary["ranking_cases"]) == 3
    assert summary["validated_raphael_repairs"] == 0
    assert all(
        row["final_quality_metrics"] is None for row in summary["capabilities"].values()
    )


def test_bounded_outcomes_and_seed() -> None:
    manifest, _ = evaluation.context()
    state = evaluation.seed(next(c for c in manifest["cases"] if c["id"] == "O01"))
    assert state["commit_sha"] == "0" * 40
    assert "failure_class_hint" not in state
    assert evaluation.outcome({}, "trace_anomaly")["validated_repairs"] == 0


def test_reproduction_log_rejects_changed_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest, _ = evaluation.context()
    case = next(c for c in manifest["cases"] if c["id"] == "B01")
    (tmp_path / "B01").mkdir()
    (tmp_path / "B01/buggy-reproduction.log").write_text("tampered log control")
    with pytest.raises(ReadinessError, match="not_phase1_original"):
        evaluation.run_case(case, tmp_path, tmp_path)


def test_cli_success_dispatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        evaluation, "predict", lambda *args: {"status": "control_predict"}
    )
    monkeypatch.setattr(evaluation, "score", lambda *args: {"status": "control_score"})
    for stage in ("predict", "score"):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "evaluate",
                stage,
                "--cache-root",
                str(tmp_path),
                "--predictions",
                str(tmp_path),
                "--output",
                str(tmp_path),
            ],
        )
        evaluation.main()
        assert json.loads(capsys.readouterr().out)["status"] == "control_" + stage


def test_committed_original_evidence_is_bound_and_metrics_recompute() -> None:
    """Offline evidence audit; does not claim to re-fetch the original source cache."""
    manifest, protocol = evaluation.context()
    directory = evaluation.ROOT / "docs/evidence/issue-78/phase-2"
    rows, _ = evaluation.validate_predictions(directory, manifest, protocol)
    summary = json.loads((directory / "summary.json").read_text())
    assert len(rows) == 48
    assert summary["prediction_seal_sha256"] == digest_file(directory / "seal.json")
    assert summary["capabilities"]["candidate_ranker"][
        "development_file_oracle_metrics"
    ] == ranking_metrics(summary["ranking_cases"])
    assert all(
        c["decision"] == "keep_deferred" for c in summary["capabilities"].values()
    )
    assert all(
        c["final_quality_metrics"] is None for c in summary["capabilities"].values()
    )
    for case in manifest["cases"]:
        oracle = {f["path"] for f in case["files"] if f["role"] == "oracle"}
        assert all(
            not oracle.intersection(f["path"] for f in r["inputs"])
            for r in rows
            if r["case_id"] == case["id"]
        )
