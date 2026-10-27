"""Paired development replays of original evidence; no final quality approval.

Predict seals outputs before score opens upstream fix metadata. Neither command
executes downloaded code, calls an external LLM, or runs a sandbox/publication.
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import platform
import re
import resource
import subprocess
import tarfile
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from raphael_agent.graph import initial_run_state, nodes
from raphael_agent.local_inference import artifacts
from raphael_agent.model_gateway import ModelGateway
from raphael_agent.readiness import (
    ReadinessError,
    canonical_digest,
    digest_file,
    freeze_blockers,
    validate_manifest,
    verify_baseline,
    verify_evidence,
)
from raphael_agent.readiness_metrics import ranking_metrics
from scripts.qualify_model_graph import OWNER, Catalog, configured

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "agent/fixtures/production_readiness"
REPRODUCTIONS = ROOT / "docs/evidence/issue-78/phase-1/reproductions.json"
SOURCE_PATHS = (
    "agent/scripts/evaluate_model_readiness.py",
    "agent/scripts/qualify_model_graph.py",
    "agent/raphael_agent/readiness_metrics.py",
)
FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+), in (\w+)')


def write_json(path: Path, value: Any) -> None:
    """Write finite JSON and refuse to silently replace a prior experiment."""
    with path.open("x") as target:
        target.write(
            json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )


def context() -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind the experiment to the unchanged Phase 1 protocol and production code."""
    manifest = json.loads((FIXTURES / "source-manifest.json").read_text())
    protocol = json.loads((FIXTURES / "protocol.json").read_text())
    validate_manifest(
        manifest, json.loads((FIXTURES / "source-manifest.schema.json").read_text())
    )
    verify_baseline(ROOT, protocol)
    return manifest, protocol


def input_file(case: dict[str, Any], cache: Path, suffix: str) -> Path:
    """Select exactly one declared input, never an oracle or raw report snapshot."""
    matches = [
        f for f in case["files"] if f["role"] == "input" and f["path"].endswith(suffix)
    ]
    if len(matches) != 1:
        raise ReadinessError("input_selection_ambiguous")
    return cache / str(matches[0]["path"])


