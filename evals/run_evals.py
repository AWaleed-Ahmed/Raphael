"""Run versioned Raphael evaluation scenarios through the real E2E process path."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
EVALS = Path(__file__).resolve().parent
SCENARIOS = EVALS / "scenarios"
SCHEMA_PATH = EVALS / "manifest.schema.json"
REAL_RUNNER = ROOT / "e2e" / "run_real_job.py"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data


def load_scenarios(selected: set[str] | None = None) -> list[dict[str, Any]]:
    schema = load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    scenarios: list[dict[str, Any]] = []
    for path in sorted(SCENARIOS.glob("*/manifest.json")):
        manifest = load_json(path)
        errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.path))
        if errors:
            detail = "; ".join(error.message for error in errors)
            raise ValueError(f"{path}: invalid manifest: {detail}")
        scenario_id = manifest["scenario_id"]
        if selected and scenario_id not in selected:
            continue
        manifest["_path"] = str(path)
        scenarios.append(manifest)
    if selected:
        found = {scenario["scenario_id"] for scenario in scenarios}
        missing = sorted(selected - found)
        if missing:
            raise ValueError(f"unknown scenario id(s): {', '.join(missing)}")
    if not scenarios:
        raise ValueError("no evaluation scenario manifests found")
    return scenarios


def parse_trace(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid trace JSON: {exc}") from exc
        if isinstance(item, dict):
            records.append(item)
    return records


def body_as_json(record: dict[str, Any], side: str) -> dict[str, Any] | None:
    body = (record.get(side) or {}).get("body")
    if not isinstance(body, str) or not body:
        return None
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def trace_evidence(records: list[dict[str, Any]], job_id: str) -> dict[str, Any]:
    """Extract only structured evidence actually carried on the dispatch wire."""
    observed_signature: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    patch_files: list[dict[str, Any]] = []
    initial_rendered_files: dict[str, str] = {}
    terminal: dict[str, Any] | None = None

    for record in records:
        request = body_as_json(record, "request")
        response = body_as_json(record, "response")

        if request and request.get("kind") == "result":
            payload = request.get("payload") or {}
            if payload.get("job_id") == job_id:
                result = payload.get("result") or {}
                if payload.get("verb") == "observe_failure" and isinstance(result.get("signature"), dict):
                    observed_signature = result["signature"]
                if payload.get("verb") == "run_validation" and isinstance(result, dict):
                    validation = result
                if payload.get("verb") == "deploy_revision" and not initial_rendered_files:
                    for item in result.get("rendered_files") or []:
                        if isinstance(item, dict) and isinstance(item.get("path"), str) and isinstance(item.get("content"), str):
                            initial_rendered_files[item["path"]] = item["content"]

        if not response:
            continue
        for message in response.get("messages") or []:
            if not isinstance(message, dict):
                continue
            payload = message.get("payload") or {}
            if payload.get("job_id") != job_id:
                continue
            if message.get("kind") == "action" and payload.get("verb") == "deploy_revision":
                files = ((payload.get("args") or {}).get("patch") or {}).get("files")
                if isinstance(files, list):
                    patch_files = [item for item in files if isinstance(item, dict)]
            if message.get("kind") == "terminal":
                terminal = payload

    return {
        "observed_signature": observed_signature,
        "validation": validation,
        "patch_files": patch_files,
        "initial_rendered_files": initial_rendered_files,
        "terminal": terminal,
    }


def patch_line_changes(patch_files: list[dict[str, Any]], originals: dict[str, str]) -> tuple[int | None, list[str]]:
    """Return the exact added/removed lines, rejecting a patch without its original source."""
    changed_lines: list[str] = []
    for item in patch_files:
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not isinstance(content, str) or path not in originals:
            return None, []
        diff = difflib.unified_diff(
            originals[path].splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        changed_lines.extend(
            line.rstrip("\n")
            for line in diff
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
        )
    return len(changed_lines), changed_lines


def nested(mapping: dict[str, Any] | None, *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def score_scenario(manifest: dict[str, Any], runner_result: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    job_id = str(runner_result.get("job_id") or "")
    evidence = trace_evidence(records, job_id)
    state = runner_result.get("run_state") if isinstance(runner_result.get("run_state"), dict) else {}
    diagnosis = state.get("diagnosis") if isinstance(state.get("diagnosis"), dict) else {}
    diagnosis_class = nested(diagnosis, "classification", "failure_class")
    asserted_confidence = (
        nested(diagnosis, "classification", "confidence")
        or diagnosis.get("confidence")
        or nested(evidence["observed_signature"], "confidence")
    )
    expected = manifest["expected"]
    required = manifest["required_evidence"]

    actual_terminal = nested(evidence["terminal"], "final_status") or runner_result.get("final_status")
    actual_class = diagnosis_class or nested(evidence["observed_signature"], "class")
    patch_files = evidence["patch_files"]
    patch_scope = expected.get("patch_scope") or {}
    allowed_paths = set(patch_scope.get("allowed_file_paths") or [])
    actual_paths = {str(item.get("path")) for item in patch_files if item.get("path")}
    patch_contents = "\n".join(str(item.get("content") or "") for item in patch_files)
    required_content = patch_scope.get("required_content") or []
    changed_line_count, changed_lines = patch_line_changes(patch_files, evidence["initial_rendered_files"])
    required_changed_line_fragments = patch_scope.get("required_changed_line_fragments") or []

    patch_scope_correct = True
    if patch_scope:
        patch_scope_correct = (
            bool(patch_files)
            and actual_paths.issubset(allowed_paths)
            and all(fragment in patch_contents for fragment in required_content)
            and changed_line_count is not None
            and changed_line_count <= patch_scope["max_changed_lines"]
            and all(fragment in changed_lines for fragment in required_changed_line_fragments)
        )
    assertions = {
        "classification_correct": actual_class == expected["failure_class"],
        "terminal_state_correct": actual_terminal == expected["terminal_status"],
        "patch_scope_correct": patch_scope_correct,
        "pre_fix_signature_present": bool(evidence["observed_signature"]) == required["pre_fix_signature"],
        "validation_matches": (
            nested(evidence["validation"], "passed") == required["validation"]["passed"]
            and nested(evidence["validation"], "signature_cleared") == required["validation"]["signature_cleared"]
        ),
        "terminal_instruction_matches": nested(evidence["terminal"], "instructions") == required["terminal_instruction"],
    }
    escalation_expected = manifest["category"] == "expected_escalation"
    escalation_observed = actual_terminal == "escalated"
    return {
        "scenario_id": manifest["scenario_id"],
        "manifest": manifest["_path"],
        "fixture_commit": manifest["fixture"]["commit_sha"],
        "job_id": job_id or None,
        "runner_exit_code": runner_result.get("runner_exit_code"),
        "asserted_confidence": asserted_confidence,
        "was_diagnosis_correct": assertions["classification_correct"],
        "escalation_expected": escalation_expected,
        "escalation_observed": escalation_observed,
        "actual": {
            "failure_class": actual_class,
            "terminal_status": actual_terminal,
            "patch_paths": sorted(actual_paths),
            "patch_changed_line_count": changed_line_count,
            "patch_changed_lines": changed_lines,
        },
        "assertions": assertions,
        "passed": runner_result.get("runner_exit_code") == 0 and all(assertions.values()),
        "trace": runner_result.get("trace_file"),
        "runner_log": runner_result.get("runner_log"),
    }


def run_scenario(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    scenario_dir = output_dir / manifest["scenario_id"]
    scenario_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "E2E_REAL_CLONE_URL": manifest["fixture"]["clone_url"],
        "E2E_REAL_COMMIT_SHA": manifest["fixture"]["commit_sha"],
        "E2E_REAL_NARROWED_LOCATION": manifest["narrowed_location"]["file_path"],
        "E2E_TRACE_FILE": str(scenario_dir / "trace.jsonl"),
        "E2E_REAL_RESULT_FILE": str(scenario_dir / "runner-result.json"),
        "E2E_REAL_DISPATCH_LOG": str(scenario_dir / "dispatch.log"),
        "E2E_REAL_IGNIS_LOG": str(scenario_dir / "ignis.log"),
    })
    started = time.monotonic()
    try:
        completed = subprocess.run(
            [sys.executable, str(REAL_RUNNER)],
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
        )
        stdout = completed.stdout
        return_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        stdout += "\nERROR: evaluation runner timed out after 300 seconds\n"
        return_code = 124
    runner_log = scenario_dir / "runner.log"
    runner_log.write_text(stdout, encoding="utf-8")
    print(f"\n=== {manifest['scenario_id']} ({return_code}) ===")
    print(stdout, end="" if stdout.endswith("\n") else "\n")
    result_path = scenario_dir / "runner-result.json"
    runner_result = load_json(result_path) if result_path.is_file() else {}
    runner_result["runner_exit_code"] = return_code
    runner_result["runner_log"] = str(runner_log)
    runner_result["elapsed_seconds"] = runner_result.get("elapsed_seconds") or round(time.monotonic() - started, 3)
    records = parse_trace(scenario_dir / "trace.jsonl")
    return score_scenario(manifest, runner_result, records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", action="append", default=[], help="run one scenario id; repeatable")
    parser.add_argument("--output-dir", default=os.getenv("EVAL_OUTPUT_DIR", str(EVALS / "out")))
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios(set(args.scenario) or None)
    results = [run_scenario(manifest, output_dir) for manifest in scenarios]
    report = {
        "schema_version": "1.0",
        "generated_at_epoch_seconds": time.time(),
        "scenario_count": len(results),
        "passed": all(result["passed"] for result in results),
        "scenarios": results,
    }
    report_path = output_dir / "eval-results.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("\n=== Evaluation summary ===")
    for result in results:
        print(
            f"{'PASS' if result['passed'] else 'FAIL'} {result['scenario_id']}: "
            f"class={result['actual']['failure_class']} terminal={result['actual']['terminal_status']} "
            f"confidence={result['asserted_confidence']}"
        )
    print(f"Results: {report_path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
