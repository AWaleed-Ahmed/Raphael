"""Integrity controls over real upstream metadata; no model accuracy fixtures."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from raphael_agent.readiness import (
    ReadinessError,
    audit_source_overlap,
    audit_training,
    canonical_digest,
    digest_file,
    freeze_blockers,
    paired_jobs,
    validate_manifest,
    validate_pair,
    verify_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "agent/fixtures/production_readiness"
SCHEMA = json.loads((SOURCES / "source-manifest.schema.json").read_text())
PROTOCOL = json.loads((SOURCES / "protocol.json").read_text())
SNAPSHOT = json.loads((SOURCES / "source-manifest.json").read_text())


@pytest.fixture
def real_cases(tmp_path: Path) -> tuple[dict[str, Any], Path]:
    """Use three exact BugsInPy test commands as opaque integrity test bytes."""
    manifest = deepcopy(SNAPSHOT)
    manifest["cases"] = [c for c in manifest["cases"] if c["id"].startswith("B")]
    for case in manifest["cases"]:
        item = next(f for f in case["files"] if f["path"].endswith("run_test.sh"))
        path = tmp_path / item["path"]
        path.parent.mkdir(parents=True)
        path.write_bytes(
            (
                ROOT / "agent/tests/fixtures/readiness_commands" / (case["id"] + ".sh")
            ).read_bytes()
        )
        # A unit-control bundle, not incident evidence passed to a model.
        item["role"] = "input"
        case["files"] = [item]
    return manifest, tmp_path


def test_real_source_snapshot_and_protocol_are_prepared_not_scored() -> None:
    validate_manifest(SNAPSHOT, SCHEMA)
    assert len(SNAPSHOT["cases"]) == 12
    jobs = paired_jobs(SNAPSHOT, PROTOCOL)
    assert len(jobs) == 24
    for left, right in zip(jobs[::2], jobs[1::2], strict=True):
        validate_pair(left, right, PROTOCOL)
        assert left["execution_status"] == "prepared_not_executed"
        case = next(c for c in SNAPSHOT["cases"] if c["id"] == left["case_id"])
        oracle_paths = {f["path"] for f in case["files"] if f["role"] == "oracle"}
        assert not oracle_paths & {f["path"] for f in left["inputs"]}
    assert "independent_final_test_not_frozen" in freeze_blockers(SNAPSHOT, PROTOCOL)


def test_three_original_command_hashes_verify(
    real_cases: tuple[dict[str, Any], Path],
) -> None:
    manifest, cache = real_cases
    validate_manifest(manifest, SCHEMA)
    assert verify_evidence(manifest, cache)["files"] == 3
    for case in manifest["cases"]:
        item = case["files"][0]
        assert digest_file(cache / item["path"]) == item["sha256"]


@pytest.mark.parametrize("damage", ["missing", "changed", "symlink"])
def test_evidence_cannot_be_replaced_or_escape_cache(
    real_cases: tuple[dict[str, Any], Path], tmp_path: Path, damage: str
) -> None:
    manifest, cache = real_cases
    target = cache / manifest["cases"][0]["files"][0]["path"]
    content = target.read_bytes()
    target.unlink()
    if damage == "changed":
        target.write_bytes(content.replace(b"python", b"PYTHON"))
    if damage == "symlink":
        outside = tmp_path.parent / (tmp_path.name + "-outside")
        outside.write_bytes(content)
        target.symlink_to(outside)
    with pytest.raises(
        ReadinessError,
        match={
            "missing": "evidence_missing",
            "changed": "evidence_hash_mismatch",
            "symlink": "evidence_outside_cache",
        }[damage],
    ):
        verify_evidence(manifest, cache)


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("schema", "manifest_schema_invalid"),
        ("id", "duplicate_case_id"),
        ("group", "incident_crosses_splits"),
        ("input", "input_missing"),
        ("path", "unsafe_evidence_path"),
        ("absolute", "unsafe_evidence_path"),
        ("windows", "unsafe_evidence_path"),
        ("conflict", "conflicting_evidence_path"),
        ("oracle", "oracle_in_model_input"),
        ("duplicate", "duplicate_input_crosses_splits"),
        ("review", "independent_reviews_missing"),
        ("overlap", "final_test_overlap_unresolved"),
        ("terms", "final_test_evidence_review_missing"),
        ("labels", "reviewed_labels_disagree"),
    ],
)
def test_manifest_leakage_and_provenance_controls(
    real_cases: tuple[dict[str, Any], Path], damage: str, reason: str
) -> None:
    manifest, _ = real_cases
    a, b = manifest["cases"][:2]
    if damage == "schema":
        a["unexpected"] = True
    elif damage == "id":
        b["id"] = a["id"]
    elif damage == "group":
        b.update(incident_group=a["incident_group"], split="regression")
    elif damage == "input":
        a["files"][0]["role"] = "raw"
    elif damage in {"path", "absolute", "windows"}:
        a["files"][0]["path"] = {
            "path": "../outside",
            "absolute": "/outside",
            "windows": "..\\outside",
        }[damage]
    elif damage == "conflict":
        b["files"][0]["path"] = a["files"][0]["path"]
    elif damage == "oracle":
        b["files"].append({**a["files"][0], "path": "oracle.txt", "role": "oracle"})
    elif damage == "duplicate":
        b["files"][0]["sha256"] = a["files"][0]["sha256"]
        b["split"] = "regression"
    else:
        a.update(
            split="final_test",
            overlap={k: "clear" for k in a["overlap"]},
            label_status="adjudicated",
            label_sha256=a["files"][0]["sha256"],
            terms_status="approved",
            input_review="approved",
        )
        # Review identity placeholders only in negative controls, never evidence.
        a["reviews"] = [
            {
                "reviewer_id": f"control-{i}",
                "kind": "human",
                "approved": True,
                "label_sha256": a["label_sha256"],
            }
            for i in range(2)
        ]
        if damage == "review":
            a["reviews"][1]["kind"] = "agent"
        elif damage == "overlap":
            a["overlap"]["training"] = "unknown"
        elif damage == "terms":
            a["terms_status"] = "local_only_pending_review"
        elif damage == "labels":
            a["reviews"][1]["label_sha256"] = "0" * 64
    with pytest.raises(ReadinessError, match=reason):
        validate_manifest(manifest, SCHEMA)


@pytest.mark.parametrize(
    "field", ["inputs", "input_sha256", "protocol_sha256", "baseline", "policy"]
)
def test_paired_comparison_refuses_context_drift(field: str) -> None:
    left, right = paired_jobs(SNAPSHOT, PROTOCOL)[:2]
    right = deepcopy(right)
    right[field] = "changed"
    with pytest.raises(ReadinessError, match="paired_context_mismatch"):
        validate_pair(left, right, PROTOCOL)


def test_both_arms_cannot_silently_rewrite_frozen_protocol() -> None:
    left, right = deepcopy(paired_jobs(SNAPSHOT, PROTOCOL)[:2])
    left["baseline"] = right["baseline"] = {}
    with pytest.raises(ReadinessError, match="pair_not_bound_to_protocol"):
        validate_pair(left, right, PROTOCOL)


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("mode", "invalid_pair_mode"),
        ("same", "pair_modes_not_distinct"),
        ("shape", "pair_shape_invalid"),
        ("hash", "paired_input_digest_mismatch"),
    ],
)
def test_pair_rejects_invalid_modes_shape_and_digest(damage: str, reason: str) -> None:
    left, right = deepcopy(paired_jobs(SNAPSHOT, PROTOCOL)[:2])
    if damage == "mode":
        left["model_enabled"] = 0
    elif damage == "same":
        right["model_enabled"] = False
    elif damage == "shape":
        left["extra"] = right["extra"] = True
    else:
        left["input_sha256"] = right["input_sha256"] = "0" * 64
    with pytest.raises(ReadinessError, match=reason):
        validate_pair(left, right, PROTOCOL)


def test_policy_blocks_learning_external_calls_and_publication() -> None:
    protocol = deepcopy(PROTOCOL)
    protocol["policy"]["learning"] = True
    with pytest.raises(ReadinessError, match="unsafe_evaluation_policy"):
        paired_jobs(SNAPSHOT, protocol)


def test_exclusions_do_not_become_prepared_predictions() -> None:
    manifest = deepcopy(SNAPSHOT)
    manifest["cases"][0]["split"] = "excluded"
    assert len(paired_jobs(manifest, PROTOCOL)) == 22


def test_nonfinite_or_non_json_context_cannot_be_sealed() -> None:
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})
    for value in [float("nan"), object()]:
        with pytest.raises(ReadinessError, match="context_not_finite_json"):
            canonical_digest(value)


def test_training_audit_uses_trusted_hashes_and_reports_unavailable_data(
    tmp_path: Path,
) -> None:
    report = audit_training(ROOT, tmp_path)
    assert all(m["trusted_artifact_matches"] for m in report.values())
    assert report["incident_similarity"]["dataset_files"][0]["hash_matches"]
    assert not report["failure_classifier"]["dataset_files"][0]["available"]
    overlap = audit_source_overlap(ROOT, tmp_path, SNAPSHOT)
    assert overlap["scanned_files"] == 0
    assert overlap["cases"]["K01"]["prior_fixture_url_match"]
    assert not overlap["cases"]["K01"]["index_source_url_match"]
    assert not overlap["cases"]["B01"]["prior_fixture_url_match"]


def test_protocol_approval_needs_an_actual_review_record() -> None:
    protocol = deepcopy(PROTOCOL)
    protocol["approval"]["status"] = "approved"
    assert "protocol_owner_review_pending" in freeze_blockers(SNAPSHOT, protocol)
    assert "candidate_ranker:final_sample_floor_unmet" in freeze_blockers(
        SNAPSHOT, protocol
    )


def test_boolean_policy_cannot_use_integer_aliases() -> None:
    protocol = deepcopy(PROTOCOL)
    protocol["policy"]["learning"] = 0
    with pytest.raises(ReadinessError, match="unsafe_evaluation_policy"):
        paired_jobs(SNAPSHOT, protocol)


def test_baseline_is_bound_to_actual_source_and_artifact_hashes() -> None:
    from raphael_agent.readiness import verify_baseline

    verify_baseline(ROOT, PROTOCOL)
    for field, reason in [
        ("contract", "baseline_contract_drift"),
        ("source", "baseline_source_or_artifact_drift"),
        ("model", "unsafe_model_identity"),
        ("path", "baseline_source_set_mismatch"),
    ]:
        protocol = deepcopy(PROTOCOL)
        if field == "contract":
            protocol["baseline"]["contracts_version_sha256"] = "0" * 64
        elif field == "source":
            protocol["baseline"]["graph_sources"][
                "agent/raphael_agent/model_gateway.py"
            ] = ("0" * 64)
        elif field == "path":
            protocol["baseline"]["graph_sources"]["../outside"] = "0" * 64
        else:
            protocol["baseline"]["models"]["../outside"] = next(
                iter(protocol["baseline"]["models"].values())
            )
        with pytest.raises(ReadinessError, match=reason):
            verify_baseline(ROOT, protocol)


@pytest.mark.parametrize("case_id", ["B01", "B02", "B03"])
def test_locked_source_fetcher_and_zip_integrity_use_original_metadata(
    tmp_path: Path, case_id: str
) -> None:
    import hashlib
    import zlib

    import httpx
    from scripts.fetch_readiness_evidence import fetch_item

    content = (
        ROOT / "agent/tests/fixtures/readiness_commands" / (case_id + ".sh")
    ).read_bytes()
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(content) + compressor.flush()
    item = {
        "path": case_id + ".sh",
        "url": "https://drive.usercontent.google.com/download?id=unit-control",
        "member": "original.sh",
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "crc32": f"{zlib.crc32(content):08x}",
        "compressed_start": 10,
        "compressed_bytes": len(compressed),
        "archive_bytes": len(compressed) + 10,
    }

    def serve(request: httpx.Request) -> httpx.Response:
        assert request.headers["Range"] == f"bytes=10-{len(compressed)+9}"
        return httpx.Response(
            206,
            headers={
                "content-range": f"bytes 10-{len(compressed)+9}/{len(compressed)+10}"
            },
            content=compressed,
        )

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        fetch_item(client, item, tmp_path)
        assert (tmp_path / item["path"]).read_bytes() == content
        fetch_item(client, item, tmp_path)  # Verified cache needs no second request.


@pytest.mark.parametrize("damage", ["hash", "size", "crc", "budget"])
def test_download_does_not_publish_unverified_bytes(
    tmp_path: Path, damage: str
) -> None:
    from scripts.fetch_readiness_evidence import write_verified

    content = (ROOT / "agent/tests/fixtures/readiness_commands/B01.sh").read_bytes()
    import hashlib

    item = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    if damage == "hash":
        item["sha256"] = "0" * 64
    elif damage == "size":
        item["bytes"] = len(content) - 1
    elif damage == "budget":
        item["bytes"] = 2_000_000_000
    else:
        item["crc32"] = "00000000"
    target = tmp_path / "download"
    before = set(tmp_path.iterdir())
    with pytest.raises(ReadinessError):
        write_verified([content], item, target)
    assert not target.exists()
    assert set(tmp_path.iterdir()) == before


def test_projection_exposes_instruction_not_scoring_answers(tmp_path: Path) -> None:
    from scripts.fetch_readiness_evidence import projected_bytes

    # Projection attack control, not a new incident fixture or positive model proof.
    source = tmp_path / "queries.csv"
    source.write_text(
        "task_index,instruction,scoring_points\ntask_control,original instruction,withheld answer\n"
    )
    item = {
        "derived_from": "queries.csv",
        "projection": "csv_instruction",
        "row_id": "task_control",
    }
    assert projected_bytes(item, tmp_path) == b"original instruction\n"
    item["row_id"] = "missing"
    with pytest.raises(ReadinessError, match="original_task_missing"):
        projected_bytes(item, tmp_path)
    item["projection"] = "scoring_points"
    with pytest.raises(ReadinessError, match="unknown_source_projection"):
        projected_bytes(item, tmp_path)
    item["derived_from"] = "../outside"
    with pytest.raises(ReadinessError, match="evidence_outside_cache"):
        projected_bytes(item, tmp_path)


@pytest.mark.parametrize("damage", ["host", "range", "status", "stream", "cache"])
def test_fetcher_refuses_redirects_untrusted_hosts_and_wrong_ranges(
    tmp_path: Path, damage: str
) -> None:
    import httpx
    from scripts.fetch_readiness_evidence import fetch_item

    item = {
        "path": "control",
        "url": "https://drive.usercontent.google.com/download?id=unit-control",
        "member": "original.sh",
        "bytes": 1,
        "sha256": "0" * 64,
        "compressed_start": 0,
        "compressed_bytes": 1,
        "archive_bytes": 1,
    }
    if damage == "host":
        item["url"] = "https://untrusted.invalid/source"
    elif damage == "range":
        item["compressed_start"] = 2
    elif damage == "cache":
        (tmp_path / "control").write_bytes(b"x")

    def serve(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200 if damage == "status" else 206,
            headers={"content-range": "bytes 0-0/1"},
            content=b"x",
        )

    with httpx.Client(transport=httpx.MockTransport(serve)) as client, pytest.raises(
        (ReadinessError, __import__("zlib").error)
    ):
        fetch_item(client, item, tmp_path)


def test_plain_download_and_safe_original_body_projection(tmp_path: Path) -> None:
    import hashlib

    import httpx
    from scripts.fetch_readiness_evidence import fetch_item

    content = (ROOT / "agent/tests/fixtures/readiness_commands/B03.sh").read_bytes()
    item = {
        "path": "original.sh",
        "url": "https://raw.githubusercontent.com/soarsmu/BugsInPy/locked/run_test.sh",
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    ) as client:
        fetch_item(client, item, tmp_path)
    raw = json.dumps({"body": content.decode(), "title": "withheld title"}).encode()
    (tmp_path / "issue.json").write_bytes(raw)
    derived = {
        **item,
        "path": "derived.sh",
        "projection": "github_report_body",
        "derived_from": "issue.json",
    }
    with httpx.Client() as client:
        fetch_item(client, derived, tmp_path)
    assert (tmp_path / "derived.sh").read_bytes() == content


def test_fetch_cli_verifies_real_cached_sources_and_bounds_errors(
    real_cases: tuple[dict[str, Any], Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import sys

    from scripts.fetch_readiness_evidence import main

    manifest, cache = real_cases
    source = cache / "manifest.json"
    source.write_text(json.dumps(manifest))
    monkeypatch.setattr(
        sys, "argv", ["fetch", "--manifest", str(source), "--cache-root", str(cache)]
    )
    main()
    assert "B03:verified" in capsys.readouterr().out
    item = manifest["cases"][0]["files"][0]
    (cache / item["path"]).write_bytes(b"tampered-control")
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "existing_cache_hash_mismatch" in capsys.readouterr().err


def test_commit_snapshot_projection_is_deterministic(tmp_path: Path) -> None:
    import hashlib

    import httpx
    from scripts.fetch_readiness_evidence import fetch_item

    source = json.dumps({"sha": SNAPSHOT["cases"][0]["commits"]["buggy"]})
    expected = (json.dumps(json.loads(source), sort_keys=True) + "\n").encode()
    item = {
        "url": "https://api.github.com/repos/tornadoweb/tornado/commits/locked",
        "projection": "canonical_commit_json",
        "path": "commit.json",
        "bytes": len(expected),
        "sha256": hashlib.sha256(expected).hexdigest(),
    }
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, content=source.encode())
        )
    ) as client:
        fetch_item(client, item, tmp_path)
    assert (tmp_path / "commit.json").read_bytes() == expected


@pytest.mark.parametrize("require_final", [False, True])
def test_preparation_cli_never_turns_pending_sources_into_final_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, require_final: bool
) -> None:
    import sys

    from scripts.prepare_model_readiness import main

    output = tmp_path / "preparation"
    argv = ["prepare", "--output", str(output)]
    if require_final:
        argv.append("--require-final-ready")
    monkeypatch.setattr(sys, "argv", argv)
    if require_final:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
    else:
        main()
    report = json.loads((output / "preparation.json").read_text())
    assert report["predictions_executed"] == 0
    assert not report["raw_evidence"]["verified"]
    assert "raw_evidence_not_verified" in report["final_freeze_blockers"]
    assert "protocol_owner_review_pending" in report["final_freeze_blockers"]
    assert report["paired_jobs"] == 24


def test_preparation_input_failure_does_not_expose_raw_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sys

    from scripts.prepare_model_readiness import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare",
            "--manifest",
            str(tmp_path / "sensitive-control"),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert capsys.readouterr().err == "preparation_input_invalid\n"


def test_baseline_cannot_omit_a_model_or_admit_untrusted_weights() -> None:
    from raphael_agent.readiness import verify_baseline

    protocol = deepcopy(PROTOCOL)
    protocol["baseline"]["models"].pop("candidate_ranker")
    with pytest.raises(ReadinessError, match="baseline_model_set_mismatch"):
        verify_baseline(ROOT, protocol)
    protocol = deepcopy(PROTOCOL)
    protocol["baseline"]["models"]["candidate_ranker"]["artifact_sha256"] = "0" * 64
    with pytest.raises(ReadinessError, match="baseline_untrusted_identity"):
        verify_baseline(ROOT, protocol)
