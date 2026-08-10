"""Run budgets / timeouts / cost ceilings (Phase 4). Fail closed on exhaust."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def max_wall_seconds() -> int:
    # Default 30 minutes (PRD §9.4); tests may lower via env.
    return max(1, _env_int("RAPHAEL_MAX_WALL_SECONDS", 1800))


def max_diagnosis_attempts() -> int:
    return max(1, _env_int("RAPHAEL_MAX_DIAGNOSIS_ATTEMPTS", 2))


def max_patch_attempts_budget() -> int:
    # Align with patch.config / RAPHAEL_MAX_PATCH_ATTEMPTS
    return max(1, _env_int("RAPHAEL_MAX_PATCH_ATTEMPTS", 3))


def max_cost_usd() -> float:
    # 0 = disabled
    return max(0.0, _env_float("RAPHAEL_MAX_COST_USD", 0.0))


def sandbox_http_timeout_seconds() -> float:
    return max(1.0, _env_float("RAPHAEL_SANDBOX_HTTP_TIMEOUT", 180.0))


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_budget_snapshot(*, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    wall = max_wall_seconds()
    deadline = now + timedelta(seconds=wall)
    return {
        "max_wall_seconds": wall,
        "max_diagnosis_attempts": max_diagnosis_attempts(),
        "max_patch_attempts": max_patch_attempts_budget(),
        "max_cost_usd": max_cost_usd(),
        "deadline_at": deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sandbox_http_timeout_seconds": sandbox_http_timeout_seconds(),
    }


def check_budgets(run: dict[str, Any], *, node: str) -> dict[str, Any] | None:
    """Return a halt descriptor if a budget is exhausted; else None.

    Halt shape: ``{kind, reason_code, message, terminal}`` where terminal is
    ``escalated`` or ``failed_closed``.
    """
    snap = run.get("budget_snapshot") or {}
    attempts = run.get("attempt_count") or {}
    usage = run.get("token_and_cost_usage") or {}

    # Wall clock
    deadline_raw = snap.get("deadline_at")
    if deadline_raw:
        try:
            if datetime.now(timezone.utc) > _parse_iso(str(deadline_raw)):
                return {
                    "kind": "wall_time",
                    "reason_code": "budget_exhausted",
                    "message": f"Wall-clock budget exceeded at node={node}",
                    "terminal": "escalated",
                }
        except ValueError:
            return {
                "kind": "wall_time",
                "reason_code": "budget_exhausted",
                "message": f"Invalid deadline_at; fail closed at node={node}",
                "terminal": "failed_closed",
            }

    # Diagnosis attempts (check current count — caller increments after)
    max_diag = int(snap.get("max_diagnosis_attempts") or max_diagnosis_attempts())
    if int(attempts.get("diagnosis") or 0) > max_diag:
        return {
            "kind": "diagnosis_attempts",
            "reason_code": "budget_exhausted",
            "message": f"Diagnosis attempts exceeded max={max_diag}",
            "terminal": "escalated",
        }

    max_patch = int(snap.get("max_patch_attempts") or max_patch_attempts_budget())
    if int(attempts.get("patch") or 0) > max_patch:
        return {
            "kind": "patch_attempts",
            "reason_code": "budget_exhausted",
            "message": f"Patch attempts exceeded max={max_patch}",
            "terminal": "escalated",
        }

    max_cost = float(snap.get("max_cost_usd") if snap.get("max_cost_usd") is not None else max_cost_usd())
    if max_cost > 0:
        spent = float(usage.get("estimated_cost_usd") or 0.0)
        if spent > max_cost:
            return {
                "kind": "cost",
                "reason_code": "budget_exhausted",
                "message": f"Estimated cost ${spent} exceeds ceiling ${max_cost}",
                "terminal": "escalated",
            }

    return None
