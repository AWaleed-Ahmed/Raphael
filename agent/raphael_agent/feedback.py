"""Optional post-merge / human-feedback hook interface (FR-065 stub)."""

from __future__ import annotations

from typing import Any, Protocol


class FeedbackRecorder(Protocol):
    def record_pr_outcome(self, event: dict[str, Any]) -> None: ...


class NullFeedbackRecorder:
    """No-op recorder — Phase 4 stub; learning loop is out of scope."""

    def record_pr_outcome(self, event: dict[str, Any]) -> None:
        return None


def default_feedback_recorder() -> FeedbackRecorder:
    return NullFeedbackRecorder()
