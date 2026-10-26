"""Replay provenance-bearing public fixtures against approved local artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from raphael_agent.incident_scope import configured_scope
from raphael_agent.local_inference import predict
from raphael_agent.local_inference.artifacts import RUNTIME_VERSIONS, TRUSTED_ARTIFACTS

METHODS = {
    "failure_classifier": "classify_failure",
    "candidate_ranker": "rank_candidates",
    "incident_similarity": "retrieve_incidents",
    "patch_selector": "select_patch",
    "trace_anomaly": "detect_trace",
}


def qualify(model_root: Path, cases_root: Path) -> dict[str, Any]:
    """Report execution and observed quality separately; do not tune labels."""
    models: dict[str, Any] = {}
    for name, method in METHODS.items():
        path = cases_root / f"{name}.jsonl"
        cases = [json.loads(line) for line in path.read_text().splitlines()]
        predictions = []
        correct = 0
        labeled = 0
        for case in cases:
            payload = case["input"]
            if name == "candidate_ranker":
                payload = payload["candidates"]
            function = getattr(predict, method)
            result = (
                function(model_root, payload, 5, scope=configured_scope())
                if name == "incident_similarity"
                else function(model_root, payload)
            )
            expected = case["expected"]
            if name == "failure_classifier":
                matched = result["failure_class"] == expected["failure_class"]
            elif name == "candidate_ranker":
                matched = (
                    result["candidates"][0]["candidate_path"]
                    in expected["patched_source_files"]
                )
            elif name == "incident_similarity":
                matched = (
                    bool(result["results"])
                    and result["results"][0]["failure_class"]
                    == expected["failure_class"]
                )
            elif name == "trace_anomaly":
                matched = result["is_anomaly"] == expected["is_anomaly"]
            else:
                matched = bool(result.get("policy_allowed")) and result.get(
                    "safe_template"
                ) in expected.get("acceptable_templates", [])
            if "learned_execution" not in expected:
                labeled += 1
                correct += int(matched)
            predictions.append(
                {"source_url": case["source"]["url"], "prediction": result}
            )
        learned = sum(
            bool(row["prediction"]["learned_execution"]) for row in predictions
        )
        if not learned:
            raise AssertionError(f"No learned execution for {name}")
        models[name] = {
            "cases": len(cases),
            "learned_execution": learned,
            "rule_overrides": sum(
                bool(row["prediction"].get("rule_based")) for row in predictions
            ),
            "abstained": sum(
                bool(row["prediction"].get("abstained")) for row in predictions
            ),
            "observed_label_matches": correct,
            "labeled_cases": labeled,
            "fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "predictions_sha256": hashlib.sha256(
                json.dumps(predictions, sort_keys=True).encode()
            ).hexdigest(),
            "artifact_sha256": TRUSTED_ARTIFACTS[name][1],
        }
    return {
        "python": platform.python_version(),
        "libraries": RUNTIME_VERSIONS,
        "models": models,
        "limits": [
            "Runtime qualification, not production calibration.",
            "GitHub failure labels are marker-derived; patch labels are hypotheses.",
            "BugsInPy ranking labels identify fix files, not causal lines.",
            "RCAEval labels are controlled fault windows, not individual trace truth.",
            "The extra Fission probe case verifies learned execution only.",
        ],
    }


def main() -> None:
    """Write a deterministic replay summary for explicitly supplied data roots."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--cases-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = qualify(args.model_root.resolve(), args.cases_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
