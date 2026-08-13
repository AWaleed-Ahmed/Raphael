"""Markdown reply templates for GitHub-native commands (GH-M1)."""

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

**Deferred (not implemented — GH-M2+)** — admin or `RAPHAEL_GITHUB_COMMAND_TEAM`:
- `{prefix} retry` / `{prefix} escalate` / `{prefix} cancel`
- `{prefix} diagnose` / `{prefix} fix`
- Check Runs (`RAPHAEL_GITHUB_CHECK_RUNS`) — advisory, conclusion `neutral` when enabled later
"""

_NOT_FOUND = """\
### Raphael
No run found for this thread. Pass an explicit id (`{prefix} status run-…`) or wait for an ingest to finish.

**Mode:** partner={partner_mode} publish={publish_mode}
"""


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


def render_status(run: dict[str, Any], *, prefix: str) -> str:
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
    result_id = run.get("result_id") or (run.get("publish") or {}).get("result_id") or "_(none)_"
    partner, publish = current_modes()
    return _load("status.md", _STATUS_FALLBACK).format_map(
        _Fmt(
            run_id=run.get("run_id") or "unknown",
            status=run.get("status") or "unknown",
            failure_class=failure_class,
            confidence=confidence_s,
            result_id=result_id,
            delivery=_delivery_line(run),
            partner_mode=partner,
            publish_mode=publish,
            prefix=prefix,
        )
    ).strip() + "\n"


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


def render_denied(*, verb: str, prefix: str) -> str:
    return (
        f"`{prefix} {verb}` is not allowed for this actor. "
        "Write collaborators may run `status`, `help`, and `feedback`. "
        "Other verbs require repo admin or `RAPHAEL_GITHUB_COMMAND_TEAM` membership.\n"
    )


def render_deferred(*, verb: str, prefix: str) -> str:
    return (
        f"`{prefix} {verb}` is **not implemented** yet (GH-M2+). "
        "GH-M1 supports `status`, `help`, and `feedback accepted|rejected|edited` only. "
        "Check Runs are also deferred.\n"
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