def buggy_workspace(archive: Path, destination: Path) -> Path:
    """Materialize only trusted buggy source bytes, without links or execution."""
    destination.mkdir()
    with tarfile.open(archive) as source:
        members = source.getmembers()
        if any(not (m.isfile() or m.isdir()) for m in members):
            raise ReadinessError("source_archive_contains_links_or_special_files")
        source.extractall(destination, members=members, filter="data")
    roots = list(destination.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ReadinessError("source_archive_root_invalid")
    return roots[0]


def application_stack(log: str, workspace: Path) -> str:
    """Retain real application frame coordinates, with repository-relative paths.

    Do not expose fixed-test overlay bodies, assertions, test names or commands.
    Do not synthesize frames from pytest's abbreviated assertion locations.
    """
    frames = []
    for line in log.splitlines():
        match = FRAME.match(line)
        if not match or f"/{workspace.name}/" not in match[1]:
            continue
        relative = match[1].split(f"/{workspace.name}/", 1)[1]
        path = (workspace / relative).resolve()
        if (
            not path.is_relative_to(workspace.resolve())
            or not path.is_file()
            or any(p in {"test", "tests"} for p in Path(relative).parts)
        ):
            continue
        frames.append(f'  File "{relative}", line {match[2]}, in {match[3]}')
    return "\n".join(frames)


def telemetry_contract(path: Path) -> dict[str, Any]:
    """Inspect a fixed prefix of original CSV without inventing missing meanings."""
    with path.open(newline="") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames or []
        count = 0
        for _ in range(1000):
            if next(reader, None) is None:
                break
            count += 1
    required = {"service_name", "operation", "latency_ms"}
    missing = sorted(required - set(columns))
    return {
        "columns": columns,
        "prefix_rows_inspected": count,
        "missing_native_contract_fields": missing,
        "compatible": not missing,
        "verified_healthy_baseline": False,
        "reason": "native_schema_requires_reviewed_adapter_and_owned_healthy_baseline",
        "prediction_executed": False,
    }


def seed(case: dict[str, Any]) -> dict[str, Any]:
    """Use public identity plus labelled test ownership; no answer hints/signatures."""
    repository = case["repository"] or "public-source/telemetry"
    owner, name = repository.split("/", 1)
    return dict(
        initial_run_state(
            {
                **OWNER,
                "run_id": f"readiness-{case['id']}",
                "trigger": {"kind": "github_issue"},
                "repository": {"owner": owner, "name": name},
                "target_environment": "original-source-development-replay",
                "commit_sha": case["commits"].get("buggy") or "0" * 40,
            },
            sandbox_mode="recorded_stub",
        )
    )


def outcome(state: dict[str, Any], capability: str) -> dict[str, Any]:
    """Persist bounded decisions and provenance, excluding source report text."""
    diagnosis = state.get("diagnosis") or {}
    result = (state.get("model_results") or {}).get(capability)
    return {
        "model_result": result,
        "classification": diagnosis.get("classification"),
        "selected_hypothesis_id": diagnosis.get("selected_hypothesis_id"),
        "diagnosis_confidence": diagnosis.get("confidence"),
        "graph_status": state.get("status"),
        "terminal_reason": state.get("terminal_reason"),
        "fault_candidates": state.get("fault_candidates") or [],
        "patch_proposals": len(state.get("candidate_patches") or []),
        "reproduced_in_ignis": False,
        "validated_repairs": 0,
    }


def run_case(
    case: dict[str, Any], cache: Path, temporary: Path
) -> list[dict[str, Any]]:
    """Run two arms at production call sites on immutable, oracle-free inputs."""
    base = seed(case)
    inputs = [
        {k: f[k] for k in ("path", "sha256", "bytes")}
        for f in case["files"]
        if f["role"] == "input"
    ]
    reproduction: dict[str, Any] | None = None
    if case["id"].startswith("B"):
        # Original log hashes were sealed in Phase 1 before model evaluation.
        reproduction = next(
            r
            for r in json.loads(REPRODUCTIONS.read_text())
            if r["case_id"] == case["id"]
        )
        log_path = cache / case["id"] / "buggy-reproduction.log"
        expected = next(r for r in reproduction["runs"] if r["mode"] == "buggy")
        if (
            digest_file(log_path) != expected["log_sha256"]
            or expected["exit_code"] != 1
        ):
            raise ReadinessError("reproduction_log_not_phase1_original")
        workspace = buggy_workspace(
            input_file(case, cache, "buggy-source.tar.gz"), temporary / case["id"]
        )
        stack = application_stack(log_path.read_text(), workspace)
        base["workspace_path"] = str(workspace)
        base["runtime_observation"] = {"stack_trace": stack}
        inputs.append(
            {
                "path": f"{case['id']}/buggy-reproduction.log",
                "sha256": expected["log_sha256"],
                "bytes": log_path.stat().st_size,
            }
        )
    elif case["id"].startswith("K"):
        base["issue_body"] = input_file(case, cache, "report.txt").read_text()
    else:
        check = telemetry_contract(input_file(case, cache, "trace_span.csv"))
        return [
            {
                "case_id": case["id"],
                "capability": "trace_anomaly",
                "model_enabled": enabled,
                "split": case["split"],
                "incident_group": case["incident_group"],
                "input_sha256": canonical_digest(inputs),
                "inputs": inputs,
                "elapsed_ms": 0.0,
                "execution_layer": "native_telemetry_compatibility_check",
                "output": check,
            }
            for enabled in (False, True)
        ]
    records = []
    for capability in case["capabilities"]:
        # Generate candidates ONCE with all models disabled. Freeze this list;
        # ranking ablation cannot use retrieval/model diagnosis to change features.
        os.environ["RAPHAEL_MODEL_ENABLED"] = "0"
        common = copy.deepcopy(base)
        common.update(nodes.node_evidence(common))
        if capability == "candidate_ranker":
            common.update(nodes.node_localize(common))
        frozen = common.get("fault_candidates") or []
        model_input = ModelGateway._failure_record(common)
        for enabled in (False, True):
            os.environ["RAPHAEL_MODEL_ENABLED"] = "1" if enabled else "0"
            state = copy.deepcopy(common)
            start = perf_counter()
            if capability == "failure_classifier":
                state.update(nodes.node_diagnose(state))
            elif capability == "incident_similarity":
                state.update(nodes.node_localize(state))
            elif capability == "candidate_ranker":
                state.setdefault("model_results", {}).pop(capability, None)
                prediction = ModelGateway().rank_candidates(
                    state, copy.deepcopy(frozen), []
                )
                if prediction:
                    state["fault_candidates"] = prediction["candidates"]
                    state.setdefault("model_results", {})[capability] = prediction[
                        "model"
                    ]

                else:
                    state["model_results"][capability] = {
                        "available": False,
                        "reason": (
                            "no_graph_candidates"
                            if not frozen
                            else "disabled_by_environment"
                        ),
                    }

                # Every identity field except score/order must survive unchanged.
                def identity(rows: list[dict[str, Any]]) -> list[str]:
                    return sorted(
                        canonical_digest({k: v for k, v in row.items() if k != "score"})
                        for row in rows
                    )

                if identity(frozen) != identity(state.get("fault_candidates") or []):
                    raise ReadinessError("candidate_identity_mutated")
            else:
                state.update(nodes.node_diagnose(state))
                # No original report has a verified Ignis reproduction. Exercise
                # the real precondition, never assert a fabricated reproduction.
                state.update(nodes.node_patch(state))
            records.append(
                {
                    "case_id": case["id"],
                    "capability": capability,
                    "model_enabled": enabled,
                    "split": case["split"],
                    "incident_group": case["incident_group"],
                    "inputs": inputs,
                    "input_sha256": canonical_digest(inputs),
                    "adapter_input_sha256": canonical_digest(model_input),
                    "adapter_evidence_characters": len(model_input["evidence_text"]),
                    "collected_excerpt_characters": sum(
                        len(e.get("content_excerpt") or "")
                        for e in common.get("evidence") or []
                    ),
                    "candidate_input_sha256": canonical_digest(frozen),
                    "application_frame_count": len(
                        (base.get("runtime_observation") or {})
                        .get("stack_trace", "")
                        .splitlines()
                    ),
                    "execution_layer": (
                        "graph_generated_candidates_frozen_gateway_ablation"
                        if capability == "candidate_ranker"
                        else "production_graph_nodes"
                    ),
                    "elapsed_ms": round((perf_counter() - start) * 1000, 4),
                    "output": outcome(state, capability),
                }
            )
    return records


def predict(cache: Path, output: Path) -> dict[str, Any]:
    """Seal development predictions before loading evaluator-only answers."""
    manifest, protocol = context()
    evidence = verify_evidence(manifest, cache)
    if any(c["split"] == "final_test" for c in manifest["cases"]):
        raise ReadinessError("development_runner_rejects_final_test")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ReadinessError("output_directory_not_empty")
    rows = []
    cold = {}
    with (
        tempfile.TemporaryDirectory(prefix="readiness-") as directory,
        Catalog() as catalog,
        configured(catalog, ROOT / "models", Path(directory) / "data"),
    ):
        for name in artifacts.TRUSTED_ARTIFACTS:
            artifacts._load_bundle.cache_clear()
            start = perf_counter()
            artifacts.load_bundle(ROOT / "models", name)
            cold[name] = round((perf_counter() - start) * 1000, 4)
        for case in manifest["cases"]:
            if case["split"] != "excluded":
                rows.extend(run_case(case, cache, Path(directory)))
    predictions = output / "predictions.jsonl"
    with predictions.open("x") as target:
        target.write(
            "".join(
                json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows
            )
        )
    seal = {
        "schema_version": 1,
        "status": "development_predictions_sealed_not_scored",
        "manifest_sha256": canonical_digest(manifest),
        "protocol_sha256": canonical_digest(protocol),
        "reproductions_sha256": digest_file(REPRODUCTIONS),
        "predictions_sha256": digest_file(predictions),
        "row_count": len(rows),
        "raw_evidence": evidence,
        "production_baseline": protocol["baseline"],
        "verifier_sources": {p: digest_file(ROOT / p) for p in SOURCE_PATHS},
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "cpu_model": next(
            (
                s.partition(":")[2].strip()
                for s in Path("/proc/cpuinfo").read_text().splitlines()
                if s.startswith("model name")
            ),
            "unknown",
        ),
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "libraries": artifacts.RUNTIME_VERSIONS,
        "runtime_sources": {
            p.relative_to(ROOT).as_posix(): digest_file(p)
            for p in sorted((ROOT / "agent/raphael_agent").rglob("*.py"))
        },
        "cold_artifact_load_ms": cold,
        "peak_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "policy": protocol["policy"],
        "final_freeze_blockers": freeze_blockers(manifest, protocol),
        "scope": "fixture-public-index; loopback empty catalog; no customer tenancy or live Supabase",
        "ablation": "one capability call site at a time; upstream model effects held at deterministic baseline; not a complete-graph benefit experiment",
    }
    write_json(output / "seal.json", seal)
    return seal


def validate_predictions(
    directory: Path,
    manifest: dict[str, Any],
    protocol: dict[str, Any],
    *,
    require_current_sources: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reject altered evidence and unpaired contexts.

    Historical audits may validate the sealed dataset without certifying the
    current runtime. New scoring always requires current source hashes.
    """
    seal = json.loads((directory / "seal.json").read_text())
    if (
        seal["predictions_sha256"] != digest_file(directory / "predictions.jsonl")
        or seal["manifest_sha256"] != canonical_digest(manifest)
        or seal["protocol_sha256"] != canonical_digest(protocol)
        or seal["production_baseline"] != protocol["baseline"]
        or seal["policy"] != protocol["policy"]
        or (
            require_current_sources
            and (
                seal["runtime_sources"]
                != {
                    p.relative_to(ROOT).as_posix(): digest_file(p)
                    for p in sorted((ROOT / "agent/raphael_agent").rglob("*.py"))
                }
                or seal["verifier_sources"]
                != {p: digest_file(ROOT / p) for p in SOURCE_PATHS}
            )
        )
        or seal["reproductions_sha256"] != digest_file(REPRODUCTIONS)
    ):
        raise ReadinessError("prediction_seal_mismatch")
    rows = [
        json.loads(line)
        for line in (directory / "predictions.jsonl").read_text().splitlines()
    ]
    canonical_digest(rows)  # Reject non-finite result JSON even if rehashed.
    expected = {
        (c["id"], name, enabled)
        for c in manifest["cases"]
        if c["split"] != "excluded"
        for name in c["capabilities"]
        for enabled in (False, True)
    }
    actual = [(r["case_id"], r["capability"], r["model_enabled"]) for r in rows]
    if (
        len(rows) != len(expected)
        or set(actual) != expected
        or seal["row_count"] != len(rows)
    ):
        raise ReadinessError("prediction_arms_missing_or_duplicated")
    cases = {c["id"]: c for c in manifest["cases"]}
    for row in rows:
        if type(row["model_enabled"]) is not bool:
            raise ReadinessError("prediction_mode_invalid")
        case = cases[row["case_id"]]
        inputs = [
            {k: f[k] for k in ("path", "sha256", "bytes")}
            for f in case["files"]
            if f["role"] == "input"
        ]
        if case["id"].startswith("B"):
            repro = next(
                r
                for r in json.loads(REPRODUCTIONS.read_text())
                if r["case_id"] == case["id"]
            )
            log = next(r for r in repro["runs"] if r["mode"] == "buggy")
            # The original log is a declared Phase 1 derivation, not a model label.
            supplied = row["inputs"][-1]
            if (
                supplied["path"] != f"{case['id']}/buggy-reproduction.log"
                or supplied["sha256"] != log["log_sha256"]
            ):
                raise ReadinessError("prediction_log_identity_mismatch")
            inputs.append(supplied)
        if (
            row["inputs"] != inputs
            or row["input_sha256"] != canonical_digest(inputs)
            or row["split"] != case["split"]
            or row["incident_group"] != case["incident_group"]
        ):
            raise ReadinessError("prediction_input_context_mismatch")
    for row in (r for r in rows if r["model_enabled"] is False):
        other = next(
            r
            for r in rows
            if r["case_id"] == row["case_id"]
            and r["capability"] == row["capability"]
            and r["model_enabled"] != row["model_enabled"]
        )
        for key in ("input_sha256", "adapter_input_sha256", "candidate_input_sha256"):
            if row.get(key) != other.get(key):
                raise ReadinessError("prediction_paired_context_mismatch")
    return rows, seal


def score(directory: Path, cache: Path, output: Path) -> dict[str, Any]:
    """Score only available upstream file oracles after checking sealed predictions."""
    manifest, protocol = context()
    rows, seal = validate_predictions(directory, manifest, protocol)
    verify_evidence(manifest, cache)
    ranking = []
    for case in manifest["cases"]:
        if "candidate_ranker" not in case["capabilities"]:
            continue
        item = next(
            f
            for f in case["files"]
            if f["path"].endswith("fixed-commit.json") and f["role"] == "oracle"
        )
        commit = json.loads((cache / item["path"]).read_text())
        relevant = [
            f["filename"]
            for f in commit["files"]
            if not any(p in {"test", "tests"} for p in Path(f["filename"]).parts)
            and f["filename"].endswith(".py")
        ]
        if not relevant:
            raise ReadinessError("upstream_fix_file_oracle_empty")
        arms = {
            str(r["model_enabled"]): r["output"]["fault_candidates"]
            for r in rows
            if r["case_id"] == case["id"] and r["capability"] == "candidate_ranker"
        }
        ranking.append(
            {
                "case_id": case["id"],
                "incident_group": case["incident_group"],
                "relevant_files": relevant,
                "oracle_sha256": item["sha256"],
                "baseline": [c["path"] for c in arms["False"]],
                "model": [c["path"] for c in arms["True"]],
            }
        )
    matrix = {}
    for capability in protocol["gates"]:
        calls = [
            r for r in rows if r["capability"] == capability and r["model_enabled"]
        ]
        results = [r["output"].get("model_result") or {} for r in calls]
        matrix[capability] = {
            "acceptance": (
                "blocked"
                if capability in {"trace_anomaly", "patch_selector"}
                else "insufficient_evidence"
            ),
            "decision": "keep_deferred",
            "cases_checked": len(calls),
            "learned_executions": sum(
                r.get("learned_execution") is True for r in results
            ),
            "rule_overrides": sum(r.get("rule_based") is True for r in results),
            "abstentions": sum(
                r.get("abstained") is True or r.get("execution_source") == "abstention"
                for r in results
            ),
            "final_quality_metrics": None,
            "policy_stops": sum(
                (r["output"].get("classification") or {}).get("category") == "blocked"
                for r in calls
            ),
            "queries_returning_matches": (
                sum(
                    bool((r["output"].get("model_result") or {}).get("results"))
                    for r in calls
                )
                if capability == "incident_similarity"
                else None
            ),
            "gates": protocol["gates"][capability],
            "sample_floor": protocol["sample_floors"][capability],
        }
    matrix["candidate_ranker"]["development_file_oracle_metrics"] = ranking_metrics(
        ranking
    )
    classification_pairs = [
        (
            r,
            next(
                other
                for other in rows
                if other["case_id"] == r["case_id"]
                and other["capability"] == r["capability"]
                and other["model_enabled"] is False
            ),
        )
        for r in rows
        if r["capability"] == "failure_classifier" and r["model_enabled"]
    ]
    matrix["failure_classifier"]["paired_classification_changes"] = sum(
        left["output"].get("classification") != right["output"].get("classification")
        for left, right in classification_pairs
    )
    matrix["incident_similarity"]["returned_match_count"] = sum(
        len((r["output"].get("model_result") or {}).get("results") or [])
        for r in rows
        if r["capability"] == "incident_similarity" and r["model_enabled"]
    )

    matrix["failure_classifier"][
        "missing"
    ] = "Independent cause/taxonomy labels, calibrated probabilities, final sample, complete-graph comparison."
    matrix["incident_similarity"][
        "missing"
    ] = "Independent relevance/no-match labels, three distinct pre-query histories; fixture partitions duplicate one public corpus."
    matrix["trace_anomaly"][
        "missing"
    ] = "Reviewed native telemetry adapter/units, owned healthy baseline, verified healthy exposure and event labels. No anomaly accuracy scored."
    matrix["patch_selector"][
        "missing"
    ] = "Original runnable supported Kubernetes repairs with verified Ignis reproduction; zero model-selected or validated repairs."
    summary = {
        "status": "development_evaluated_not_production_qualified",
        "prediction_seal_sha256": digest_file(directory / "seal.json"),
        "protocol_sha256": seal["protocol_sha256"],
        "final_freeze_blockers": seal["final_freeze_blockers"],
        "ranking_cases": ranking,
        "capabilities": matrix,
        "labels": "Maintainer changed Python source filenames are provisional development oracles; no independent human cause/relevance labels are invented.",
        "statistical_unit": "incident; repeated candidates/calls are not independent samples",
        "validated_raphael_repairs": 0,
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "summary.json", summary)
    lines = [
        "# Phase 2 development evaluation",
        "",
        "All five capabilities remain deferred. Final held-out approval and quality gates are pending.",
        "",
        "| Capability | Cases checked | Learned calls | Rule overrides | Decision |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, values in matrix.items():
        lines.append(
            f"| {name} | {values['cases_checked']} | {values['learned_executions']} | {values['rule_overrides']} | {values['acceptance']} |"
        )
    lines.extend(
        [
            "",
            "Ranking uses real graph-generated candidates and a maintainer-file development oracle. Other quality metrics remain unscored. See summary.json for exact gates, denominators and blockers.",
            "",
        ]
    )
    with (output / "evaluation-summary.md").open("x") as target:
        target.write("\n".join(lines))
    return summary


def main() -> None:
    """Run explicit prediction/scoring stages; never certify a final test set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("predict", "score"))
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.stage == "predict":
            result = predict(args.cache_root.resolve(), args.output.resolve())
        else:
            if args.predictions is None:
                parser.error("score requires --predictions")
            result = score(
                args.predictions.resolve(),
                args.cache_root.resolve(),
                args.output.resolve(),
            )
        print(json.dumps({"status": result["status"]}))
    except (
        ReadinessError,
        OSError,
        ValueError,
        KeyError,
        StopIteration,
        tarfile.TarError,
    ):
        parser.exit(1, "readiness_evaluation_input_invalid\n")


if __name__ == "__main__":
    main()
