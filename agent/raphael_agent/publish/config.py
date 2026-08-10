"""Publish configuration (env-driven). Partner dry-run is the pilot default."""

from __future__ import annotations

import os
from typing import Any, Literal

PublishMode = Literal["dry_run", "live"]
PartnerMode = Literal["dry_run", "allowlist", "diagnosis_only"]


def publish_mode() -> PublishMode:
    """Raw RAPHAEL_PUBLISH_MODE (before partner/allowlist gating)."""
    raw = os.environ.get("RAPHAEL_PUBLISH_MODE", "dry_run").strip().lower()
    if raw in {"live", "real", "github"}:
        return "live"
    return "dry_run"


def partner_mode() -> PartnerMode:
    """Pilot partner mode.

    - ``dry_run`` (default): always dry-run publish (safe partner default)
    - ``allowlist``: live draft PR only when ``RAPHAEL_PUBLISH_MODE=live``,
      token present, and failure class is in ``RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES``
    - ``diagnosis_only``: same as dry_run publish, message marks diagnosis-only partner path
    """
    raw = os.environ.get("RAPHAEL_PARTNER_MODE", "dry_run").strip().lower()
    if raw in {"allowlist", "allow", "pilot_allowlist"}:
        return "allowlist"
    if raw in {"diagnosis_only", "diagnosis", "diagnose_only"}:
        return "diagnosis_only"
    return "dry_run"


def live_publish_failure_classes() -> frozenset[str]:
    """Allowlisted failure classes for live draft PRs. Empty ⇒ no live publishes."""
    raw = os.environ.get("RAPHAEL_LIVE_PUBLISH_FAILURE_CLASSES", "").strip()
    if not raw:
        return frozenset()
    return frozenset(p.strip() for p in raw.split(",") if p.strip())


def failure_class_from_run(run: dict[str, Any]) -> str | None:
    diagnosis = run.get("diagnosis") or {}
    classification = diagnosis.get("classification") or {}
    value = classification.get("failure_class")
    return str(value) if value else None


def effective_publish_mode(run: dict[str, Any]) -> PublishMode:
    """Resolve dry_run vs live after partner mode + failure-class allowlist."""
    partner = partner_mode()
    if partner in {"dry_run", "diagnosis_only"}:
        return "dry_run"
    # allowlist partner mode
    if publish_mode() != "live":
        return "dry_run"
    allowed = live_publish_failure_classes()
    if not allowed:
        return "dry_run"
    failure_class = failure_class_from_run(run)
    if failure_class and failure_class in allowed:
        return "live"
    return "dry_run"


def github_token() -> str | None:
    """Resolve GitHub auth: PAT env first, else optional App installation token."""
    pat = (
        os.environ.get("RAPHAEL_GITHUB_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or None
    )
    if pat:
        return pat
    try:
        from raphael_agent.publish.github_app import (
            app_auth_configured,
            fetch_installation_token,
        )

        if app_auth_configured():
            return fetch_installation_token()
    except Exception:  # noqa: BLE001 — fail closed
        return None
    return None


def github_api_base() -> str:
    return os.environ.get("RAPHAEL_GITHUB_API_BASE", "https://api.github.com").rstrip(
        "/"
    )


def base_branch() -> str:
    return os.environ.get("RAPHAEL_GITHUB_BASE_BRANCH", "main").strip() or "main"


def pr_labels() -> list[str]:
    raw = os.environ.get("RAPHAEL_GITHUB_PR_LABELS", "raphael,agent-generated")
    return [p.strip() for p in raw.split(",") if p.strip()]


def pr_reviewers() -> list[str]:
    """Optional GitHub logins to request as reviewers (best-effort).

    Merges ``RAPHAEL_GITHUB_REVIEWERS`` with CODEOWNERS-derived logins when
    ``RAPHAEL_REVIEWERS_FROM_CODEOWNERS=1`` and a workspace/CODEOWNERS path is set.
    """
    raw = os.environ.get("RAPHAEL_GITHUB_REVIEWERS", "").strip()
    reviewers = [p.strip().lstrip("@") for p in raw.split(",") if p.strip()]
    if os.environ.get("RAPHAEL_REVIEWERS_FROM_CODEOWNERS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        from raphael_agent.publish.codeowners import reviewers_from_codeowners

        for login in reviewers_from_codeowners():
            if login not in reviewers:
                reviewers.append(login)
    return reviewers


def committer_name() -> str:
    return os.environ.get("RAPHAEL_GIT_COMMITTER_NAME", "raphael-agent")


def committer_email() -> str:
    return os.environ.get(
        "RAPHAEL_GIT_COMMITTER_EMAIL", "raphael-agent@users.noreply.github.com"
    )
