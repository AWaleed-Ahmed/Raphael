"""Shared authoritative Secret-coverage check before model or patch calls."""
from __future__ import annotations

import json
from typing import Any

from jsonschema import ValidationError

from raphael_agent.schema_util import load_sandbox_schema, validate_against
from raphael_agent.evidence.redaction import redact_text


def sanitized_secret_coverage(value: Any) -> dict[str, Any] | None:
    """Copy bounded reference metadata; reject payload fields and redact text."""
    if not isinstance(value, dict):
        return None
    try:
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > 65_536:
            return None
        validate_against(load_sandbox_schema("fidelity_report.json")["properties"]["secret_coverage"], value)
    except (ValidationError, TypeError, ValueError):
        return None
    report = json.loads(encoded)
    for reference in report["references"]:
        for key, item in reference.items():
            if isinstance(item, str):
                reference[key] = redact_text(item)[0]
    return report


def required_secret_gaps(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("sandbox_mode") not in {"live", "connector"}:
        return []
    report = sanitized_secret_coverage(state.get("secret_coverage"))
    if report is None or report["complete"] is not True:
        return []  # Unknown is not evidence of a missing dependency.
    return [item for item in report["references"] if item["optional"] is not True
            and item["status"] in {"missing_object", "missing_key"}]
