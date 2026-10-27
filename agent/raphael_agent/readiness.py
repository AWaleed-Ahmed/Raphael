"""Offline provenance and paired-input checks; never train or score a model."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ReadinessError(ValueError):
    """A bounded validation failure without raw evidence or exception contents."""


def digest_file(path: Path) -> str:
    """Hash large original artifacts without loading them into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    """Identify structured evidence independent of JSON whitespace/key order."""
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (ValueError, TypeError) as exc:
        raise ReadinessError("context_not_finite_json") from exc
    return hashlib.sha256(encoded).hexdigest()


def validate_manifest(manifest: dict[str, Any], schema: dict[str, Any]) -> None:
    """Reject malformed sources and cross-split or oracle/input leakage."""
    if next(Draft202012Validator(schema).iter_errors(manifest), None):
        raise ReadinessError("manifest_schema_invalid")
    ids: set[str] = set()
    paths: dict[str, tuple[str, str]] = {}
    groups: dict[str, str] = {}
    input_hashes: dict[str, str] = {}
    oracle_hashes = {
        item["sha256"]
        for case in manifest["cases"]
        for item in case["files"]
        if item["role"] == "oracle"
    }
    for case in manifest["cases"]:
        if case["id"] in ids:
            raise ReadinessError("duplicate_case_id")
        ids.add(case["id"])
        previous = groups.setdefault(case["incident_group"], case["split"])
        if previous != case["split"]:
            raise ReadinessError("incident_crosses_splits")
        if not any(item["role"] == "input" for item in case["files"]):
            raise ReadinessError("input_missing")
        for item in case["files"]:
            path = Path(item["path"])
            if path.is_absolute() or ".." in path.parts or "\\" in item["path"]:
                raise ReadinessError("unsafe_evidence_path")
            identity = (item["sha256"], item["role"])
            if paths.setdefault(item["path"], identity) != identity:
                raise ReadinessError("conflicting_evidence_path")
            if item["role"] == "input":
                if item["sha256"] in oracle_hashes:
                    raise ReadinessError("oracle_in_model_input")
                previous = input_hashes.setdefault(item["sha256"], case["split"])
                if previous != case["split"]:
                    raise ReadinessError("duplicate_input_crosses_splits")
        if case["split"] == "final_test":
            if any(value != "clear" for value in case["overlap"].values()):
                raise ReadinessError("final_test_overlap_unresolved")
            reviews = case["reviews"]
            reviewers = {
                r["reviewer_id"]
                for r in reviews
                if r["kind"] == "human" and r["approved"]
            }
            label_hash = case["label_sha256"]
            if not label_hash or any(
                r["label_sha256"] != label_hash for r in reviews if r["approved"]
            ):
                raise ReadinessError("reviewed_labels_disagree")
            if len(reviewers) < 2 or case["label_status"] != "adjudicated":
                raise ReadinessError("independent_reviews_missing")
            if case["terms_status"] != "approved" or case["input_review"] != "approved":
                raise ReadinessError("final_test_evidence_review_missing")


def verify_evidence(manifest: dict[str, Any], cache_root: Path) -> dict[str, Any]:
    """Verify exact cached originals and reject evidence outside the cache."""
    root = cache_root.resolve(strict=True)
    verified: dict[str, str] = {}
    total = 0
    for case in manifest["cases"]:
        for item in case["files"]:
            path = (root / item["path"]).resolve()
            if not path.is_relative_to(root):
                raise ReadinessError("evidence_outside_cache")
            if item["path"] in verified:
                continue
            if not path.is_file():
                raise ReadinessError("evidence_missing")
            if (
                path.stat().st_size != item["bytes"]
                or digest_file(path) != item["sha256"]
            ):
                raise ReadinessError("evidence_hash_mismatch")
            verified[item["path"]] = item["sha256"]
            total += item["bytes"]
    return {"files": len(verified), "bytes": total, "verified": True}


def paired_jobs(
    manifest: dict[str, Any], protocol: dict[str, Any]
) -> list[dict[str, Any]]:
    """Seal identical inputs for two future arms, without executing predictions."""
    if (
        set(protocol["policy"]) != {"learning", "external_llm", "publication"}
        or protocol["policy"]["learning"] is not False
        or protocol["policy"]["external_llm"] is not False
        or protocol["policy"]["publication"] != "dry_run"
    ):
        raise ReadinessError("unsafe_evaluation_policy")
    jobs: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        if case["split"] == "excluded":
            continue
        # Only explicit input-role refs enter the predictor bundle. Environment,
        # raw report snapshots, labels, fixed code and fix diffs stay outside.
        inputs = sorted(
            (
                {k: item[k] for k in ("path", "sha256", "bytes")}
                for item in case["files"]
                if item["role"] == "input"
            ),
            key=lambda item: item["path"],
        )
        common = {
            "case_id": case["id"],
            "incident_group": case["incident_group"],
            "split": case["split"],
            "inputs": inputs,
            "input_sha256": canonical_digest(inputs),
            "protocol_sha256": canonical_digest(protocol),
            "baseline": protocol["baseline"],
            "policy": protocol["policy"],
            "execution_status": "prepared_not_executed",
        }
        jobs.extend({**common, "model_enabled": enabled} for enabled in (False, True))
    return jobs


