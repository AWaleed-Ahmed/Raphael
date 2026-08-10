"""Operator metrics over RunStore + ingest decisions (Phase 4)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
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
    runs = store.list_runs()
    status_counts: Counter[str] = Counter()
    publish_modes: Counter[str] = Counter()
    patch_attempts_total = 0
    durations: list[float] = []
    for run in runs:
        status_counts[str(run.get("status") or "unknown")] += 1
        pub = run.get("publish") or {}
        if pub:
            mode = pub.get("mode") or ("dry_run" if pub.get("dry_run") else "live")
            publish_modes[str(mode)] += 1
        attempts = run.get("attempt_count") or {}
        patch_attempts_total += int(attempts.get("patch") or 0)
        dur = _duration_seconds(run)
        if dur is not None:
            durations.append(dur)

    ingest_counts: Counter[str] = Counter()
    for decision in store.iter_decisions() if hasattr(store, "iter_decisions") else []:
        ingest_counts[str(decision.get("decision") or "unknown")] += 1
    # Fallback: read decisions jsonl if helper missing
    if not ingest_counts:
        ingest_counts = _read_decisions(store)

    avg_duration = sum(durations) / len(durations) if durations else None
    return {
        "generated_at": utc_now(),
        "runs_total": len(runs),
        "by_terminal_status": dict(status_counts),
        "ingest_decisions": dict(ingest_counts),
        "publish_modes": dict(publish_modes),
        "patch_attempts_total": patch_attempts_total,
        "avg_run_duration_seconds": avg_duration,
        "notes": [
            "Sandbox force-cleanup remains controller-side (POST /v1/admin/force-cleanup).",
            "Agent metrics are read-only aggregates over RAPHAEL_AGENT_DATA_DIR.",
        ],
    }


def _read_decisions(store: RunStore) -> Counter[str]:
    counts: Counter[str] = Counter()
    path = store.decisions_path
    if not path.is_file():
        return counts
    import json

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        counts[str(row.get("decision") or "unknown")] += 1
    return counts
