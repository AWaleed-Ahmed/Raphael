"""Shared authoritative Secret-coverage check before model or patch calls."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import ValidationError

from raphael_agent.schema_util import load_sandbox_schema, validate_against


def required_secret_gaps(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("sandbox_mode") not in {"live", "connector"}:
        return []
    report = state.get("secret_coverage")
    if not isinstance(report, dict):
        return []
    try:
        validate_against(load_sandbox_schema("fidelity_report.json")["properties"]["secret_coverage"], report)
        if len(json.dumps(report, ensure_ascii=False).encode("utf-8")) > 65_536:
            return []
    except (ValidationError, TypeError, ValueError):
        return []
    if report.get("complete") is not True:
        return []  # Unknown is not evidence of a missing dependency.
    return [item for item in report["references"] if item["optional"] is not True
            and item["status"] in {"missing_object", "missing_key"}]
