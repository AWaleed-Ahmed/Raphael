"""Handle GitHub ``issue_comment`` webhooks for GH-M1 commands.

Does not call the sandbox HTTP API. Does not change partner/publish gates.
``retry`` / ``escalate`` / ``diagnose`` / ``fix`` / Check Runs are deferred.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.feedback import default_feedback_recorder, normalize_feedback_event
from raphael_agent.github_commands.acl import acl_allows
from raphael_agent.github_commands.config import (
    bot_logins,
    command_prefix,
    command_rate_limit,
    command_team_logins,
)
from raphael_agent.github_commands.idempotency import CommandIdempotencyStore
from raphael_agent.github_commands.parse import DEFERRED_VERBS, ParsedCommand, parse_command
from raphael_agent.github_commands.rate_limit import CommandRateLimiter
from raphael_agent.github_commands.replies import (
    render_deferred,
    render_denied,
    render_feedback_ack,
    render_help,
    render_parse_error,
    render_rate_limited,
    render_run_not_found,
    render_status,
)
from raphael_agent.graph.state import append_audit
from raphael_agent.runs import find_latest_run_for_github_number
from raphael_agent.store import RunStore
from raphael_agent.timeutil import utc_now

CommentPoster = Callable[[str, str, int, str], dict[str, Any] | None]

_HTML_MARKER = re.compile(r"<!--\s*raphael:run_id=([^\s]+?)\s*-->", re.IGNORECASE)
_FOOTER_MARKER = re.compile(r"raphael:run_id=([A-Za-z0-9._:-]+)")


def extract_run_id_markers(*texts: str | None) -> str | None:
    """Last ``raphael:run_id`` marker across issue/comment bodies (HTML then footer)."""
    found: str | None = None
    for text in texts:
        if not text:
            continue
        for match in _HTML_MARKER.finditer(text):
            found = match.group(1)
        for match in _FOOTER_MARKER.finditer(text):
            found = match.group(1)
    return found


def _login(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("login") or "").strip()
    return ""


def _is_self_comment(comment: dict[str, Any], sender: dict[str, Any]) -> bool:
    logins = bot_logins()
    for user in (comment.get("user"), sender):
        login = _login(user).lower()
        if login and login in logins:
            return True
        user_type = (user or {}).get("type") if isinstance(user, dict) else None
        if str(user_type or "").lower() == "bot" and login and "raphael" in login:
            return True
    return False


def _repo(payload: dict[str, Any]) -> tuple[str, str]:
    repo = payload.get("repository") or {}
    owner_obj = repo.get("owner") or {}
    owner = owner_obj.get("login") or owner_obj.get("name") or ""
    return str(owner), str(repo.get("name") or "")


def _redact(text: str) -> str:
    cleaned, _notes = redact_text(text)
    return cleaned


def _post_comment(
    *,
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
    poster: CommentPoster | None,
) -> dict[str, Any] | None:
    if poster is not None:
        return poster(owner, repo, issue_number, body)
    from raphael_agent.publish.config import github_token

    if not github_token():
        return None
    try:
        from raphael_agent.publish.github_client import GitHubPublisher

        return GitHubPublisher().create_issue_comment(
            owner, repo, issue_number=issue_number, body=body
        )
    except Exception:  # noqa: BLE001 — webhook must not 5xx on comment post
        return None


def resolve_run(
    store: RunStore,
    *,
    parsed: ParsedCommand,
    owner: str,
    repo: str,
    issue_number: int | None,
    issue_body: str | None,
    comment_body: str | None,
) -> dict[str, Any] | None:
    """Explicit arg → thread marker → store lookup by Issue/PR number."""
    if parsed.verb == "status" and parsed.args:
        explicit = parsed.args[0]
        found = store.get_run(explicit)
        if found is not None:
            return found
        return {"run_id": explicit, "_missing": True}

    marker = extract_run_id_markers(issue_body, comment_body)
    if marker:
        found = store.get_run(marker)
        if found is not None:
            return found

    if issue_number is None:
        return None
    return find_latest_run_for_github_number(
        store, owner=owner, repo=repo, number=int(issue_number)
    )


def _audit_command(store: RunStore, run: dict[str, Any] | None, detail: str) -> None:
    if run is None or run.get("_missing") or not run.get("run_id"):
        return
    latest = store.get_run(str(run["run_id"])) or run
    latest["audit_events"] = append_audit(latest, "github_command", "invoke", detail)
    latest["updated_at"] = utc_now()
    store.save_run(latest)


def handle_issue_comment_event(
    payload: dict[str, Any],
    *,
    delivery_id: str | None,
    store: RunStore,
    poster: CommentPoster | None = None,
    rate_limiter: CommandRateLimiter | None = None,
    idempotency: CommandIdempotencyStore | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Process an authenticated ``issue_comment`` payload. Never raises to HTTP 500."""
    action = str(payload.get("action") or "").lower()
    if action and action != "created":
        return {
            "decision": "ignored",
            "reason": f"issue_comment action={action} (only created is handled)",
        }

    comment = payload.get("comment") if isinstance(payload.get("comment"), dict) else {}
    issue = payload.get("issue") if isinstance(payload.get("issue"), dict) else {}
    sender = payload.get("sender") if isinstance(payload.get("sender"), dict) else {}
    owner, repo = _repo(payload)
    comment_id = str(comment.get("id") or "") or None
    actor = _login(comment.get("user") or {}) or _login(sender)

    if _is_self_comment(comment, sender):
        return {"decision": "ignored", "reason": "bot self-comment"}

    prefix = prefix if prefix is not None else command_prefix()
    parsed = parse_command(str(comment.get("body") or ""), prefix=prefix)
    if parsed is None:
        return {"decision": "ignored", "reason": "not a raphael command"}

    idemp = idempotency or CommandIdempotencyStore(
        store.root / "github_command_idempotency.json"
    )
    prior = idemp.get(comment_id=comment_id, delivery_id=delivery_id)
    if prior is not None:
        replay = dict(prior)
        replay["idempotent_replay"] = True
        replay["decision"] = prior.get("decision") or "idempotent_replay"
        return replay

    limiter = rate_limiter or CommandRateLimiter(
        store.root / "github_command_rate.json",
        limit=command_rate_limit(),
    )
    allowed, remaining = limiter.allow(owner or "_", repo or "_", actor or "_anonymous")
    if not allowed:
        reply = _redact(render_rate_limited(prefix=prefix))
        result = {
            "decision": "rate_limited",
            "reason": "GH-053 rate limit (repo+actor)",
            "verb": parsed.verb,
            "reply": reply,
            "comment_posted": False,
            "rate_limit_remaining": remaining,
            "idempotent_replay": False,
        }
        posted = _maybe_post(owner, repo, issue, reply, poster)
        result["comment_posted"] = posted
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    association = str(comment.get("author_association") or "")
    permission = None
    user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
    perms = user.get("permissions") if isinstance(user.get("permissions"), dict) else None
    if isinstance(perms, dict):
        # GitHub collaborator permission objects use boolean flags or a "role" string.
        permission = str(perms.get("role") or perms.get("permission") or "") or None
        if perms.get("admin") is True:
            permission = "admin"
        elif perms.get("push") is True or perms.get("write") is True:
            permission = permission or "write"
    test_perm = payload.get("_raphael_permission")
    if isinstance(test_perm, str) and test_perm:
        permission = test_perm

    if parsed.verb and not acl_allows(
        parsed.verb,
        association=association,
        login=actor,
        permission=permission,
        team_logins=command_team_logins(),
    ):
        reply = _redact(render_denied(verb=parsed.verb or "command", prefix=prefix))
        result = {
            "decision": "denied",
            "reason": "acl_denied",
            "verb": parsed.verb,
            "reply": reply,
            "comment_posted": False,
            "idempotent_replay": False,
        }
        result["comment_posted"] = _maybe_post(owner, repo, issue, reply, poster)
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    if parsed.error:
        reply = _redact(render_parse_error(error=parsed.error, prefix=prefix))
        result = {
            "decision": "invalid",
            "reason": parsed.error,
            "verb": parsed.verb,
            "reply": reply,
            "comment_posted": False,
            "idempotent_replay": False,
        }
        result["comment_posted"] = _maybe_post(owner, repo, issue, reply, poster)
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    if parsed.verb in DEFERRED_VERBS:
        reply = _redact(render_deferred(verb=parsed.verb, prefix=prefix))
        result = {
            "decision": "deferred",
            "reason": "GH-M2+ not implemented",
            "verb": parsed.verb,
            "reply": reply,
            "comment_posted": False,
            "idempotent_replay": False,
        }
        result["comment_posted"] = _maybe_post(owner, repo, issue, reply, poster)
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    issue_number = issue.get("number")
    try:
        issue_n = int(issue_number) if issue_number is not None else None
    except (TypeError, ValueError):
        issue_n = None
    is_pr = bool(issue.get("pull_request"))
    run = resolve_run(
        store,
        parsed=parsed,
        owner=owner,
        repo=repo,
        issue_number=issue_n,
        issue_body=str(issue.get("body") or "") or None,
        comment_body=str(comment.get("body") or "") or None,
    )

    if parsed.verb == "help":
        reply = _redact(render_help(prefix=prefix))
        result = {
            "decision": "replied",
            "reason": "help",
            "verb": "help",
            "reply": reply,
            "comment_posted": False,
            "idempotent_replay": False,
        }
        result["comment_posted"] = _maybe_post(owner, repo, issue, reply, poster)
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    if parsed.verb == "status":
        if run is None or run.get("_missing"):
            reply = _redact(render_run_not_found(prefix=prefix))
            result = {
                "decision": "replied",
                "reason": "run_not_found",
                "verb": "status",
                "reply": reply,
                "run_id": (run or {}).get("run_id"),
                "comment_posted": False,
                "idempotent_replay": False,
            }
        else:
            reply = _redact(render_status(run, prefix=prefix))
            _audit_command(store, run, f"status actor={actor}")
            result = {
                "decision": "replied",
                "reason": "status",
                "verb": "status",
                "reply": reply,
                "run_id": run.get("run_id"),
                "comment_posted": False,
                "idempotent_replay": False,
            }
        result["comment_posted"] = _maybe_post(owner, repo, issue, reply, poster)
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    if parsed.verb == "feedback":
        outcome = parsed.outcome or "other"
        extra_notes = " ".join(parsed.args[1:]).strip() if parsed.args else ""
        notes = f"github issue_comment /raphael feedback {outcome}"
        if issue_n is not None:
            notes += f" #{issue_n}"
        if extra_notes:
            notes += f" {extra_notes}"
        html_url = None
        if is_pr:
            pr = issue.get("pull_request") or {}
            html_url = pr.get("html_url") or issue.get("html_url")
        event = normalize_feedback_event(
            {
                "event_id": f"gh-cmd-{comment_id or delivery_id or 'unknown'}-feedback",
                "outcome": outcome,
                "source": "github_webhook",
                "run_id": None if run is None or run.get("_missing") else run.get("run_id"),
                "result_id": None
                if run is None or run.get("_missing")
                else (run.get("result_id") or (run.get("publish") or {}).get("result_id")),
                "pull_request_url": html_url,
                "pull_request_number": issue_n if is_pr else None,
                "repository": {"owner": owner, "name": repo} if owner and repo else None,
                "failure_class": None
                if run is None or run.get("_missing")
                else ((run.get("diagnosis") or {}).get("classification") or {}).get(
                    "failure_class"
                ),
                "actor": actor or None,
                "notes": notes,
                "raw_ref": f"github:issue_comment:{delivery_id or comment_id}",
            }
        )
        recorded = default_feedback_recorder().record(event)
        if run is not None and not run.get("_missing"):
            _audit_command(store, run, f"feedback {outcome} actor={actor}")
        reply = _redact(
            render_feedback_ack(
                outcome=outcome, event_id=str(recorded["event_id"]), prefix=prefix
            )
        )
        result = {
            "decision": "replied",
            "reason": "feedback",
            "verb": "feedback",
            "outcome": outcome,
            "reply": reply,
            "run_id": recorded.get("run_id"),
            "feedback_event_id": recorded["event_id"],
            "comment_posted": False,
            "idempotent_replay": False,
        }
        result["comment_posted"] = _maybe_post(owner, repo, issue, reply, poster)
        idemp.put(result, comment_id=comment_id, delivery_id=delivery_id)
        return result

    return {"decision": "ignored", "reason": "unhandled verb", "verb": parsed.verb}


def _maybe_post(
    owner: str,
    repo: str,
    issue: dict[str, Any],
    reply: str,
    poster: CommentPoster | None,
) -> bool:
    number = issue.get("number")
    if not owner or not repo or number is None:
        return False
    try:
        issue_number = int(number)
    except (TypeError, ValueError):
        return False
    posted = _post_comment(
        owner=owner,
        repo=repo,
        issue_number=issue_number,
        body=reply,
        poster=poster,
    )
    return posted is not None
