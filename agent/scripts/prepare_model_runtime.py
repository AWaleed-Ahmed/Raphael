"""Prepare private source-linked runtime jobs; do not redistribute raw incident text."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
from typing import Any

from raphael_agent.evidence.issue import collect_issue_evidence
from raphael_agent.readiness import (
    ReadinessError,
    canonical_digest,
    digest_file,
    verify_evidence,
)
from scripts.evaluate_model_readiness import (
    ROOT,
    context,
    input_file,
    seed,
    validate_predictions,
)


def prepare(cache: Path, output: Path) -> dict[str, Any]:
    """Preserve original inputs and clearly distinguish prior projection controls."""
    manifest, protocol = context()
    verify_evidence(manifest, cache)
    rows, _ = validate_predictions(
        ROOT / "docs/evidence/issue-78/phase-2",
        manifest,
        protocol,
        require_current_sources=False,
    )
    jobs: list[dict[str, Any]] = []
    excluded = []
    safety = []
    for case in manifest["cases"]:
        if case["id"].startswith("K"):
            state = seed(case)
            state["issue_body"] = input_file(case, cache, "report.txt").read_text()
            state["evidence"] = collect_issue_evidence(state)
            baseline = next(
                r
                for r in rows
                if r["case_id"] == case["id"]
                and r["capability"] == "failure_classifier"
                and not r["model_enabled"]
            )
            state["diagnosis"] = {
                "classification": baseline["output"]["classification"]
            }
            for capability in (
                "failure_classifier",
                "incident_similarity",
                "patch_selector",
            ):
                jobs.append(
                    {
                        "id": case["id"] + ":" + capability,
                        "capability": capability,
                        "source_ids": [case["id"]],
                        "tier": "original_report_gateway_diagnostic",
                        "input_sha256": canonical_digest(state),
                        "state": state,
                    }
                )
            if case["id"] in {"K01", "K03", "K04"}:
                safety.append({"id": case["id"], "state": copy.deepcopy(state)})
        elif case["id"].startswith("B"):
            row = next(
                r for r in rows if r["case_id"] == case["id"] and not r["model_enabled"]
            )
            if not row["output"]["fault_candidates"]:
                excluded.append(
                    {
                        "id": case["id"],
                        "reason": "no_graph_candidates; no ranking call counted",
                    }
                )
            else:
                jobs.append(
                    {
                        "id": case["id"] + ":candidate_ranker",
                        "capability": "candidate_ranker",
                        "source_ids": [case["id"]],
                        "tier": "phase2_graph_candidates",
                        "input_sha256": row["candidate_input_sha256"],
                        "state": seed(case),
                        "candidates": row["output"]["fault_candidates"],
                    }
                )
        else:
            excluded.append(
                {
                    "id": case["id"],
                    "reason": "native_OpenRCA_contract_and_verified_owned_baseline_unavailable",
                }
            )
    fixture = ROOT / "agent/tests/fixtures/local_inference"
    for i, line in enumerate(
        (fixture / "trace_anomaly.jsonl").read_text().splitlines()[:3]
    ):
        case = json.loads(line)
        payload = case["input"]
        jobs.append(
            {
                "id": "R65-trace-" + str(i),
                "capability": "trace_anomaly",
                "source_ids": [case["source"]["url"]],
                "tier": "prior_source_linked_projection_operational_regression_only",
                "input_sha256": canonical_digest(payload),
                "state": {
                    "tenant_id": "fixture-tenant-a",
                    "company_id": "fixture-company-a",
                    "client_id": "fixture-client-a1",
                    "runtime_observation": payload,
                },
            }
        )
    patch = json.loads((fixture / "patch_selector.jsonl").read_text().splitlines()[-1])
    jobs.append(
        {
            "id": "R65-patch-learned-refusal",
            "capability": "patch_selector",
            "source_ids": [patch["source"]["url"]],
            "tier": "prior_source_linked_gateway_projection_advisory_only",
            "input_sha256": canonical_digest(patch["input"]),
            "state": {
                "tenant_id": "fixture-tenant-a",
                "company_id": "fixture-company-a",
                "client_id": "fixture-client-a1",
                "evidence": [{"summary": patch["input"]["evidence_text"]}],
                "diagnosis": {
                    "classification": {"failure_class": patch["input"]["failure_class"]}
                },
                "fault_candidates": [
                    {
                        "candidate_type": patch["input"]["candidate_type"],
                        "symbol": patch["input"]["manifest_field"],
                        "path": "",
                    }
                ],
            },
        }
    )
    own = {
        "tenant_id": "fixture-tenant-a",
        "company_id": "fixture-company-a",
        "client_id": "fixture-client-a1",
    }
    faults = [next(c for c in safety if c["id"] == "K01")]
    log = cache / "B02/buggy-reproduction.log"
    original = next(
        r
        for r in json.loads(
            (ROOT / "docs/evidence/issue-78/phase-1/reproductions.json").read_text()
        )
        if r["case_id"] == "B02"
    )
    if digest_file(log) != next(
        r["log_sha256"] for r in original["runs"] if r["mode"] == "buggy"
    ):
        raise ReadinessError("reproduction_log_hash_mismatch")
    faults.append(
        {
            "id": "B02",
            "state": {
                **own,
                "evidence": [
                    {
                        "summary": "Original recorded pytest failure",
                        "content_excerpt": log.read_text(),
                    }
                ],
            },
            "source_sha256": digest_file(log),
        }
    )
    market = next(c for c in manifest["cases"] if c["id"] == "O03")
    with input_file(market, cache, "trace_span.csv").open() as source:
        native = next(csv.DictReader(source))
    faults.append(
        {
            "id": "O03",
            "state": {**own, "runtime_observation": native},
            "projection": "first original native row; no renamed fields, invented units, status or healthy baseline",
        }
    )
    bundle = {
        "jobs": jobs,
        "excluded": excluded,
        "manifest_sha256": canonical_digest(manifest),
        "protocol_sha256": canonical_digest(protocol),
        "phase2_seal_sha256": digest_file(
            ROOT / "docs/evidence/issue-78/phase-2/seal.json"
        ),
        "policy": protocol["policy"],
    }
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ReadinessError("output_directory_not_empty")
    (output / "jobs.json").write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n"
    )
    (output / "fault-cases.json").write_text(
        json.dumps({"faults": faults, "safety": safety}, indent=2, sort_keys=True)
        + "\n"
    )
    metadata = {
        "input_bundle_sha256": canonical_digest(jobs),
        "input_file_sha256": digest_file(output / "jobs.json"),
        "jobs": [
            {k: v for k, v in j.items() if k not in {"state", "candidates"}}
            for j in jobs
        ],
        "excluded": excluded,
        "manifest_sha256": bundle["manifest_sha256"],
        "protocol_sha256": bundle["protocol_sha256"],
        "policy": bundle["policy"],
    }
    (output / "input-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )
    return metadata


def main() -> None:
    """Write only to a new private output directory, never the source cache."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.cache_root.resolve(), args.output.resolve())
    except (ReadinessError, OSError, ValueError, KeyError, StopIteration):
        parser.exit(1, "runtime_preparation_input_invalid\n")
    print(
        json.dumps({"jobs": len(report["jobs"]), "excluded": len(report["excluded"])})
    )


if __name__ == "__main__":
    main()
