"""Optional post-merge / human-feedback recording (FR-065 — lightweight)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol

from raphael_agent.timeutil import utc_now


class FeedbackRecorder(Protocol):
    def record_pr_outcome(self, event: dict[str, Any]) -> None: ...


class NullFeedbackRecorder:
    """No-op recorder."""

    def record_pr_outcome(self, event: dict[str, Any]) -> None:
        return None


class JsonlFeedbackRecorder:
    """Append PR outcome events under RAPHAEL_AGENT_DATA_DIR/feedback.jsonl."""

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self.path = path
        else:
            root = Path(os.environ.get("RAPHAEL_AGENT_DATA_DIR") or ".raphael-agent-data")
            self.path = root / "feedback.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_pr_outcome(self, event: dict[str, Any]) -> None:
        row = dict(event)
        row.setdefault("recorded_at", utc_now())
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, default=str) + "\n")


def default_feedback_recorder() -> FeedbackRecorder:
    mode = os.environ.get("RAPHAEL_FEEDBACK_RECORDER", "jsonl").strip().lower()
    if mode in {"off", "null", "none"}:
        return NullFeedbackRecorder()
    return JsonlFeedbackRecorder()
