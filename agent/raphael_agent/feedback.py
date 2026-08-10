"""Optional post-merge / human-feedback recording (FR-065 — lightweight audit)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Protocol

from raphael_agent.schema_util import validate_agent
from raphael_agent.timeutil import utc_now


ALLOWED_OUTCOMES = frozenset(
    {
        "draft_opened",
        "dry_run_prepared",
        "fix_snippet_posted",
        "fix_snippet_prepared",
        "accepted",
        "edited",
        "rejected",
        "merged",
        "closed_unmerged",
        "deploy_succeeded",
        "deploy_failed",
        "other",
    }
)


class FeedbackRecorder(Protocol):
    def record(self, event: dict[str, Any]) -> dict[str, Any]: ...


class NullFeedbackRecorder:
    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        return normalize_feedback_event(event)

    # Back-compat
    def record_pr_outcome(self, event: dict[str, Any]) -> None:
        self.record(event)


class JsonlFeedbackRecorder:
    """Append validated feedback events under RAPHAEL_AGENT_DATA_DIR/feedback.jsonl."""

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self.path = path
        else:
            root = Path(os.environ.get("RAPHAEL_AGENT_DATA_DIR") or ".raphael-agent-data")
            self.path = root / "feedback.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        row = normalize_feedback_event(event)
        validate_agent("feedback_event.json", _for_schema(row))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")
        return row

    def record_pr_outcome(self, event: dict[str, Any]) -> None:
        self.record(event)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows


def _for_schema(event: dict[str, Any]) -> dict[str, Any]:
    skip_if_none = {
        "run_id",
        "result_id",
        "pull_request_url",
        "pull_request_number",
        "repository",
        "failure_class",
        "actor",
        "notes",
        "raw_ref",
    }
    out: dict[str, Any] = {}
    for key, value in event.items():
        if key in skip_if_none and value is None:
            continue
        out[key] = value
    repo = out.get("repository")
    if isinstance(repo, dict):
        cleaned = {k: v for k, v in repo.items() if v is not None}
        if cleaned:
            out["repository"] = cleaned
        else:
            out.pop("repository", None)
    return out


def normalize_feedback_event(event: dict[str, Any]) -> dict[str, Any]:
    outcome = str(event.get("outcome") or "other")
    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError(f"unsupported feedback outcome: {outcome}")
    row: dict[str, Any] = {
        "event_id": str(event.get("event_id") or f"fb-{uuid.uuid4().hex[:12]}"),
        "outcome": outcome,
        "recorded_at": event.get("recorded_at") or utc_now(),
        "source": str(event.get("source") or "manual"),
        "run_id": event.get("run_id"),
        "result_id": event.get("result_id"),
        "pull_request_url": event.get("pull_request_url"),
        "pull_request_number": event.get("pull_request_number"),
        "repository": event.get("repository"),
        "failure_class": event.get("failure_class"),
        "actor": event.get("actor"),
        "notes": event.get("notes"),
        "raw_ref": event.get("raw_ref"),
    }
    return row


def feedback_from_run(
    run: dict[str, Any],
    *,
    outcome: str,
    source: str = "publish",
    notes: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    diagnosis = run.get("diagnosis") or {}
    classification = diagnosis.get("classification") or {}
    publish = run.get("publish") or {}
    return normalize_feedback_event(
        {
            "outcome": outcome,
            "source": source,
            "run_id": run.get("run_id"),
            "result_id": run.get("result_id") or publish.get("result_id"),
            "pull_request_url": run.get("pull_request_url") or publish.get("pull_request_url"),
            "pull_request_number": publish.get("pull_request_number"),
            "repository": run.get("repository"),
            "failure_class": classification.get("failure_class"),
            "notes": notes,
            "actor": actor,
        }
    )


def feedback_from_pull_request_webhook(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Map GitHub pull_request events to feedback outcomes (accept/reject/merge)."""
    action = (payload.get("action") or "").lower()
    pr = payload.get("pull_request") or {}
    if not pr:
        return None
    repo = payload.get("repository") or {}
    owner_obj = repo.get("owner") or {}
    owner = owner_obj.get("login") if isinstance(owner_obj, dict) else owner_obj
    repository = None
    if owner and repo.get("name"):
        repository = {"owner": str(owner), "name": str(repo["name"])}

    merged = bool(pr.get("merged"))
    outcome: str | None = None
    if action == "closed":
        outcome = "merged" if merged else "closed_unmerged"
    elif action in {"synchronize", "edited"}:
        outcome = "edited"
    elif action == "review_requested":
        outcome = "other"
    else:
        return None

    actor_obj = payload.get("sender") or {}
    actor = actor_obj.get("login") if isinstance(actor_obj, dict) else None
    return normalize_feedback_event(
        {
            "event_id": f"gh-pr-{pr.get('id') or pr.get('number')}-{action}",
            "outcome": outcome,
            "source": "github_webhook",
            "pull_request_url": pr.get("html_url"),
            "pull_request_number": pr.get("number"),
            "repository": repository,
            "actor": actor,
            "notes": f"github pull_request action={action} merged={merged}",
        }
    )


def default_feedback_recorder() -> FeedbackRecorder:
    mode = os.environ.get("RAPHAEL_FEEDBACK_RECORDER", "jsonl").strip().lower()
    if mode in {"off", "null", "none"}:
        return NullFeedbackRecorder()
    return JsonlFeedbackRecorder()


def feedback_on_publish_enabled() -> bool:
    return os.environ.get("RAPHAEL_FEEDBACK_ON_PUBLISH", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