def validate_pair(
    left: dict[str, Any], right: dict[str, Any], protocol: dict[str, Any]
) -> None:
    """Refuse paired comparisons with different source, policy or revisions."""
    if (
        type(left.get("model_enabled")) is not bool
        or type(right.get("model_enabled")) is not bool
    ):
        raise ReadinessError("invalid_pair_mode")
    if left["model_enabled"] == right["model_enabled"]:
        raise ReadinessError("pair_modes_not_distinct")
    required = {
        "case_id",
        "incident_group",
        "split",
        "inputs",
        "input_sha256",
        "protocol_sha256",
        "baseline",
        "policy",
        "execution_status",
    }
    if set(left) != required | {"model_enabled"} or set(right) != set(left):
        raise ReadinessError("pair_shape_invalid")
    if {k: v for k, v in left.items() if k != "model_enabled"} != {
        k: v for k, v in right.items() if k != "model_enabled"
    }:
        raise ReadinessError("paired_context_mismatch")
    if (
        left["protocol_sha256"] != canonical_digest(protocol)
        or left["baseline"] != protocol["baseline"]
        or left["policy"] != protocol["policy"]
    ):
        raise ReadinessError("pair_not_bound_to_protocol")
    if left["input_sha256"] != canonical_digest(left["inputs"]):
        raise ReadinessError("paired_input_digest_mismatch")


def freeze_blockers(manifest: dict[str, Any], protocol: dict[str, Any]) -> list[str]:
    """Keep engineering preparation separate from an approved final dataset."""
    blockers = []
    approval = protocol["approval"]
    if (
        approval["status"] != "approved"
        or not approval["reviewer_id"]
        or not approval["approved_at"]
    ):
        blockers.append("protocol_owner_review_pending")
    if not any(c["split"] == "final_test" for c in manifest["cases"]):
        blockers.append("independent_final_test_not_frozen")
    final_cases = [c for c in manifest["cases"] if c["split"] == "final_test"]
    for capability, floor in protocol["sample_floors"].items():
        required = next(
            floor[k]
            for k in (
                "incidents",
                "queries",
                "fault_episodes",
                "eligible_historical_attempts",
            )
            if k in floor
        )
        eligible = [c for c in final_cases if capability in c["capabilities"]]
        count = len({c["incident_group"] for c in eligible})
        if count < required:
            blockers.append(capability + ":final_sample_floor_unmet")
        for dimension in ("projects", "repositories", "systems"):
            if dimension in floor:
                key = "system" if dimension == "systems" else "repository"
                if len({c[key] for c in eligible if c[key]}) < floor[dimension]:
                    blockers.append(capability + ":source_diversity_floor_unmet")
        if (
            "per_claimed_class" in floor
            or "histories" in floor
            or "healthy_service_hours" in floor
        ):
            # Detailed class/history/exposure labels require adjudicated oracle
            # data, which this first source snapshot does not yet contain.
            blockers.append(capability + ":detailed_label_coverage_not_frozen")
    for case in manifest["cases"]:
        if case["split"] == "excluded":
            continue
        if case["label_status"] != "adjudicated":
            blockers.append(case["id"] + ":independent_label_review_pending")
        if case["terms_status"] != "approved":
            blockers.append(case["id"] + ":data_terms_pending")
        if case["input_review"] != "approved":
            blockers.append(case["id"] + ":answer_leakage_review_pending")
    return blockers


def audit_training(root: Path, training_root: Path) -> dict[str, Any]:
    """Check manifest-linked data and internal group splits without fitting."""
    from raphael_agent.local_inference.artifacts import TRUSTED_ARTIFACTS

    models = {}
    for name, (manifest_hash, artifact_hash, size) in TRUSTED_ARTIFACTS.items():
        folder = root / "models" / name
        manifest = json.loads((folder / "manifest.json").read_text())
        trusted = (
            digest_file(folder / "manifest.json") == manifest_hash
            and digest_file(folder / "model.joblib") == artifact_hash
            and (folder / "model.joblib").stat().st_size == size
        )
        files = []
        groups: dict[str, set[str]] = {}
        for item in manifest["dataset_files"]:
            original = Path(item["path"])
            # Never read arbitrary absolute manifest paths: only the declared
            # local training tree or the approved repository-relative corpus.
            if "raphael/data/" in original.as_posix():
                relative = original.as_posix().split("raphael/data/", 1)[1]
                path = (training_root / relative).resolve()
                if not path.is_relative_to(training_root.resolve()):
                    raise ReadinessError("training_path_outside_root")
            else:
                path = (root / original).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ReadinessError("training_path_outside_root")
            entry = {
                "path": item["path"],
                "expected_sha256": item["sha256"],
                "available": path.is_file(),
            }
            if path.is_file():
                rows = [
                    json.loads(line) for line in path.read_text().splitlines() if line
                ]
                entry.update(sha256=digest_file(path), records=len(rows))
                entry["hash_matches"] = entry["sha256"] == item["sha256"]
                groups[path.stem] = {
                    row["incident_id"] if name == "candidate_ranker" else family
                    for row in rows
                    for family in (
                        re.findall(r"fam_[a-z]+_\d+", row.get("fingerprint", ""))
                        if name == "failure_classifier"
                        else [""]
                    )
                }
            files.append(entry)
        intersections = {
            a + "/" + b: len(groups[a] & groups[b])
            for a, b in [
                ("train", "validation"),
                ("train", "test"),
                ("validation", "test"),
            ]
            if a in groups and b in groups
        }
        index_verification: dict[str, Any] | None = None
        if name == "incident_similarity":
            verification_path = (
                root / "agent/tests/fixtures/incident_isolation/public-sources.json"
            )
            verification = json.loads(verification_path.read_text())
            index_verification = {
                "source_verification_matches": digest_file(verification_path)
                == manifest["source_verification_sha256"],
                "verified_public_sources": sum(
                    bool(item["verified"]) for item in verification["sources"]
                ),
                "ownership": manifest["ownership"],
            }
        models[name] = {
            "trusted_artifact_matches": trusted,
            "index_verification": index_verification,
            "dataset_files": files,
            "split_group_intersections": intersections,
            "generation_lineage": "not_independently_attested",
            "scope": "declared_corpus_hash_and_exact_group_checks_only",
        }
    return models


