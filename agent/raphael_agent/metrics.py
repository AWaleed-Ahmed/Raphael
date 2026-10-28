"""Operator metrics over RunStore + ingest decisions (Phase 4)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from raphael_agent.store import RunStore
from raphael_agent.timeutil import utc_now


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _duration_seconds(run: dict[str, Any]) -> float | None:
    start = _parse_iso(run.get("created_at"))
    end = _parse_iso(run.get("updated_at"))
    if not start or not end:
        return None
    return max(0.0, (end - start).total_seconds())


def summarize_store(store: RunStore | None = None) -> dict[str, Any]:
    """Aggregate lightweight operator metrics from durable RunStore docs."""
    store = store or RunStore()
    runs_total = 0
    duration_total = 0.0
    duration_count = 0
    models = ModelMetrics()
    status_counts: Counter[str] = Counter()
    publish_modes: Counter[str] = Counter()
    patch_attempts_total = 0
    for run in store.iter_runs():
        runs_total += 1
        models.observe(run)
        status_counts[str(run.get("status") or "unknown")] += 1
        pub = run.get("publish") or {}
        if pub:
            mode = pub.get("mode") or ("dry_run" if pub.get("dry_run") else "live")
            publish_modes[str(mode)] += 1
        attempts = run.get("attempt_count") or {}
        patch_attempts_total += int(attempts.get("patch") or 0)
        dur = _duration_seconds(run)
        if dur is not None:
            duration_total += dur
            duration_count += 1

    ingest_counts: Counter[str] = Counter()
    for decision in store.iter_decisions() if hasattr(store, "iter_decisions") else []:
        ingest_counts[str(decision.get("decision") or "unknown")] += 1
    # Fallback: read decisions jsonl if helper missing
    if not ingest_counts:
        ingest_counts = _read_decisions(store)

    avg_duration = duration_total / duration_count if duration_count else None
    feedback = summarize_feedback()
    learning = summarize_learning()
    return {
        "generated_at": utc_now(),
        "runs_total": runs_total,
        "by_terminal_status": dict(status_counts),
        "ingest_decisions": dict(ingest_counts),
        "publish_modes": dict(publish_modes),
        "patch_attempts_total": patch_attempts_total,
        "avg_run_duration_seconds": avg_duration,
        "models": models.summary(),
        "feedback": feedback,
        "learning": learning,
        "notes": [
            "Sandbox force-cleanup remains controller-side (POST /v1/admin/force-cleanup).",
            "Agent metrics are read-only aggregates over RAPHAEL_AGENT_DATA_DIR.",
            "FR-065 feedback aggregates are audit-only unless RAPHAEL_LEARNING=1 applies a snapshot.",
        ],
    }


def summarize_learning() -> dict[str, Any]:
    from raphael_agent.learning import learning_enabled, load_learning_snapshot

    snap = load_learning_snapshot()
    if not snap:
        return {
            "enabled": learning_enabled(),
            "snapshot_loaded": False,
            "classes": 0,
        }
    return {
        "enabled": learning_enabled(),
        "snapshot_loaded": True,
        "snapshot_id": snap.get("snapshot_id"),
        "classes": len(snap.get("classes") or []),
        "built_at": snap.get("built_at"),
    }


def summarize_feedback() -> dict[str, Any]:
    """Aggregate FR-065 feedback.jsonl outcomes (deepened audit, no ML)."""
    from raphael_agent.feedback import JsonlFeedbackRecorder

    rows = JsonlFeedbackRecorder().iter_events()
    by_outcome: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    total = 0
    for row in rows:
        total += 1
        by_outcome[str(row.get("outcome") or "unknown")] += 1
        by_source[str(row.get("source") or "unknown")] += 1
    return {
        "events_total": total,
        "by_outcome": dict(by_outcome),
        "by_source": dict(by_source),
    }


def _read_decisions(store: RunStore) -> Counter[str]:
    counts: Counter[str] = Counter()
    path = store.decisions_path
    if not path.is_file():
        return counts
    with path.open(encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            counts[str(row.get("decision") or "unknown")] += 1
    return counts


class ModelMetrics:
    """Fixed-cardinality, five-minute inference signals over existing run audits."""

    def __init__(self) -> None:
        from raphael_agent.model_gateway import CAPABILITIES

        self.since = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.counts = {name: Counter() for name in CAPABILITIES.values()}
        self.latest: dict[str, list[tuple[datetime, bool]]] = {name: [] for name in self.counts}
        self.critical: set[str] = set()

    def observe(self, run: dict[str, Any]) -> None:
        for event in run.get("audit_events") or []:
            if event.get("event") != "model_execution":
                continue
            at = _parse_iso(event.get("at"))
            if at is None or at < self.since or at > self.since + timedelta(minutes=5):
                continue
            detail = str(event.get("detail") or "")
            try:
                row = json.loads(detail[detail.index("{"):])
            except (ValueError, json.JSONDecodeError):
                continue
            at = _parse_iso(row.get("completed_at")) or at
            if at < self.since or at > self.since + timedelta(minutes=5):
                continue
            name = row.get("capability")
            if name not in self.counts:
                continue
            counts = self.counts[name]
            source = row.get("source")
            if source not in {"disabled", "not_applicable", "unavailable_fallback", "abstention",
                              "deterministic_rule_override", "trained_inference", "deterministic"}:
                continue
            counts[source] += 1
            if row.get("reason") in {
                "incident_scope_mismatch", "incident_scope_unverified", "incident_record_scope_unverified",
                "stop_control_unavailable",
                "manifest_hash_mismatch", "artifact_hash_mismatch", "invalid_model_output",
            }:
                self.critical.add(name)
            if row.get("attempted") is not True:
                continue
            error = source == "unavailable_fallback"
            counts["attempts"] += 1
            counts["errors"] += error
            self.latest[name] = sorted(self.latest[name] + [(at, error)], key=lambda item: item[0])[-3:]
            elapsed = row.get("elapsed_ms")
            if isinstance(elapsed, (int, float)) and elapsed > 50:
                counts["latency_over_50ms"] += 1

    def summary(self) -> dict[str, Any]:
        alerts = []
        for name, counts in self.counts.items():
            if name in self.critical:
                alerts.append({"capability": name, "code": "model_integrity", "severity": "critical"})
            last = self.latest[name]
            if ((counts["attempts"] >= 100 and counts["errors"] / counts["attempts"] > .01)
                    or (len(last) == 3 and all(error for _, error in last))):
                alerts.append({"capability": name, "code": "model_runtime_errors", "severity": "warning"})
        return {"window_seconds": 300, "by_capability": {k: dict(v) for k, v in self.counts.items()},
                "alerts": alerts, "delivery": "operator_poll", "quality": "unmeasured"}
