"""Validate a phase-1 source freeze and prepare two unexecuted evaluation arms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

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
    verify_baseline,
    verify_evidence,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "agent/fixtures/production_readiness"


def main() -> None:
    """Write preparation evidence; no model is loaded or prediction performed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=FIXTURES / "source-manifest.json"
    )
    parser.add_argument("--protocol", type=Path, default=FIXTURES / "protocol.json")
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--training-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-final-ready", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text())
        protocol = json.loads(args.protocol.read_text())
        schema = json.loads((FIXTURES / "source-manifest.schema.json").read_text())
        validate_manifest(manifest, schema)
        verify_baseline(ROOT, protocol)
        jobs = paired_jobs(manifest, protocol)
        for left, right in zip(jobs[::2], jobs[1::2], strict=True):
            validate_pair(left, right, protocol)
        blockers = freeze_blockers(manifest, protocol)
        report: dict[str, Any] = {
            "status": "prepared_not_scored",
            "manifest_file_sha256": digest_file(args.manifest),
            "protocol_file_sha256": digest_file(args.protocol),
            "schema_file_sha256": digest_file(FIXTURES / "source-manifest.schema.json"),
            "verifier_sources_sha256": {
                relative: digest_file(ROOT / relative)
                for relative in (
                    "agent/raphael_agent/readiness.py",
                    "agent/scripts/prepare_model_readiness.py",
                    "agent/scripts/fetch_readiness_evidence.py",
                )
            },
            "manifest_sha256": canonical_digest(manifest),
            "protocol_sha256": canonical_digest(protocol),
            "cases": len(manifest["cases"]),
            "paired_jobs": len(jobs),
            "raw_evidence": (
                verify_evidence(manifest, args.cache_root)
                if args.cache_root
                else {"verified": False}
            ),
            "training": (
                audit_training(ROOT, args.training_root) if args.training_root else None
            ),
            "final_freeze_blockers": blockers,
            "predictions_executed": 0,
            "source_overlap": (
                audit_source_overlap(ROOT, args.training_root, manifest)
                if args.training_root
                else None
            ),
        }
        if not args.cache_root:
            blockers.append("raw_evidence_not_verified")
        if not args.training_root:
            blockers.append("training_provenance_not_audited")
        if report["training"] and any(
            not model["trusted_artifact_matches"]
            or any(not item.get("hash_matches") for item in model["dataset_files"])
            for model in report["training"].values()
        ):
            blockers.append("training_or_artifact_hash_unresolved")
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "preparation.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        (args.output / "paired-jobs.jsonl").write_text(
            "".join(json.dumps(job, sort_keys=True) + "\n" for job in jobs)
        )
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "cases": report["cases"],
                    "paired_jobs": len(jobs),
                    "predictions": 0,
                    "final_freeze_blockers": len(blockers),
                }
            )
        )
        if args.require_final_ready and blockers:
            raise SystemExit(2)
    except (ReadinessError, OSError, json.JSONDecodeError, KeyError) as exc:
        parser.exit(
            1,
            (
                str(exc) + "\n"
                if isinstance(exc, ReadinessError)
                else "preparation_input_invalid\n"
            ),
        )


if __name__ == "__main__":
    main()
