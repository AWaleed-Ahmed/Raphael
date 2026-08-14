"""GH-041 sticky Raphael actions footer. Create or PATCH one marked comment."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.github_commands.config import command_prefix
from raphael_agent.github_commands.replies import render_sticky

STICKY_MARKER = "<!-- raphael:sticky -->"

CommentLister = Callable[[str, str, int], list[dict[str, Any]]]
CommentPoster = Callable[[str, str, int, str], dict[str, Any] | None]
CommentUpdater = Callable[[str, str, int, str], dict[str, Any] | None]


def find_sticky_comment(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for comment in comments:
        body = str(comment.get("body") or "")
        if STICKY_MARKER in body:
            return comment
    return None


def upsert_sticky_footer(
    run: dict[str, Any],
    *,
    target: tuple[str, str, int] | None,
    prefix: str | None = None,
    lister: CommentLister | None = None,
    poster: CommentPoster | None = None,
    updater: CommentUpdater | None = None,
) -> dict[str, Any]:
    """Post or refresh the single sticky footer. Never offers Merge (GH-044)."""
    prefix = prefix if prefix is not None else command_prefix()
    markdown = render_sticky(run, prefix=prefix)
    reply, _notes = redact_text(markdown)
    if target is None:
        return {
            "decision": "skipped",
            "reason": "no_github_target",
            "reply": reply,
            "action": "none",
        }

    owner, repo, number = target
    comments: list[dict[str, Any]] = []
    listed = False
    if lister is not None:
        try:
            comments = list(lister(owner, repo, number) or [])
            listed = True
        except Exception:  # noqa: BLE001
            listed = False
    else:
        publisher = _publisher_or_none()
        if publisher is not None:
            try:
                comments = publisher.list_issue_comments(
                    owner, repo, issue_number=number
                )
                listed = True
            except Exception:  # noqa: BLE001
                listed = False

    existing = find_sticky_comment(comments) if listed else None
    if existing is not None:
        comment_id = existing.get("id")
        try:
            comment_id_i = int(comment_id)
        except (TypeError, ValueError):
            comment_id_i = None
        posted = False
        if comment_id_i is not None:
            posted = _update(
                owner, repo, comment_id_i, reply, updater=updater
            )
        return {
            "decision": "updated" if posted else "rendered",
            "reply": reply,
            "action": "update",
            "comment_id": comment_id,
            "posted": posted,
        }

    if not listed:
        return {
            "decision": "skipped",
            "reason": "cannot_list_comments",
            "reply": reply,
            "action": "none",
        }

    created = _create(owner, repo, number, reply, poster=poster)
    return {
        "decision": "created" if created else "rendered",
        "reply": reply,
        "action": "create",
        "posted": created is not None,
        "comment": created,
    }


def _publisher_or_none():
    from raphael_agent.publish.config import github_token

    if not github_token():
        return None
    try:
        from raphael_agent.publish.github_client import GitHubPublisher

        return GitHubPublisher()
    except Exception:  # noqa: BLE001
        return None


def _create(
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    *,
    poster: CommentPoster | None,
) -> dict[str, Any] | None:
    if poster is not None:
        return poster(owner, repo, issue_number, body)
    publisher = _publisher_or_none()
    if publisher is None:
        return None
    try:
        return publisher.create_issue_comment(
            owner, repo, issue_number=issue_number, body=body
        )
    except Exception:  # noqa: BLE001
        return None


def _update(
    owner: str,
    repo: str,
    comment_id: int,
    body: str,
    *,
    updater: CommentUpdater | None,
) -> bool:
    if updater is not None:
        return updater(owner, repo, comment_id, body) is not None
    publisher = _publisher_or_none()
    if publisher is None:
        return False
    try:
        publisher.update_issue_comment(
            owner, repo, comment_id=comment_id, body=body
        )
        return True
    except Exception:  # noqa: BLE001
        return False
