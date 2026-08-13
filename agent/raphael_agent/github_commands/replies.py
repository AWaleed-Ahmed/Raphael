"""Markdown reply templates for GitHub-native commands (GH-M1–M3)."""

from __future__ import annotations

from typing import Any

from raphael_agent.publish.config import partner_mode, publish_mode
from raphael_agent.schema_util import REPO_ROOT

_STATUS_FALLBACK = """\
<!-- raphael:run_id={run_id} -->
### Raphael run `{run_id}`
- **Status:** {status}
- **Class:** {failure_class} (confidence {confidence})
- **Sandbox result:** `{result_id}`
- **Delivery:** {delivery}
- **Mode:** partner={partner_mode} publish={publish_mode}

Commands: `{prefix} feedback accepted` · `{prefix} feedback rejected` · `{prefix} retry` · `{prefix} help`
"""

_HELP_FALLBACK = """\
### Raphael commands
Prefix: `{prefix}`  ·  **Mode:** partner={partner_mode} publish={publish_mode}

**Implemented (GH-M1)** — write collaborators:
- `{prefix} status [run_id]` — run summary for this Issue/PR
- `{prefix} help` — this list (no secrets)
- `{prefix} feedback accepted|rejected|edited` — FR-065 feedback only (**never** merges)

**Implemented (GH-M2)** — admin or `RAPHAEL_GITHUB_COMMAND_TEAM`:
- `{prefix} retry [run_id]` — new run from the same fingerprint; sets `parent_run_id`
- `{prefix} escalate [run_id] [notes]` — in-flight → `escalated`/`human_requested`; terminal → notes only

**Deferred (not implemented — GH-M4)** — admin or team:
- `{prefix} cancel` / `{prefix} diagnose` / `{prefix} fix`
- Check Runs (`RAPHAEL_GITHUB_CHECK_RUNS`) — advisory, conclusion `neutral` when enabled later
"""

_NOT_FOUND = """\
### Raphael
No run found for this thread. Pass an explicit id (`{prefix} status run-…`) or wait for an ingest to finish.

**Mode:** partner={partner_mode} publish={publish_mode}
"""

_TERMINAL_DRAFT = """\
<!-- raphael:run_id={run_id} -->
### Raphael run `{run_id}` — draft ready for review
- **Status:** {status}
- **Class:** {failure_class} (confidence {confidence})
- **Sandbox result:** `{result_id}`
- **Delivery:** {delivery}
- **Mode:** partner={partner_mode} publish={publish_mode}

How to review: open the draft PR, confirm the allowlisted diff, and merge only after human review. Raphael never auto-merges.

Commands: `{prefix} feedback accepted` · `{prefix} feedback rejected` · `{prefix} retry` · `{prefix} help`
"""

_TERMINAL_FIX = """\
<!-- raphael:run_id={run_id} -->
### Raphael run `{run_id}` — fix snippet proposed
- **Status:** {status}
- **Class:** {failure_class} (confidence {confidence})
- **Sandbox result:** `{result_id}`
- **Delivery:** {delivery}
- **Mode:** partner={partner_mode} publish={publish_mode}

A constrained fix snippet is on this Issue. A human must open the PR — Raphael does not.

Commands: `{prefix} feedback accepted` · `{prefix} feedback rejected` · `{prefix} help`
"""

_TERMINAL_ESCALATED = """\
<!-- raphael:run_id={run_id} -->
### Raphael run `{run_id}` — escalated
- **Status:** {status}
- **Class:** {failure_class} (confidence {confidence})
- **Sandbox result:** `{result_id}`
- **Reason:** {terminal_reason}
- **Mode:** partner={partner_mode} publish={publish_mode}

{next_step}

Commands: `{prefix} retry` · `{prefix} status` · `{prefix} help`
"""

_TERMINAL_FAILED = """\
<!-- raphael:run_id={run_id} -->
### Raphael run `{run_id}` — failed closed
- **Status:** {status}
- **Class:** {failure_class} (confidence {confidence})
- **Sandbox result:** `{result_id}`
- **Reason:** {terminal_reason}
- **Mode:** partner={partner_mode} publish={publish_mode}

{next_step}

Commands: `{prefix} retry` · `{prefix} status` · `{prefix} help`
"""

