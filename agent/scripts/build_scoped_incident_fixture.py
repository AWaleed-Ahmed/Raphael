"""Reproduce the release-owned, public-source tenant-isolation fixture index."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
from raphael_agent.incident_scope import IncidentScope
from raphael_agent.local_inference.artifacts import RUNTIME_VERSIONS
from raphael_agent.local_inference.features import stable_text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

FIXTURE_SCOPES = (
    IncidentScope("fixture-tenant-a", "fixture-company-a", "fixture-client-a1"),
    IncidentScope("fixture-tenant-a", "fixture-company-a", "fixture-client-a2"),
    IncidentScope("fixture-tenant-b", "fixture-company-b", "fixture-client-b1"),
    IncidentScope("fixture-tenant-b", "fixture-company-b", "fixture-client-b2"),
)
TEXT_FIELDS = ("fingerprint", "evidence_text", "normalized_reason")


def build(source: Path, source_verification: Path, output: Path) -> dict[str, Any]:
    """Fit each test partition independently; never infer real customer ownership."""
    verification = json.loads(source_verification.read_text())
    if (
        hashlib.sha256(source.read_bytes()).hexdigest()
        != verification["fixture_sha256"]
    ):
        raise ValueError("source_fixture_hash_mismatch")
    available = {item["url"] for item in verification["sources"] if item["verified"]}
    cases = [
        case
        for line in source.read_text().splitlines()
        if (case := json.loads(line))["source"]["url"] in available
    ]
    partitions = []
    for scope in FIXTURE_SCOPES:
        rows = [
            {**case["input"], "evidence_text": case["input"]["summary"]}
            for case in cases
        ]
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        matrix = normalize(
            vectorizer.fit_transform([stable_text(row, TEXT_FIELDS) for row in rows]),
            norm="l2",
        )
        records = [
            {
                **scope.as_dict(),
                "incident_id": f"test-{scope.client_id}-{position:03d}",
                "failure_class": case["expected"]["failure_class"],
                "summary": case["input"]["summary"][:1200],
                "source_url": case["source"]["url"],
                "sandbox_result": "not_tested",
                "successful_fix_template": None,
            }
            for position, case in enumerate(cases)
        ]
        partitions.append(
            {
                "scope": scope.as_dict(),
                "vectorizer": vectorizer,
                "matrix": matrix,
                "records": records,
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    bundle = {
        "format_version": 2,
        "task": "incident_similarity",
        "text_fields": TEXT_FIELDS,
        "minimum_similarity": 0.2,
        "partitions": partitions,
    }
    artifact = output / "model.joblib"
    joblib.dump(bundle, artifact)
    data = artifact.read_bytes()
    manifest = {
        "model_name": "incident_similarity",
        "format_version": 2,
        "artifact": "model.joblib",
        "artifact_sha256": hashlib.sha256(data).hexdigest(),
        "artifact_bytes": len(data),
        "libraries": RUNTIME_VERSIONS,
        "python_version": "3.12",
        "dataset_files": [
            {
                "path": "agent/tests/fixtures/local_inference/incident_similarity.jsonl",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "cases": len(cases),
            }
        ],
        "source_verification_sha256": hashlib.sha256(
            source_verification.read_bytes()
        ).hexdigest(),
        "scope_policy": "Exact tenant/company/client partitions with independently fitted TF-IDF indexes.",
        "ownership": "Explicit synthetic test assignments; public source authors are not customer tenants.",
        "limitations": [
            "Public issue reports and marker-derived labels, not validated customer fixes.",
            "Four test partitions repeat the same 49 available source reports to exercise overlapping text.",
            "No implicit public/shared corpus; no claim of production accuracy or rollout.",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def main() -> None:
    """Write only the explicitly selected release fixture output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-verification", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.source_verification, args.output)


if __name__ == "__main__":
    main()
