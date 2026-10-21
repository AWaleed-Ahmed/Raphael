"""Validate private reports at transition boundaries, not in persistence."""
from functools import wraps
import logging
from typing import Any

from jsonschema import ValidationError

from raphael_agent.schema_util import validate_agent
from raphael_agent.graph.state import RunState
from raphael_agent.timeutil import utc_now

LOG = logging.getLogger(__name__)


def escalation_failure_updates(state: dict[str, Any]) -> dict[str, Any]:
    """Return safe terminal updates, never the rejected values or exception text."""
    report = state.get("escalation_report")
    if report is None:
        return {}
    try:
        validate_agent("escalation_report.json", report)
    except ValidationError as exc:
        path = "/".join(str(part) for part in exc.absolute_schema_path)
        schema_path = "contracts/agent/escalation_report.json#/" + path
        LOG.error("Escalation report rejected at schema path %s", schema_path)
        now = utc_now()
        return {
            "status": "failed_closed", "terminal_reason": "escalation_report_invalid",
            "current_node": None, "updated_at": now,
            "escalation_report": {
                "reason_code": "escalation_report_invalid",
                "summary": "Escalation report failed validation",
                "what_happened": "The report did not satisfy its private schema",
                "evidence_ids": [], "hypotheses_considered": [], "attempts": [],
                "why_no_fix": "Invalid reporting state prevents safe continuation",
                "recommended_next_checks": ["Review the report schema and its producer"],
                "escalated_at": now,
            },
            "candidate_patches": [], "validated_fix_record": None,
            "pull_request_url": None, "pull_request_branch": None, "publish": None,
            "audit_events": list(state.get("audit_events") or []) + [{
                "at": now, "node": "escalation_validation",
                "event": "escalation_report_invalid", "detail": schema_path,
            }],
        }
    return {}


def escalation_report_boundary(node):
    """Check node-produced reports before another graph node can act on them."""
    @wraps(node)
    def guarded(state: RunState):
        failure = escalation_failure_updates(state)
        if failure:
            return failure
        updates = node(state)
        failure = escalation_failure_updates({**state, **updates})
        return {**updates, **failure} if failure else updates
    return guarded