_STICKY_FALLBACK = """\
<!-- raphael:sticky -->
<!-- raphael:run_id={run_id} -->
### Raphael actions
Latest run: `{run_id}` · **Status:** {status} · **Class:** {failure_class} (confidence {confidence})
Sandbox result: `{result_id}` · **Mode:** partner={partner_mode} publish={publish_mode}

Write collaborators:
- `{prefix} status`
- `{prefix} feedback accepted|rejected|edited`
- `{prefix} help`

Raphael never merges. There is no Merge action here.
"""

_TERMINAL_BY_STATUS = {
    "success_draft_pr_ready": ("terminal_draft_pr.md", _TERMINAL_DRAFT),
    "success_fix_proposed": ("terminal_fix_proposed.md", _TERMINAL_FIX),
    "escalated": ("terminal_escalated.md", _TERMINAL_ESCALATED),
    "failed_closed": ("terminal_failed.md", _TERMINAL_FAILED),
}


class _Fmt(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return ""


def _load(name: str, fallback: str) -> str:
    path = REPO_ROOT / "interface" / "github-native" / "templates" / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return fallback


def current_modes() -> tuple[str, str]:
    return partner_mode(), publish_mode()


def _delivery_line(run: dict[str, Any]) -> str:
    publish = run.get("publish") or {}
    url = run.get("pull_request_url") or publish.get("pull_request_url")
    if url:
        return f"draft PR → {url}"
    comment = run.get("issue_comment_url") or publish.get("issue_comment_url")
    if comment:
        return f"issue snippet → {comment}"
    return "_(none)_"


def run_summary_fields(run: dict[str, Any]) -> dict[str, str]:
    diagnosis = run.get("diagnosis") or {}
    classification = diagnosis.get("classification") or {}
    failure_class = classification.get("failure_class") or "_(unknown)_"
    confidence = diagnosis.get("confidence")
    if isinstance(confidence, float):
        confidence_s = f"{confidence:.2f}"
    elif confidence is None:
        confidence_s = "n/a"
    else:
        confidence_s = str(confidence)
    result_id = (
        run.get("result_id") or (run.get("publish") or {}).get("result_id") or "_(none)_"
    )
    partner, publish = current_modes()
    report = run.get("escalation_report") or {}
    next_step = (
        report.get("why_no_fix")
        or report.get("summary")
        or "Inspect audit_events and decide retry vs human patch."
    )
    return {
        "run_id": str(run.get("run_id") or "unknown"),
        "status": str(run.get("status") or "unknown"),
        "failure_class": str(failure_class),
        "confidence": confidence_s,
        "result_id": str(result_id),
        "delivery": _delivery_line(run),
        "partner_mode": partner,
        "publish_mode": publish,
        "terminal_reason": str(run.get("terminal_reason") or "_(none)_"),
        "next_step": str(next_step),
        "parent_run_id": str(run.get("parent_run_id") or ""),
    }


def render_status(run: dict[str, Any], *, prefix: str) -> str:
    fields = run_summary_fields(run)
    fields["prefix"] = prefix
    return _load("status.md", _STATUS_FALLBACK).format_map(_Fmt(fields)).strip() + "\n"


def render_terminal(run: dict[str, Any], *, prefix: str) -> str | None:
    status = str(run.get("status") or "")
    spec = _TERMINAL_BY_STATUS.get(status)
    if spec is None:
        return None
    name, fallback = spec
    fields = run_summary_fields(run)
    fields["prefix"] = prefix
    return _load(name, fallback).format_map(_Fmt(fields)).strip() + "\n"


def render_sticky(run: dict[str, Any], *, prefix: str) -> str:
    fields = run_summary_fields(run)
    fields["prefix"] = prefix
    return _load("sticky.md", _STICKY_FALLBACK).format_map(_Fmt(fields)).strip() + "\n"


def render_help(*, prefix: str) -> str:
    partner, publish = current_modes()
    return _load("help.md", _HELP_FALLBACK).format_map(
        _Fmt(prefix=prefix, partner_mode=partner, publish_mode=publish)
    ).strip() + "\n"


def render_run_not_found(*, prefix: str) -> str:
    partner, publish = current_modes()
    return _NOT_FOUND.format_map(
        _Fmt(prefix=prefix, partner_mode=partner, publish_mode=publish)
    ).strip() + "\n"


def render_feedback_ack(*, outcome: str, event_id: str, prefix: str) -> str:
    partner, publish = current_modes()
    return (
        f"Recorded feedback **{outcome}** (`{event_id}`). "
        "This does not merge or approve the PR.\n\n"
        f"**Mode:** partner={partner} publish={publish}\n\n"
        f"Commands: `{prefix} status` · `{prefix} help`\n"
    )


def render_retry_ack(
    *,
    child_run_id: str,
    parent_run_id: str,
    child_status: str,
    prefix: str,
) -> str:
    partner, publish = current_modes()
    return (
        f"Retry enqueued as `{child_run_id}` (status `{child_status}`), "
        f"parent `{parent_run_id}`.\n\n"
        f"<!-- raphael:run_id={child_run_id} -->\n"
        f"**Mode:** partner={partner} publish={publish}\n\n"
        f"Commands: `{prefix} status {child_run_id}` · `{prefix} help`\n"
    )


def render_retry_in_flight(*, run_id: str, status: str, prefix: str) -> str:
    return (
        f"A retry is not needed yet — run `{run_id}` is still `{status}` "
        f"(pending/running). Wait for it to finish, or `{prefix} escalate`.\n"
    )


def render_escalate_in_flight(*, run_id: str, prefix: str) -> str:
    partner, publish = current_modes()
    return (
        f"Run `{run_id}` marked **escalated** (`terminal_reason=human_requested`). "
        "Patch/publish will not continue. No patch was invented.\n\n"
        f"<!-- raphael:run_id={run_id} -->\n"
        f"**Mode:** partner={partner} publish={publish}\n\n"
        f"Commands: `{prefix} status` · `{prefix} retry` · `{prefix} help`\n"
    )


def render_escalate_terminal(*, run_id: str, status: str, prefix: str) -> str:
    partner, publish = current_modes()
    return (
        f"Recorded escalate note on terminal run `{run_id}` "
        f"(status remains `{status}`). Did not rewrite a completed success to escalated.\n\n"
        f"<!-- raphael:run_id={run_id} -->\n"
        f"**Mode:** partner={partner} publish={publish}\n"
    )


def render_denied(*, verb: str, prefix: str) -> str:
    return (
        f"`{prefix} {verb}` is not allowed for this actor. "
        "Write collaborators may run `status`, `help`, and `feedback`. "
        "Other verbs require repo admin or `RAPHAEL_GITHUB_COMMAND_TEAM` membership.\n"
    )


def render_deferred(*, verb: str, prefix: str) -> str:
    return (
        f"`{prefix} {verb}` is **not implemented** yet (GH-M4). "
        "GH-M1/M2 support `status`/`help`/`feedback`/`retry`/`escalate`. "
        "Cancel, diagnose, fix, and Check Runs are deferred.\n"
    )


def render_parse_error(*, error: str, prefix: str) -> str:
    if error == "feedback_missing_outcome":
        return f"Usage: `{prefix} feedback accepted|rejected|edited` (not `{prefix} accept`).\n"
    if error == "feedback_invalid_outcome":
        return f"Feedback outcome must be `accepted`, `rejected`, or `edited`.\n"
    if error == "unknown_verb":
        return f"Unknown command. Try `{prefix} help`.\n"
    if error == "missing_verb":
        return f"Usage: `{prefix} <verb> [args]`. Try `{prefix} help`.\n"
    return f"Could not parse command. Try `{prefix} help`.\n"


def render_rate_limited(*, prefix: str) -> str:
    return (
        f"Rate limit exceeded for GitHub commands (default 10/hour per repo+actor). "
        f"Try `{prefix} status` later.\n"
    )
