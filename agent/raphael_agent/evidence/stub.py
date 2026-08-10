"""Fixture evidence collector (Phase 0 path)."""

from __future__ import annotations

from typing import Any

from raphael_agent.evidence.redaction import redact_evidence_item
from raphael_agent.timeutil import utc_now


def collect_fixture_evidence(run: dict[str, Any]) -> list[dict[str, Any]]:
    now = utc_now()
    resources = run.get("affected_resources") or []
    resource_name = resources[0]["name"] if resources else "payments-api"
    items = [
        {
            "evidence_id": "ev-ci-1",
            "kind": "ci_log",
            "source": {"system": "fixture", "ref": "workflow/deploy"},
            "summary": "Deployment job failed readiness check",
            "content_excerpt": f"Readiness probe failed for {resource_name}",
            "redacted": True,
            "redaction_notes": ["no_secrets_in_fixture"],
            "provenance": {
                "collector": "evidence.stub",
                "query": "fixture:ci_log",
            },
            "collected_at": now,
        },
        {
            "evidence_id": "ev-k8s-1",
            "kind": "k8s_event",
            "source": {"system": "fixture", "ref": f"event/{resource_name}"},
            "summary": "Unhealthy probe reported",
            "content_excerpt": (
                "Readiness probe failed: HTTP probe failed with statuscode: 503"
            ),
            "redacted": True,
            "redaction_notes": ["no_secrets_in_fixture"],
            "provenance": {
                "collector": "evidence.stub",
                "query": "fixture:k8s_event",
            },
            "collected_at": now,
        },
    ]
    return [redact_evidence_item(item) for item in items]


# Back-compat alias
def stub_collect_evidence(run: dict[str, Any]) -> list[dict[str, Any]]:
    return collect_fixture_evidence(run)