def audit_source_overlap(
    root: Path, training_root: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    """Find exact original identifiers in declared training and prior fixtures."""
    corpus = []
    for path in sorted(training_root.rglob("*.jsonl")):
        if "cleaned" not in path.parts:
            corpus.append((str(path.relative_to(training_root)), path.read_text()))
    prior = "\n".join(
        p.read_text()
        for p in (root / "agent/tests/fixtures/local_inference").glob("*.jsonl")
    )
    index_rows = [
        json.loads(line)
        for line in (
            root / "agent/tests/fixtures/local_inference/incident_similarity.jsonl"
        )
        .read_text()
        .splitlines()
    ]
    verification = json.loads(
        (
            root / "agent/tests/fixtures/incident_isolation/public-sources.json"
        ).read_text()
    )
    available = {item["url"] for item in verification["sources"] if item["verified"]}
    index_urls = {
        row["source"]["url"] for row in index_rows if row["source"]["url"] in available
    }
    prior_results = [
        (str(path.relative_to(training_root.parent)), path.read_text())
        for path in sorted(
            (training_root.parent / "evaluation/results").rglob("*.jsonl")
        )
    ]
    result = {}
    for case in manifest["cases"]:
        identifiers = [case["source_url"], *case["commits"].values()]
        hits = [
            name for name, text in corpus if any(token in text for token in identifiers)
        ]
        result[case["id"]] = {
            "training_exact_identifier_files": hits,
            "prior_fixture_url_match": case["source_url"] in prior,
            "index_source_url_match": case["source_url"] in index_urls,
            "prior_local_result_files": [
                name
                for name, text in prior_results
                if any(token in text for token in identifiers)
            ],
            "semantic_or_generation_independence": "not_established_by_exact_scan",
        }
    return {
        "scanned_files": len(corpus),
        "prior_local_result_files_scanned": len(prior_results),
        "prior_local_result_hashes": {
            name: hashlib.sha256(text.encode()).hexdigest()
            for name, text in prior_results
        },
        "cases": result,
    }


def verify_baseline(root: Path, protocol: dict[str, Any]) -> None:
    """Reject source/artifact drift from the preregistered baseline identity."""
    baseline = protocol["baseline"]
    if digest_file(root / "CONTRACTS_VERSION") != baseline["contracts_version_sha256"]:
        raise ReadinessError("baseline_contract_drift")
    from raphael_agent.local_inference.artifacts import TRUSTED_ARTIFACTS

    if not all(re.fullmatch(r"[a-z_]+", name) for name in baseline["models"]):
        raise ReadinessError("unsafe_model_identity")
    if set(baseline["models"]) != set(TRUSTED_ARTIFACTS):
        raise ReadinessError("baseline_model_set_mismatch")
    files = dict(baseline["graph_sources"])
    if set(files) != {
        "agent/raphael_agent/graph/nodes.py",
        "agent/raphael_agent/model_gateway.py",
        "agent/raphael_agent/model_outputs.py",
        "agent/raphael_agent/incident_scope.py",
    }:
        raise ReadinessError("baseline_source_set_mismatch")
    for name, hashes in baseline["models"].items():
        if (hashes["manifest_sha256"], hashes["artifact_sha256"]) != TRUSTED_ARTIFACTS[
            name
        ][:2]:
            raise ReadinessError("baseline_untrusted_identity")
        files[f"models/{name}/manifest.json"] = hashes["manifest_sha256"]
        files[f"models/{name}/model.joblib"] = hashes["artifact_sha256"]
    for relative, expected in files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ReadinessError("baseline_file_invalid")
        if digest_file(path) != expected:
            raise ReadinessError("baseline_source_or_artifact_drift")
