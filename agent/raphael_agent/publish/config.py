"""Publish configuration (env-driven). Default mode is dry_run."""

from __future__ import annotations

import os
from typing import Literal

PublishMode = Literal["dry_run", "live"]


def publish_mode() -> PublishMode:
    raw = os.environ.get("RAPHAEL_PUBLISH_MODE", "dry_run").strip().lower()
    if raw in {"live", "real", "github"}:
        return "live"
    return "dry_run"


def github_token() -> str | None:
    return (
        os.environ.get("RAPHAEL_GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or None
    )


def github_api_base() -> str:
    return os.environ.get("RAPHAEL_GITHUB_API_BASE", "https://api.github.com").rstrip(
        "/"
    )


def base_branch() -> str:
    return os.environ.get("RAPHAEL_GITHUB_BASE_BRANCH", "main").strip() or "main"


def pr_labels() -> list[str]:
    raw = os.environ.get("RAPHAEL_GITHUB_PR_LABELS", "raphael,agent-generated")
    return [p.strip() for p in raw.split(",") if p.strip()]


def committer_name() -> str:
    return os.environ.get("RAPHAEL_GIT_COMMITTER_NAME", "raphael-agent")


def committer_email() -> str:
    return os.environ.get(
        "RAPHAEL_GIT_COMMITTER_EMAIL", "raphael-agent@users.noreply.github.com"
    )
