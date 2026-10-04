"""Escalation reports are validated before either durable store writes."""

from __future__ import annotations

from copy import deepcopy

import pytest
from jsonschema import ValidationError

from raphael_agent.store import RunStore, SqliteRunStore


def _valid_report():
    return {
        "reason_code": "low_confidence",
        "summary": "review required",
        "what_happened": "Diagnosis did not clear its confidence gate",
        "evidence_ids": [],
        "hypotheses_considered": [],
        "attempts": [],
        "why_no_fix": "No supported fix was established",
        "recommended_next_checks": ["Review the run evidence"],
        "escalated_at": "2026-10-04T00:00:00Z",
    }


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
@pytest.mark.parametrize(
    "invalid_change",
    [
        {"reason_code": "unknown_reason"},
        {"attempts": [{"kind": "other", "status": "unknown_status"}]},
    ],
)
def test_invalid_report_does_not_overwrite_existing_record(
    tmp_path, store_type, invalid_change
):
    store = store_type(tmp_path / store_type.__name__)
    valid = {"run_id": "review-report-1", "status": "escalated", "escalation_report": _valid_report()}
    store.save_run(valid)

    invalid = deepcopy(valid)
    invalid["escalation_report"].update(invalid_change)
    with pytest.raises(ValidationError):
        store.save_run(invalid)

    assert store.get_run(valid["run_id"]) == valid
