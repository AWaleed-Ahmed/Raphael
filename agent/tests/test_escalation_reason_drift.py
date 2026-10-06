"""Keep emitted private reason codes and the schema in lockstep without I/O guards."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from raphael_agent.escalation_reasons import ESCALATION_REASON_CODES
from raphael_agent.graph.nodes import _escalation
from raphael_agent.schema_util import load_agent_schema, validate_agent


ROOT = Path(__file__).resolve().parents[2]


def literal_results(expr: ast.AST, bindings=None, seen=frozenset()) -> set[str]:
    """Only string results, not condition text, messages, or lookup key names."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return {expr.value}
    if isinstance(expr, ast.Name) and bindings and expr.id not in seen:
        return set().union(*(literal_results(value, bindings, seen | {expr.id})
                             for value in bindings.get(expr.id, [])))
    if isinstance(expr, ast.IfExp):
        return literal_results(expr.body, bindings, seen) | literal_results(expr.orelse, bindings, seen)
    if isinstance(expr, ast.BoolOp):
        return set().union(*(literal_results(value, bindings, seen) for value in expr.values))
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id == "str":
        return set().union(*(literal_results(value, bindings, seen) for value in expr.args))
    return set()


def emitted_literals(source: str) -> set[str]:
    tree = ast.parse(source)
    reasons: set[str] = set()
    bindings: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings.setdefault(target.id, []).append(node.value)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in {"reason_code", "blocked_reason"}:
                    reasons.update(literal_results(keyword.value, bindings))
            if isinstance(node.func, ast.Name) and node.func.id == "TemplateRefusal" and node.args:
                reasons.update(literal_results(node.args[0], bindings))
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in {"reason_code", "blocked_reason"}:
                    reasons.update(literal_results(value, bindings))
    return reasons


def test_reason_schema_matches_single_code_vocabulary():
    actual = load_agent_schema("escalation_report.json")["properties"]["reason_code"]["enum"]
    assert len(actual) == len(set(actual))
    assert set(actual) == ESCALATION_REASON_CODES


@pytest.mark.parametrize("reason", sorted(ESCALATION_REASON_CODES))
def test_every_registered_reason_constructs_a_valid_report(reason):
    report = _escalation(
        {}, reason_code=reason, summary="Human review required",
        what_happened="No supported automatic repair was established",
        why_no_fix="Evidence does not justify a safe patch",
    )
    assert report["reason_code"] == reason
    validate_agent("escalation_report.json", report)


def test_source_emitted_reason_literals_are_registered():
    # Dispatch terminal reasons and publication error details are NOT reports.
    # Scan all agent producers, including new modules, rather than a file allowlist.
    found: set[str] = set()
    unknown: dict[str, list[str]] = {}
    for path in sorted((ROOT / "agent" / "raphael_agent").rglob("*.py")):
        emitted = emitted_literals(path.read_text(encoding="utf-8"))
        found.update(emitted)
        if missing := emitted - ESCALATION_REASON_CODES:
            unknown[str(path.relative_to(ROOT))] = sorted(missing)
    assert not unknown, f"Unregistered escalation producers: {unknown}"
    assert {"production_secret_required", "privileged_or_host_access",
            "unresolved_secret_dependency", "patch_value_unavailable",
            "budget_exhausted"} <= found


@pytest.mark.parametrize("source", [
    '_escalation({}, reason_code="future_reason")',
    'AnalyzerHit(blocked_reason="future_reason")',
    'raise TemplateRefusal("future_reason", "detail")',
    'halt = {"reason_code": "future_reason"}',
    'reason = "future_reason" if condition else "policy_blocked"\n_escalation({}, reason_code=reason)',
])
def test_source_guard_detects_new_unregistered_reason(source):
    assert emitted_literals(source) - ESCALATION_REASON_CODES == {"future_reason"}


def test_source_guard_does_not_confuse_details_or_terminal_codes_with_report_reasons():
    assert emitted_literals('state["terminal_reason"] = "job_lease_expired"') == set()
    assert emitted_literals('reason = "model_required" if detail == "not a code" else "policy_blocked"\n_escalation({}, reason_code=reason)') == {
        "model_required", "policy_blocked",
    }
