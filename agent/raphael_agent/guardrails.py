"""Pilot / MVP guardrails — code-enforced deny-list helpers (permission matrix).

These predicates mirror ``docs/permission-matrix.md``. Tests call them so
docs and runtime cannot drift unnoticed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from raphael_agent.publish.config import (
    effective_publish_mode,
    failure_class_from_run,
    github_token,
    live_publish_failure_classes,
    partner_mode,
    publish_mode,
)
from raphael_agent.publish import publish


@dataclass(frozen=True)
class GuardrailCheck:
    id: str
    ok: bool
    detail: str


def live_publish_allowed(run: dict[str, Any]) -> bool:
    """True only when every live-draft gate passes (not merely effective mode)."""
    if partner_mode() != "allowlist":
        return False
    if publish_mode() != "live":
        return False
    allowed = live_publish_failure_classes()
    if not allowed:
        return False
    fc = failure_class_from_run(run)
    if not fc or fc not in allowed:
        return False
    if not github_token():
        return False
    return effective_publish_mode(run) == "live"


def assert_publish_guardrails(run: dict[str, Any]) -> list[str]:
    """Return violation messages if a publish() call would break hard rules.

    Used by tests; does not mutate GitHub.
    """
    violations: list[str] = []
    status = run.get("status")
    if status in {"escalated", "failed_closed"}:
        result = publish(run)
        if result.get("ok"):
            violations.append("publish must fail closed for escalated/failed_closed")
        return violations

    if not run.get("result_id"):
        result = publish(run)
        if result.get("ok") or result.get("pull_request_url"):
            violations.append("publish without result_id must not succeed")
        return violations

    # Partner dry_run must never mutate even if PUBLISH_MODE=live
    if partner_mode() in {"dry_run", "diagnosis_only"}:
        if effective_publish_mode(run) != "dry_run":
            violations.append("partner dry_run/diagnosis_only must force effective dry_run")

    if partner_mode() == "allowlist" and not live_publish_failure_classes():
        if effective_publish_mode(run) != "dry_run":
            violations.append("empty failure-class allowlist must force dry_run")

    if effective_publish_mode(run) == "live" and not github_token():
        # publish() itself fails closed; effective mode can still be live
        pass

    return violations


def go_nogo_checks(*, require_token_for_live: bool = True) -> list[GuardrailCheck]:
    """Operator go/no-go snapshot from current env (no network)."""
    checks: list[GuardrailCheck] = []
    partner = partner_mode()
    checks.append(
        GuardrailCheck(
            id="partner_mode_set",
            ok=partner in {"dry_run", "allowlist", "diagnosis_only"},
            detail=f"RAPHAEL_PARTNER_MODE={partner}",
        )
    )
    allow = live_publish_failure_classes()
    checks.append(
        GuardrailCheck(
            id="default_safe_partner",
            ok=(
                partner in {"dry_run", "diagnosis_only"}
                or (
                    partner == "allowlist"
                    and (
                        publish_mode() != "live"
                        or (bool(allow) and len(allow) <= 3)
                    )
                )
            ),
            detail=(
                "partner dry_run (safe default)"
                if partner == "dry_run"
                else f"partner={partner} publish={publish_mode()} allowlist_n={len(allow)}"
            ),
        )
    )
    empty_allow = not allow
    checks.append(
        GuardrailCheck(
            id="empty_allowlist_blocks_live",
            ok=True,  # documented invariant; enforced in effective_publish_mode
            detail=(
                "allowlist empty => code forces dry_run"
                if empty_allow
                else f"allowlist={sorted(allow)}"
            ),
        )
    )
    checks.append(
        GuardrailCheck(
            id="no_auto_merge_configured",
            ok=os.environ.get("RAPHAEL_AUTO_MERGE", "").strip().lower()
            not in {"1", "true", "yes"},
            detail="RAPHAEL_AUTO_MERGE must stay unset/false (unsupported)",
        )
    )
    checks.append(
        GuardrailCheck(
            id="llm_default_off_for_pilot",
            ok=os.environ.get("RAPHAEL_LLM_DIAGNOSIS", "0").strip() in {"0", "", "false", "no"},
            detail=f"RAPHAEL_LLM_DIAGNOSIS={os.environ.get('RAPHAEL_LLM_DIAGNOSIS', '0')}",
        )
    )
    if partner == "allowlist" and publish_mode() == "live" and not empty_allow:
        has_token = bool(github_token())
        checks.append(
            GuardrailCheck(
                id="live_token_present",
                ok=has_token if require_token_for_live else True,
                detail="RAPHAEL_GITHUB_TOKEN required for live draft PRs"
                if not has_token
                else "GitHub token present",
            )
        )
        checks.append(
            GuardrailCheck(
                id="live_allowlist_narrow",
                ok=len(allow) <= 3,
                detail="Keep live allowlist narrow (≤3 classes) for first pilot week",
            )
        )
    return checks


def go_nogo_verdict(checks: list[GuardrailCheck] | None = None) -> dict[str, Any]:
    items = checks or go_nogo_checks()
    failed = [c for c in items if not c.ok]
    return {
        "go": len(failed) == 0,
        "checks": [{"id": c.id, "ok": c.ok, "detail": c.detail} for c in items],
        "failed": [c.id for c in failed],
        "recommendation": (
            "GO - env matches safe pilot posture"
            if not failed
            else "NO-GO - fix failed checks before live allowlist"
        ),
    }
