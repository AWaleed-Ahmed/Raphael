"""Offline learner: FR-065 feedback → learning_snapshot priors."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from raphael_agent.feedback import JsonlFeedbackRecorder
from raphael_agent.learning.config import (
    max_confidence_delta,
    min_samples,
    snapshot_path,
)
from raphael_agent.schema_util import validate_agent
from raphael_agent.store import RunStore
from raphael_agent.timeutil import utc_now

POSITIVE = frozenset({"accepted", "merged", "deploy_succeeded"})
EDITED = frozenset({"edited"})
NEGATIVE = frozenset({"rejected", "closed_unmerged"})
DEPLOY_FAIL = frozenset({"deploy_failed"})


def _repo_key(event: dict[str, Any], runs_by_id: dict[str, dict[str, Any]]) -> str | None:
    repo = event.get("repository")
    if isinstance(repo, dict) and repo.get("owner") and repo.get("name"):
        return f"{repo['owner']}/{repo['name']}"
    run_id = event.get("run_id")
    if run_id and run_id in runs_by_id:
        r = runs_by_id[run_id].get("repository") or {}
        if r.get("owner") and r.get("name"):
            return f"{r['owner']}/{r['name']}"
    return None


def _failure_class(
    event: dict[str, Any], runs_by_id: dict[str, dict[str, Any]]
) -> str | None:
    if event.get("failure_class"):
        return str(event["failure_class"])
    run_id = event.get("run_id")
    if run_id and run_id in runs_by_id:
        classification = (runs_by_id[run_id].get("diagnosis") or {}).get(
            "classification"
        ) or {}
        fc = classification.get("failure_class")
        if fc:
            return str(fc)
    return None


def _score_bucket(stats: dict[str, int]) -> tuple[float, bool, float]:
    """Return (confidence_delta, prefer_escalate, template_weight)."""
    total = stats["samples"]
    if total <= 0:
        return 0.0, False, 1.0
    pos = stats["accepted_or_merged"]
    edited = stats["edited"]
    neg = stats["rejected_or_closed"]
    dfail = stats["deploy_failed"]
    # Weighted score in [-1, 1]
    raw = (pos * 1.0 + edited * -0.35 + neg * -1.0 + dfail * -1.25) / total
    cap = max_confidence_delta()
    delta = max(-cap, min(cap, raw * cap))
    prefer_escalate = (neg + dfail) >= max(2, (total + 1) // 2) and raw < -0.15
    # Template weight: boost successes, shrink failures (never zero).
    weight = max(0.25, min(2.0, 1.0 + raw))
    return round(delta, 4), prefer_escalate, round(weight, 4)


def build_learning_snapshot(
    *,
    feedback_rows: list[dict[str, Any]] | None = None,
    runs: list[dict[str, Any]] | None = None,
    min_n: int | None = None,
) -> dict[str, Any]:
    """Aggregate feedback into a schema-valid learning_snapshot."""
    rows = feedback_rows if feedback_rows is not None else JsonlFeedbackRecorder().read_all()
    run_list = runs if runs is not None else RunStore().list_runs()
    runs_by_id = {r["run_id"]: r for r in run_list if r.get("run_id")}
    threshold = min_n if min_n is not None else min_samples()

    buckets: dict[tuple[str, str | None], dict[str, int]] = defaultdict(
        lambda: {
            "samples": 0,
            "accepted_or_merged": 0,
            "edited": 0,
            "rejected_or_closed": 0,
            "deploy_failed": 0,
        }
    )

    for event in rows:
        outcome = str(event.get("outcome") or "")
        # Skip non-human outcome noise for learning.
        if outcome in {
            "draft_opened",
            "dry_run_prepared",
            "fix_snippet_posted",
            "fix_snippet_prepared",
            "other",
        }:
            continue
        fc = _failure_class(event, runs_by_id)
        if not fc or fc == "unknown":
            continue
        repo = _repo_key(event, runs_by_id)
        # Always accumulate global class stats; also repo-scoped when known.
        keys = [(fc, None)]
        if repo:
            keys.append((fc, repo))
        for key in keys:
            stats = buckets[key]
            stats["samples"] += 1
            if outcome in POSITIVE:
                stats["accepted_or_merged"] += 1
            elif outcome in EDITED:
                stats["edited"] += 1
            elif outcome in NEGATIVE:
                stats["rejected_or_closed"] += 1
            elif outcome in DEPLOY_FAIL:
                stats["deploy_failed"] += 1

    classes: list[dict[str, Any]] = []
    for (fc, repo), stats in sorted(buckets.items(), key=lambda x: (x[0][0], x[0][1] or "")):
        if stats["samples"] < threshold:
            continue
        delta, escalate, weight = _score_bucket(stats)
        classes.append(
            {
                "failure_class": fc,
                "repository": repo,
                "samples": stats["samples"],
                "accepted_or_merged": stats["accepted_or_merged"],
                "edited": stats["edited"],
                "rejected_or_closed": stats["rejected_or_closed"],
                "deploy_failed": stats["deploy_failed"],
                "confidence_delta": delta,
                "prefer_escalate": escalate,
                "template_weight": weight,
            }
        )

    snapshot = {
        "snapshot_id": f"learn-{uuid.uuid4().hex[:12]}",
        "built_at": utc_now(),
        "source": "feedback_jsonl",
        "version": "0.1.0",
        "min_samples": threshold,
        "feedback_events_total": len(rows),
        "notes": (
            "Priors from human/PR/deploy feedback only. "
            "Does not widen patch allowlists or change partner publish gates."
        ),
        "classes": classes,
    }
    validate_agent("learning_snapshot.json", snapshot)
    return snapshot


def save_learning_snapshot(snapshot: dict[str, Any], path: Path | None = None) -> Path:
    target = path or snapshot_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    validate_agent("learning_snapshot.json", snapshot)
    target.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return target


def load_learning_snapshot(path: Path | None = None) -> dict[str, Any] | None:
    target = path or snapshot_path()
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        validate_agent("learning_snapshot.json", data)
        return data
    except Exception:  # noqa: BLE001 — fail closed
        return None
