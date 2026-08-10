"""Cooldown and concurrency policies (FR-006)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from raphael_agent.store import RunStore


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class IngestPolicyConfig:
    cooldown_seconds: int = 900
    max_concurrent_runs: int = 2

    @classmethod
    def from_env(cls) -> IngestPolicyConfig:
        return cls(
            cooldown_seconds=int(os.environ.get("RAPHAEL_INGEST_COOLDOWN_SECONDS", "900")),
            max_concurrent_runs=int(
                os.environ.get("RAPHAEL_INGEST_MAX_CONCURRENT_RUNS", "2")
            ),
        )


@dataclass(frozen=True)
class PolicyVerdict:
    ok: bool
    decision: str
    reason: str
    existing_run_id: str | None = None
    cooldown_seconds_remaining: int | None = None
    active_run_count: int | None = None


def evaluate_ingest_policies(
    store: RunStore,
    *,
    tenant_id: str,
    fingerprint: str,
    config: IngestPolicyConfig | None = None,
    now: datetime | None = None,
) -> PolicyVerdict:
    """Apply duplicate / cooldown / concurrency gates before creating a new run."""
    cfg = config or IngestPolicyConfig.from_env()
    now = now or datetime.now(timezone.utc)

    active = store.find_by_fingerprint(
        fingerprint, statuses={"pending", "running"}
    )
    if active:
        return PolicyVerdict(
            ok=False,
            decision="duplicate",
            reason="active run already exists for fingerprint",
            existing_run_id=active.get("run_id"),
            active_run_count=store.count_active(tenant_id),
        )

    prior = store.find_by_fingerprint(fingerprint)
    if prior and cfg.cooldown_seconds > 0:
        prior_ts = _parse_ts(prior.get("updated_at") or prior.get("created_at"))
        if prior_ts is not None:
            if prior_ts.tzinfo is None:
                prior_ts = prior_ts.replace(tzinfo=timezone.utc)
            elapsed = (now - prior_ts).total_seconds()
            remaining = int(cfg.cooldown_seconds - elapsed)
            if remaining > 0:
                return PolicyVerdict(
                    ok=False,
                    decision="cooldown",
                    reason=(
                        f"fingerprint within cooldown window "
                        f"({cfg.cooldown_seconds}s)"
                    ),
                    existing_run_id=prior.get("run_id"),
                    cooldown_seconds_remaining=remaining,
                    active_run_count=store.count_active(tenant_id),
                )

    active_count = store.count_active(tenant_id)
    if active_count >= cfg.max_concurrent_runs:
        return PolicyVerdict(
            ok=False,
            decision="concurrency_limit",
            reason=(
                f"tenant has {active_count} active runs; "
                f"max={cfg.max_concurrent_runs}"
            ),
            active_run_count=active_count,
        )

    return PolicyVerdict(
        ok=True,
        decision="accepted",
        reason="policy gates passed",
        active_run_count=active_count,
    )


def policy_decision_record(
    *,
    rule: str,
    decision: str,
    message: str,
    at: str,
) -> dict[str, Any]:
    return {"rule": rule, "decision": decision, "message": message, "at": at}
