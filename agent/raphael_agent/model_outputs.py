"""Validate advisory model outputs before they affect graph state."""

from __future__ import annotations

import math
from typing import Any

from .incident_scope import IncidentScope

MODEL_CLASSES = {
    "bad_image_reference",
    "resource_exhaustion",
    "invalid_missing_config",
    "probe_misconfiguration",
    "service_port_mismatch",
    "auth_denied",
    "dependency_timeout",
    "db_error",
    "network_error",
    "latency_regression",
    "trace_divergence",
    "healthy",
    "unknown",
}
# These families have concrete generators in patch/templates.py. Everything
# still passes through provenance, file allowlists, policy and sandbox validation.
PATCH_TEMPLATES = {
    "fix_probe_port_mismatch",
    "adjust_readiness_probe_path",
    "tune_probe_timeout_seconds",
    "restore_known_good_image",
    "revert_image_digest",
    "restore_configmap_key",
}


def probability(value: Any) -> bool:
    """Accept finite real probabilities, excluding booleans."""
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def finite_tree(value: Any) -> bool:
    """Reject non-finite numbers anywhere in JSON model output."""
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and finite_tree(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return all(finite_tree(item) for item in value)
    return value is None or isinstance(value, (str, bool, int))


def valid_output(
    method: str, result: Any, payload: Any, scope: IncidentScope | None
) -> bool:
    """Validate shape, score bounds, taxonomy and canonical identities."""
    if not isinstance(result, dict) or not finite_tree(result):
        return False
    if method == "classify_failure":
        return (
            type(result.get("abstained")) is bool
            and probability(result.get("confidence"))
            and (result["abstained"] or result.get("failure_class") in MODEL_CLASSES)
        )
    if method == "detect_trace":
        return (
            type(result.get("is_anomaly")) is bool
            and type(result.get("abstained")) is bool
            and probability(result.get("anomaly_probability"))
            and probability(result.get("threshold"))
        )
    if method == "select_patch":
        if type(result.get("policy_allowed")) is not bool:
            return False
        return not result["policy_allowed"] or (
            isinstance(result.get("safe_template"), str)
            and bool(result.get("safe_template"))
            and probability(result.get("allowed_probability"))
            and probability(result.get("template_confidence"))
            and result.get("requires_sandbox_validation") is True
        )
    if method == "rank_candidates":
        rows = result.get("candidates")

        def key(row: dict[str, Any]) -> tuple[Any, Any, Any]:
            return (
                row.get("candidate_path"),
                row.get("candidate_line", 0),
                row.get("candidate_symbol"),
            )

        return (
            isinstance(rows, list)
            and all(isinstance(row, dict) for row in rows)
            and len(rows) == len(payload)
            and sorted(map(repr, map(key, rows)))
            == sorted(map(repr, map(key, payload)))
            and all(
                probability(row.get("model_score"))
                and probability(row.get("evidence_score"))
                and probability(row.get("learned_score"))
                for row in rows
            )
        )
    if method == "retrieve_incidents":
        rows = result.get("results")
        return (
            scope is not None
            and isinstance(rows, list)
            and all(
                isinstance(row, dict)
                and probability(row.get("similarity"))
                and all(row.get(key) == value for key, value in scope.as_dict().items())
                for row in rows
            )
        )
    return False


def execution_source(result: dict[str, Any] | None, error: str | None = None) -> str:
    """Describe the effective answer separately from estimator execution."""
    if result is None:
        return (
            "disabled" if error == "disabled_by_environment" else "unavailable_fallback"
        )
    if result.get("abstained") or result.get("policy_allowed") is False:
        return "abstention"
    if result.get("rule_based"):
        return "deterministic_rule_override"
    return "trained_inference" if result.get("learned_execution") else "deterministic"
