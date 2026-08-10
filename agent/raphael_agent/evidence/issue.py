"""Issue-body evidence for Route B."""

from __future__ import annotations

from typing import Any

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.timeutil import utc_now


def collect_issue_evidence(run: dict[str, Any]) -> list[dict[str, Any]]:
    trigger = run.get("trigger") or {}
    has_issue = bool(run.get("issue_body") or run.get("issue_title") or run.get("issue_number"))
    if trigger.get("kind") != "github_issue" and run.get("delivery_mode") != "issue_snippet":
        if not has_issue:
            return []

    title = run.get("issue_title") or ""
    body = run.get("issue_body") or ""
    labels = run.get("issue_labels") or []
    issue_number = run.get("issue_number")
    repo = run.get("repository") or {}
    owner = repo.get("owner") or "unknown"
    name = repo.get("name") or "unknown"
    redacted_body, notes = redact_text(body)
    content = (
        f"title: {title}\n"
        f"labels: {', '.join(str(x) for x in labels)}\n"
        f"body:\n{redacted_body}"
    )
    return [
        {
            "evidence_id": f"ev-issue-{issue_number or 'na'}",
            "kind": "other",
            "source": {
                "system": "other",
                "ref": f"{owner}/{name}#issue/{issue_number or 'na'}",
            },
            "summary": (title or "GitHub issue")[:200],
            "content_excerpt": content[:4000],
            "redacted": True,
            "redaction_notes": notes or ["issue_body_bounded"],
            "provenance": {
                "collector": "issue_evidence",
                "query": f"issues/{issue_number}",
            },
            "labels": {
                "trigger_kind": str(trigger.get("kind") or "github_issue"),
                "delivery_mode": str(run.get("delivery_mode") or "issue_snippet"),
            },
            "collected_at": utc_now(),
        }
    ]
