"""Terminal GitHub surfaces (comments, labels, sticky footer). No sandbox HTTP."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.github_commands.config import (
    command_prefix,
    github_auto_comments_enabled,
)
from raphael_agent.github_commands.labels import Labeler, apply_terminal_labels
from raphael_agent.github_commands.replies import render_terminal
from raphael_agent.github_commands.sticky import (
    CommentLister,
    CommentUpdater,
    upsert_sticky_footer,
)
from raphael_agent.graph.state import append_audit
from raphael_agent.store import RunStore
from raphael_agent.timeutil import utc_now

CommentPoster = Callable[[str, str, int, str], dict[str, Any] | None]

TERMINAL_AUTO_STATUSES = frozenset(
    {
        "success_draft_pr_ready",
        "success_fix_proposed",
        "escalated",
        "failed_closed",
    }
)

_LOCK = threading.Lock()


def _sidecar_path(store: RunStore):
    return store.root / "github_terminal_comments.json"


def _already_emitted(store: RunStore, run_id: str, status: str) -> bool:
    path = _sidecar_path(store)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    row = data.get(run_id) if isinstance(data, dict) else None
    return isinstance(row, dict) and row.get("status") == status


def _mark_emitted(store: RunStore, run_id: str, status: str, *, posted: bool) -> None:
    path = _sidecar_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        data: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        data[run_id] = {"status": status, "at": utc_now(), "posted": posted}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _comment_target(run: dict[str, Any]) -> tuple[str, str, int] | None:
    repo = run.get("repository") or {}
    owner = str(repo.get("owner") or "")
    name = str(repo.get("name") or "")
    publish = run.get("publish") or {}
    number = (
        run.get("pull_request_number")
        or publish.get("pull_request_number")
        or run.get("issue_number")
    )
    if not owner or not name or number is None:
        return None
    try:
        return owner, name, int(number)
    except (TypeError, ValueError):
        return None


def _post(
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    poster: CommentPoster | None,
) -> bool:
    if poster is not None:
        return poster(owner, repo, issue_number, body) is not None
    from raphael_agent.publish.config import github_token

    if not github_token():
        return False
    try:
        from raphael_agent.publish.github_client import GitHubPublisher

        GitHubPublisher().create_issue_comment(
            owner, repo, issue_number=issue_number, body=body
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def maybe_on_terminal(
    run: dict[str, Any],
    *,
    store: RunStore | None = None,
    poster: CommentPoster | None = None,
    labeler: Labeler | None = None,
    comment_lister: CommentLister | None = None,
    comment_updater: CommentUpdater | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """GH-M2/M3 terminal hook: labels + sticky footer + one-shot comment.

    Gated by ``RAPHAEL_GITHUB_AUTO_COMMENTS`` (unset inherits commands).
    Never raises. Never calls sandbox HTTP.
    """
    if not github_auto_comments_enabled():
        return {
            "decision": "skipped",
            "reason": "auto_comments_disabled",
            "labels": [],
        }
    status = str(run.get("status") or "")
    if status not in TERMINAL_AUTO_STATUSES:
        return {"decision": "skipped", "reason": f"status={status}", "labels": []}

    prefix = prefix if prefix is not None else command_prefix()
    target = _comment_target(run)
    labels = apply_terminal_labels(run, target=target, labeler=labeler)
    sticky = upsert_sticky_footer(
        run,
        target=target,
        prefix=prefix,
        lister=comment_lister,
        poster=poster,
        updater=comment_updater,
    )
    comment = maybe_emit_terminal_comment(
        run, store=store, poster=poster, prefix=prefix
    )
    return {
        "decision": "emitted",
        "status": status,
        "labels": labels,
        "sticky": sticky,
        "comment": comment,
    }


def maybe_emit_terminal_comment(
    run: dict[str, Any],
    *,
    store: RunStore | None = None,
    poster: CommentPoster | None = None,
    prefix: str | None = None,
) -> dict[str, Any] | None:
    """Render (and optionally post) a terminal GitHub comment. Never raises."""
    if not github_auto_comments_enabled():
        return {"decision": "skipped", "reason": "auto_comments_disabled"}
    status = str(run.get("status") or "")
    if status not in TERMINAL_AUTO_STATUSES:
        return {"decision": "skipped", "reason": f"status={status}"}
    run_id = str(run.get("run_id") or "")
    if not run_id:
        return {"decision": "skipped", "reason": "missing_run_id"}

    store = store or RunStore()
    if _already_emitted(store, run_id, status):
        return {"decision": "idempotent", "run_id": run_id, "status": status}

    prefix = prefix if prefix is not None else command_prefix()
    markdown = render_terminal(run, prefix=prefix)
    if not markdown:
        return {"decision": "skipped", "reason": "no_template"}
    reply, _notes = redact_text(markdown)

    target = _comment_target(run)
    posted = False
    if target is not None:
        owner, name, number = target
        posted = _post(owner, name, number, reply, poster)

    _mark_emitted(store, run_id, status, posted=posted)
    latest = store.get_run(run_id)
    if latest is not None:
        latest["audit_events"] = append_audit(
            latest, "github_command", "terminal_comment", status
        )
        latest["updated_at"] = utc_now()
        try:
            store.save_run(latest)
        except Exception:  # noqa: BLE001
            pass

    return {
        "decision": "emitted",
        "run_id": run_id,
        "status": status,
        "reply": reply,
        "comment_posted": posted,
    }
