"""GH-021 terminal labels. Additive only — never strips ``raphael:fix`` (GH-023)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

LABEL_DRAFT = "raphael:draft"
LABEL_ESCALATED = "raphael:escalated"
LABEL_NEEDS_HUMAN = "raphael:needs-human"
LABEL_FIX = "raphael:fix"  # Route B trigger; never removed here (GH-023).
LABEL_LEARNING_DEMOTED = "raphael:learning-demoted"  # GH-022 P2 — not applied.

Labeler = Callable[[str, str, int, list[str]], Any]


def human_has_next_step(status: str, run: dict[str, Any] | None = None) -> bool:
    """True when a human still has a GitHub-side next action.

    Draft-ready review is signaled by ``raphael:draft``, not ``needs-human``.
    ``success_fix_proposed`` needs a human to apply/open the snippet.
    ``escalated`` is a human takeover. ``failed_closed`` still needs inspect/retry.
    """
    _ = run
    if status == "success_fix_proposed":
        return True
    if status == "escalated":
        return True
    if status == "failed_closed":
        return True
    return False


def labels_for_terminal_status(
    status: str, run: dict[str, Any] | None = None
) -> list[str]:
    if status == "success_draft_pr_ready":
        return [LABEL_DRAFT]
    if status == "success_fix_proposed":
        return [LABEL_NEEDS_HUMAN]
    if status in {"escalated", "failed_closed"}:
        labels = [LABEL_ESCALATED]
        if human_has_next_step(status, run):
            labels.append(LABEL_NEEDS_HUMAN)
        return labels
    return []


def apply_terminal_labels(
    run: dict[str, Any],
    *,
    target: tuple[str, str, int] | None,
    labeler: Labeler | None = None,
) -> dict[str, Any]:
    """POST mapped labels. Never DELETE. Never includes or strips ``raphael:fix``."""
    status = str(run.get("status") or "")
    wanted = labels_for_terminal_status(status, run)
    wanted = [name for name in wanted if name != LABEL_FIX]
    if not wanted:
        return {"decision": "skipped", "reason": f"status={status}", "labels": []}
    if target is None:
        return {"decision": "skipped", "reason": "no_github_target", "labels": wanted}

    owner, repo, number = target
    posted = False
    if labeler is not None:
        labeler(owner, repo, number, wanted)
        posted = True
    else:
        from raphael_agent.publish.config import github_token

        if github_token():
            try:
                from raphael_agent.publish.github_client import GitHubPublisher

                GitHubPublisher().add_issue_labels(
                    owner, repo, issue_number=number, labels=wanted
                )
                posted = True
            except Exception:  # noqa: BLE001
                posted = False

    return {
        "decision": "applied" if posted else "rendered",
        "labels": wanted,
        "posted": posted,
        "removed": [],
    }
