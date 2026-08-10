"""GitHub Actions evidence adapter — Phase 1 uses webhook/correlation context.

Full Actions API log download lands later; here we materialize bounded evidence
from the correlated ingest fields + optional stored raw webhook pointer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raphael_agent.evidence.redaction import redact_evidence_item
from raphael_agent.timeutil import utc_now


def collect_github_actions_evidence(run: dict[str, Any]) -> list[dict[str, Any]]:
    trigger = run.get("trigger") or {}
    kind = trigger.get("kind")
    if kind not in {
        "github_workflow_run",
        "github_check_run",
        "github_deployment_status",
    }:
        return []

    now = utc_now()
    correlation = run.get("correlation") or {}
    repo = run.get("repository") or {}
    items: list[dict[str, Any]] = []

    job_label = (
        correlation.get("workflow_name")
        or correlation.get("check_name")
        or kind
    )
    items.append(
        {
            "evidence_id": "ev-gh-trigger-1",
            "kind": "ci_log",
            "source": {
                "system": "github_actions",
                "ref": str(trigger.get("event_id") or trigger.get("raw_ref") or kind),
            },
            "summary": f"GitHub {kind} failure for {job_label}",
            "content_excerpt": (
                f"repo={repo.get('owner')}/{repo.get('name')} "
                f"sha={run.get('commit_sha')} job={job_label} "
                f"fingerprint={run.get('failure_fingerprint')}"
            ),
            "redacted": False,
            "provenance": {
                "collector": "evidence.github_actions",
                "query": f"trigger:{trigger.get('event_id')}",
            },
            "collected_at": now,
            "labels": {"trigger_kind": str(kind)},
        }
    )

    raw_ref = trigger.get("raw_ref")
    if raw_ref and Path(str(raw_ref)).is_file():
        try:
            raw = json.loads(Path(str(raw_ref)).read_text(encoding="utf-8"))
            excerpt = json.dumps(raw, default=str)[:1200]
        except (OSError, json.JSONDecodeError):
            excerpt = f"raw event at {raw_ref}"
        items.append(
            {
                "evidence_id": "ev-gh-raw-1",
                "kind": "artifact",
                "source": {"system": "github_actions", "ref": str(raw_ref)},
                "summary": "Bounded raw webhook payload excerpt",
                "content_excerpt": excerpt,
                "redacted": False,
                "provenance": {
                    "collector": "evidence.github_actions",
                    "query": f"raw_ref:{raw_ref}",
                },
                "collected_at": now,
            }
        )

    return [redact_evidence_item(item) for item in items]
