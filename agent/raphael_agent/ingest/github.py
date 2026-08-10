"""GitHub webhook authentication and event dispatch (FR-001 + Phase 6 issues)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

from raphael_agent.timeutil import utc_now
from raphael_agent.ingest.issue_config import (
    default_commit_sha_fallback,
    issue_trigger_label,
    parse_raphael_sha,
)
from raphael_agent.ingest.normalize import (
    normalize_github_check_run,
    normalize_github_deployment_status,
    normalize_github_issue,
    normalize_github_workflow_run,
)
from raphael_agent.publish.config import base_branch, github_api_base, github_token


class WebhookAuthError(Exception):
    """Invalid or missing GitHub webhook signature."""


def webhook_secret() -> str | None:
    return os.environ.get("RAPHAEL_GITHUB_WEBHOOK_SECRET") or None


def verify_github_signature(
    body: bytes,
    signature_header: str | None,
    *,
    secret: str | None = None,
) -> None:
    """Verify ``X-Hub-Signature-256``. Fail closed when a secret is configured."""
    configured = secret if secret is not None else webhook_secret()
    if not configured:
        # Local/dev: allow unsigned when secret unset (document in README).
        return
    if not signature_header or not signature_header.startswith("sha256="):
        raise WebhookAuthError("missing or malformed X-Hub-Signature-256")
    digest = hmac.new(
        configured.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    expected = "sha256=" + digest
    if not hmac.compare_digest(expected, signature_header):
        raise WebhookAuthError("invalid webhook signature")


def _resolve_default_branch_sha(owner: str, repo: str, branch: str | None) -> str | None:
    """Best-effort HEAD sha for default branch when issue body omits raphael-sha."""
    token = github_token()
    if not token:
        return default_commit_sha_fallback()
    branch_name = branch or base_branch()
    import httpx

    url = f"{github_api_base().rstrip('/')}/repos/{owner}/{repo}/git/ref/heads/{branch_name}"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "raphael-agent",
                },
            )
            if response.status_code >= 400:
                return default_commit_sha_fallback()
            data = response.json()
            return data.get("object", {}).get("sha") or default_commit_sha_fallback()
    except Exception:  # noqa: BLE001
        return default_commit_sha_fallback()


def parse_github_webhook(
    body: bytes,
    *,
    event_name: str,
    delivery_id: str | None = None,
    signature_header: str | None = None,
    secret: str | None = None,
    raw_ref: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Authenticate + normalize a GitHub webhook.

    Returns ``(seed_or_none, ignore_reason)``. ``seed`` is None when the event
    is authenticated but not an actionable failure (ignored).
    """
    verify_github_signature(body, signature_header, secret=secret)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON body: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("webhook JSON must be an object")

    received_at = utc_now()
    ref = raw_ref or f"github:{event_name}:{delivery_id or 'unknown'}"

    if event_name == "workflow_run":
        try:
            return (
                normalize_github_workflow_run(
                    payload, raw_ref=ref, received_at=received_at
                ),
                "",
            )
        except ValueError as exc:
            return None, str(exc)

    if event_name == "check_run":
        try:
            return (
                normalize_github_check_run(
                    payload, raw_ref=ref, received_at=received_at
                ),
                "",
            )
        except ValueError as exc:
            return None, str(exc)

    if event_name == "deployment_status":
        try:
            return (
                normalize_github_deployment_status(
                    payload, raw_ref=ref, received_at=received_at
                ),
                "",
            )
        except ValueError as exc:
            return None, str(exc)

    if event_name == "issues":
        try:
            issue = payload.get("issue") or {}
            body_text = issue.get("body") if isinstance(issue, dict) else None
            sha = parse_raphael_sha(body_text if isinstance(body_text, str) else None)
            if not sha:
                repo = payload.get("repository") or {}
                owner_obj = repo.get("owner") or {}
                owner = owner_obj.get("login") or owner_obj.get("name")
                name = repo.get("name")
                default_branch = repo.get("default_branch")
                if owner and name:
                    sha = _resolve_default_branch_sha(str(owner), str(name), default_branch)
            if not sha:
                return (
                    None,
                    "issue missing raphael-sha and could not resolve default branch HEAD "
                    "(set RAPHAEL_DEFAULT_COMMIT_SHA or RAPHAEL_GITHUB_TOKEN)",
                )
            return (
                normalize_github_issue(
                    payload,
                    raw_ref=ref,
                    received_at=received_at,
                    trigger_label=issue_trigger_label(),
                    commit_sha=sha,
                ),
                "",
            )
        except ValueError as exc:
            return None, str(exc)

    return None, f"unsupported github event: {event_name}"
