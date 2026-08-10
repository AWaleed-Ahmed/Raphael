"""Apply frozen learning_snapshot priors to diagnosis (and template weights)."""

from __future__ import annotations

from typing import Any

from raphael_agent.learning.config import learning_enabled
from raphael_agent.learning.engine import load_learning_snapshot


def _repo_key(run: dict[str, Any]) -> str | None:
    repo = run.get("repository") or {}
    if repo.get("owner") and repo.get("name"):
        return f"{repo['owner']}/{repo['name']}"
    return None


def prior_for_class(
    snapshot: dict[str, Any],
    *,
    failure_class: str,
    repository: str | None,
) -> dict[str, Any] | None:
    """Prefer repo-scoped prior, else global class prior."""
    classes = snapshot.get("classes") or []
    global_hit = None
    for entry in classes:
        if entry.get("failure_class") != failure_class:
            continue
        repo = entry.get("repository")
        if repository and repo == repository:
            return entry
        if repo is None:
            global_hit = entry
    return global_hit


def apply_learning_to_diagnosis(
    run: dict[str, Any], diagnosis: dict[str, Any]
) -> dict[str, Any]:
    """Adjust confidence / selection using offline priors. No-op if learning off."""
    if not learning_enabled():
        return diagnosis
    snapshot = load_learning_snapshot()
    if not snapshot:
        return diagnosis

    updated = dict(diagnosis)
    classification = dict(updated.get("classification") or {})
    # Never unblock blocked categories via learning.
    if classification.get("category") == "blocked":
        updated["notes"] = (
            (updated.get("notes") or "") + "; learning skipped for blocked class"
        ).strip("; ").strip()
        return updated

    fc = classification.get("failure_class") or "unknown"
    prior = prior_for_class(snapshot, failure_class=str(fc), repository=_repo_key(run))
    if not prior:
        return updated

    delta = float(prior.get("confidence_delta") or 0.0)
    conf = float(updated.get("confidence") or 0.0)
    new_conf = max(0.0, min(1.0, conf + delta))
    updated["confidence"] = new_conf

    # Apply same delta to matching hypotheses for audit consistency.
    hyps = []
    for hyp in updated.get("hypotheses") or []:
        h = dict(hyp)
        if h.get("failure_class") == fc:
            h["confidence"] = max(0.0, min(1.0, float(h.get("confidence") or 0) + delta))
        hyps.append(h)
    if hyps:
        # Re-rank by confidence descending.
        hyps.sort(key=lambda h: float(h.get("confidence") or 0), reverse=True)
        for i, h in enumerate(hyps, start=1):
            h["rank"] = i
        updated["hypotheses"] = hyps

    threshold = float(updated.get("confidence_threshold") or 0.7)
    prefer_escalate = bool(prior.get("prefer_escalate"))
    if prefer_escalate and new_conf < threshold + 0.05:
        updated["selected_hypothesis_id"] = None
        updated["confidence"] = 0.0
        note = (
            f"learning prefer_escalate for {fc} "
            f"(samples={prior.get('samples')} delta={delta})"
        )
    elif new_conf >= threshold and updated.get("selected_hypothesis_id") is None:
        # May promote if learning boosts past threshold and a hyp exists.
        if hyps and hyps[0].get("failure_class") == fc:
            updated["selected_hypothesis_id"] = hyps[0].get("hypothesis_id")
            updated["confidence"] = float(hyps[0].get("confidence") or new_conf)
        note = f"learning confidence_delta={delta} for {fc}"
    else:
        # If boost drops below threshold, clear selection.
        if updated.get("selected_hypothesis_id") and new_conf < threshold:
            updated["selected_hypothesis_id"] = None
            updated["confidence"] = 0.0
        note = f"learning confidence_delta={delta} for {fc}"

    updated["notes"] = (
        f"{updated.get('notes') or ''}; {note}; snapshot={snapshot.get('snapshot_id')}"
    ).strip("; ").strip()
    updated["learning"] = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "failure_class": fc,
        "confidence_delta": delta,
        "prefer_escalate": prefer_escalate,
        "template_weight": prior.get("template_weight"),
        "samples": prior.get("samples"),
    }
    return updated


def template_weight_for_run(run: dict[str, Any], failure_class: str) -> float:
    if not learning_enabled():
        return 1.0
    snapshot = load_learning_snapshot()
    if not snapshot:
        return 1.0
    prior = prior_for_class(
        snapshot, failure_class=failure_class, repository=_repo_key(run)
    )
    if not prior:
        return 1.0
    return float(prior.get("template_weight") or 1.0)
