"""Check actual evaluation wire payloads after a forced-CRLF checkout CI run."""
from __future__ import annotations

import json
from pathlib import Path

from evals.run_evals import body_as_json, parse_trace, trace_evidence


def verify(report_path: Path) -> list[dict]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    required = {"probe_misconfiguration", "bad_image_reference", "invalid_missing_config"}
    patch_expected = {"probe_misconfiguration"}
    scenarios = {item["scenario_id"]: item for item in report["scenarios"]}
    if not required.issubset(scenarios):
        raise ValueError("all three pinned scenarios must have run")
    checks = []
    for name in sorted(required):
        scenario = scenarios[name]
        if not scenario["passed"]:
            raise ValueError(f"{name}: evaluation failed")
        records = parse_trace(Path(scenario["trace"]))
        rendered = []
        for record in records:
            request = body_as_json(record, "request") or {}
            payload = request.get("payload") or {}
            if (request.get("kind") == "result"
                    and payload.get("job_id") == scenario["job_id"]
                    and payload.get("verb") == "deploy_revision"):
                rendered.extend((payload.get("result") or {}).get("rendered_files") or [])
        patch_files = trace_evidence(records, scenario["job_id"])["patch_files"]
        if not rendered or (name in patch_expected and not patch_files) or (name not in patch_expected and patch_files):
            raise ValueError(f"{name}: incorrect render/patch evidence for expected outcome")
        for item in rendered + patch_files:
            content = item.get("content")
            if not isinstance(content, str) or "\r\n" in content:
                raise ValueError(f"{name}: non-LF content in {item.get('path')}")
        checks.append({
            "scenario": name,
            "rendered_file_payloads_checked": len(rendered),
            "patch_files_checked": len(patch_files),
            "crlf_pairs": 0,
            "changed_lines": scenario["actual"]["patch_changed_line_count"],
            "passed": True,
        })
    return checks


if __name__ == "__main__":
    path = Path("evals/out/eval-results.json")
    checks = verify(path)
    output = json.dumps(checks, indent=2) + "\n"
    (path.parent / "line-endings.json").write_text(output, encoding="utf-8")
    print(output, end="")
