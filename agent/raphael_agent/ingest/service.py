"""Ingest orchestration: normalize → policy → persist run_record (FR-003–006)."""

from __future__ import annotations

import os
from typing import Any

from raphael_agent.graph.state import append_audit, initial_run_state
from raphael_agent.timeutil import utc_now
from raphael_agent.ingest.fingerprint import build_fingerprint
from raphael_agent.ingest.normalize import normalize_failed_run_event
from raphael_agent.ingest.policy import (
    IngestPolicyConfig,
    evaluate_ingest_policies,
    policy_decision_record,
)
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore


def _decision(
    *,
    decision: str,
    event_id: str,
    fingerprint: str,
    reason: str,
    run_id: str | None = None,
    existing_run_id: str | None = None,
    trigger_kind: str | None = None,
    repository: dict[str, Any] | None = None,
    commit_sha: str | None = None,
    cooldown_seconds_remaining: int | None = None,
    active_run_count: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision": decision,
        "event_id": event_id,
        "fingerprint": fingerprint,
        "run_id": run_id,
        "existing_run_id": existing_run_id,
        "decided_at": utc_now(),
        "reason": reason,
        "cooldown_seconds_remaining": cooldown_seconds_remaining,
        "active_run_count": active_run_count,
    }
    if trigger_kind:
        payload["trigger_kind"] = trigger_kind
    if repository and repository.get("owner") and repository.get("name"):
        payload["repository"] = {
            "owner": repository["owner"],
            "name": repository["name"],
        }
    if commit_sha:
        payload["commit_sha"] = commit_sha
    # Omit null optional fields for stricter additionalProperties schemas.
    cleaned = {k: v for k, v in payload.items() if v is not None}
    validate_agent("ingest_decision.json", cleaned)
    return cleaned


def accept_normalized_event(
    seed: dict[str, Any],
    *,
    store: RunStore | None = None,
    policy: IngestPolicyConfig | None = None,
    raw_payload: dict[str, Any] | bytes | str | None = None,
    sandbox_mode: str = "skipped",
    validate_run: bool = True,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Apply FR-003–006 and persist a pending run_record when accepted.

    Returns ``(ingest_decision, run_state_or_none)``.
    """
    store = store or RunStore()
    seed = dict(seed)
    if not seed.get("failure_fingerprint"):
        seed["failure_fingerprint"] = build_fingerprint(seed)

    event_id = (seed.get("trigger") or {}).get("event_id") or seed["run_id"]
    fingerprint = seed["failure_fingerprint"]
    tenant_id = seed["tenant_id"]

    if raw_payload is not None:
        raw_ref = store.save_raw_event(str(event_id), raw_payload)
        trigger = dict(seed.get("trigger") or {})
        trigger["raw_ref"] = raw_ref
        seed["trigger"] = trigger

    verdict = evaluate_ingest_policies(
        store,
        tenant_id=tenant_id,
        fingerprint=fingerprint,
        config=policy,
    )
    if not verdict.ok:
        decision = _decision(
            decision=verdict.decision,
            event_id=str(event_id),
            fingerprint=fingerprint,
            reason=verdict.reason,
            existing_run_id=verdict.existing_run_id,
            trigger_kind=(seed.get("trigger") or {}).get("kind"),
            repository=seed.get("repository"),
            commit_sha=seed.get("commit_sha"),
            cooldown_seconds_remaining=verdict.cooldown_seconds_remaining,
            active_run_count=verdict.active_run_count,
        )
        store.append_decision(decision)
        return decision, None

    run = initial_run_state(seed, sandbox_mode=sandbox_mode)
    run["failure_fingerprint"] = fingerprint
    if seed.get("correlation"):
        run["correlation"] = seed["correlation"]
    run["audit_id"] = run.get("audit_id") or run["run_id"]
    run["policy_decisions"] = [
        policy_decision_record(
            rule="ingest.dedupe_cooldown_concurrency",
            decision="allow",
            message=verdict.reason,
            at=utc_now(),
        )
    ]
    run["audit_events"] = append_audit(run, "ingest", "accepted", fingerprint)

    if validate_run:
        from raphael_agent.schema_util import for_run_record_validation

        validate_agent("run_record.json", for_run_record_validation(run))

    store.save_run(dict(run))
    decision = _decision(
        decision="accepted",
        event_id=str(event_id),
        fingerprint=fingerprint,
        reason=verdict.reason,
        run_id=run["run_id"],
        trigger_kind=(seed.get("trigger") or {}).get("kind"),
        repository=seed.get("repository"),
        commit_sha=seed.get("commit_sha"),
        active_run_count=verdict.active_run_count,
    )
    store.append_decision(decision)
    return decision, run


def accept_failed_run_event(
    event: dict[str, Any],
    *,
    store: RunStore | None = None,
    policy: IngestPolicyConfig | None = None,
    sandbox_mode: str = "skipped",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """normalize_failed_run_event → policy → persist."""
    seed = normalize_failed_run_event(event)
    return accept_normalized_event(
        seed,
        store=store,
        policy=policy,
        raw_payload=event,
        sandbox_mode=sandbox_mode,
    )


def accept_and_run_graph(
    event: dict[str, Any],
    *,
    store: RunStore | None = None,
    policy: IngestPolicyConfig | None = None,
    sandbox_mode: str = "recorded_stub",
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Ingest then invoke the stub graph when accepted (smoke / optional webhook mode)."""
    from raphael_agent.graph import run_stub_graph

    store = store or RunStore()
    decision, run = accept_failed_run_event(
        event,
        store=store,
        policy=policy,
        sandbox_mode=sandbox_mode,
    )
    if run is None:
        return decision, None
    final = run_stub_graph(run)
    store.save_run(dict(final))
    return decision, final


def should_auto_run_graph() -> bool:
    return os.environ.get("RAPHAEL_INGEST_RUN_GRAPH", "").lower() in {
        "1",
        "true",
        "yes",
    }
