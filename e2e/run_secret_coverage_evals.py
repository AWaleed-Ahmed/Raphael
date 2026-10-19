"""Two undecorated structural-Secret controls using the existing real-hooks evaluator."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals.run_evals import load_json, run_scenario, SCHEMA_PATH  # noqa: E402
from raphael_agent.diagnosis.analyzers import analyze_run  # noqa: E402


def main() -> int:
    output = ROOT / "e2e/secret-coverage-out"
    output.mkdir(parents=True, exist_ok=True)
    proof = output / "proof.json"
    proof.unlink(missing_ok=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="secret-coverage-evals-") as temp:
        fixture = Path(temp) / "source.git"
        shutil.copytree(ROOT / "e2e/fixtures/kind-remediation/probe", fixture)
        for args in [
            ["init"], ["add", "."],
            ["-c", "user.name=Fixture CI", "-c", "user.email=fixture@example.invalid",
             "commit", "-m", "Undecorated Secret dependency and probe fixture"],
        ]:
            subprocess.run(["git", *args], cwd=fixture, check=True, capture_output=True)
        assert not any(hit.category == "blocked" for hit in analyze_run({
            "workspace_path": str(fixture), "manifests": {"path": "deploy/manifests"}}))
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fixture, text=True).strip()
        for covered in (False, True):
            manifest = load_json(ROOT / "evals/scenarios/probe_misconfiguration/manifest.json")
            manifest["scenario_id"] = "structural_secret_covered" if covered else "structural_secret_missing"
            manifest["fixture"] = {"repository": "fixture/secret-coverage", "clone_url": fixture.as_uri(), "commit_sha": sha}
            if not covered:
                manifest["expected"] = {"failure_class": "probe_misconfiguration", "terminal_status": "escalated",
                                        "terminal_reason": "unresolved_secret_dependency"}
                manifest["required_evidence"] = {
                    "pre_fix_signature": True, "validation": {"attempted": False},
                    "terminal_instruction": "discard_local_copy", "no_candidate_patch": True, "no_publish": True,
                    "escalation_report": {"reason_code": "unresolved_secret_dependency",
                                          "contains": ["payments-db", "DATABASE_URL"],
                                          "required_fields": ["what_happened", "evidence_ids", "why_no_fix", "recommended_next_checks"]},
                }
                manifest["category"] = "expected_escalation"
            Draft202012Validator(load_json(SCHEMA_PATH), format_checker=FormatChecker()).validate(manifest)
            path = output / (manifest["scenario_id"] + ".json")
            path.write_text(json.dumps(manifest, indent=2) + "\n")
            manifest["_path"] = str(path)
            os.environ["RAPHAEL_SECRET_FIXTURE_SET"] = "payments-test" if covered else ""
            os.environ["RAPHAEL_MODEL_ENABLED"] = "0"
            os.environ["RAPHAEL_LLM_PATCH"] = "0"
            os.environ["RAPHAEL_LEARNING"] = "0"
            result = run_scenario(manifest, output)
            results.append(result)
            state = load_json(output / manifest["scenario_id"] / "runner-result.json")["run_state"]
            coverage = state["secret_coverage"]
            assert coverage["complete"] and not coverage["truncated"]
            assert len(coverage["references"]) == 1
            assert coverage["references"][0]["status"] == ("covered" if covered else "missing_object")
            assert result["passed"], result["assertions"]
    proof.write_text(json.dumps({"passed": True, "backend": "mock", "ignis_ref": os.getenv("IGNIS_REF"),
                                 "raphael_revision": os.getenv("GITHUB_SHA"), "scenarios": results}, indent=2) + "\n")
    print("PASS required-missing refusal and covered probe repair with real agent hooks; mock Kubernetes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
