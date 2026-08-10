"""Evidence collection stubs — Phase 1 will call GitHub / K8s adapters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def stub_collect_evidence(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Return minimal fixture evidence with provenance + redaction flags."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resources = run.get("affected_resources") or []
    resource_name = resources[0]["name"] if resources else "payments-api"
    return [
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
            "content_excerpt": "Readiness probe failed: HTTP probe failed with statuscode: 503",
            "redacted": True,
            "redaction_notes": ["no_secrets_in_fixture"],
            "provenance": {
                "collector": "evidence.stub",
                "query": "fixture:k8s_event",
            },
            "collected_at": now,
        },
    ]
