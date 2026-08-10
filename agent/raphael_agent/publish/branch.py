"""Branch naming: raphael/<run-id>-<short-summary> (git-safe)."""

from __future__ import annotations

import re
from typing import Any

_SAFE = re.compile(r"[^a-zA-Z0-9._/-]+")
_MULTI_DASH = re.compile(r"-{2,}")


def short_summary_from_run(run: dict[str, Any], *, max_len: int = 40) -> str:
    diagnosis = run.get("diagnosis") or {}
    failure_class = (diagnosis.get("classification") or {}).get("failure_class")
    if failure_class and failure_class not in {"unknown", "healthy"}:
        summary = failure_class.replace("_", "-")
    else:
        hyp_id = diagnosis.get("selected_hypothesis_id") or "fix"
        summary = str(hyp_id).replace("_", "-")
    summary = _SAFE.sub("-", summary).strip("-.").lower()
    summary = _MULTI_DASH.sub("-", summary)
    if not summary:
        summary = "fix"
    return summary[:max_len].rstrip("-.")


def branch_name_for_run(run: dict[str, Any], *, max_total: int = 200) -> str:
    """Build ``raphael/<run-id>-<summary>`` truncated to git-safe length."""
    run_id = str(run.get("run_id") or "run")
    run_id = _SAFE.sub("-", run_id).strip("-")
    summary = short_summary_from_run(run)
    # Prefer keeping full run_id; truncate summary first.
    prefix = f"raphael/{run_id}-"
    budget = max_total - len(prefix)
    if budget < 8:
        # Extreme: hash-ish truncate run_id
        run_id = run_id[:48]
        prefix = f"raphael/{run_id}-"
        budget = max_total - len(prefix)
    summary = summary[: max(budget, 1)].rstrip("-.")
    name = f"{prefix}{summary}"
    return name[:max_total].rstrip("-./")


def pr_title_for_run(run: dict[str, Any]) -> str:
    resources = run.get("affected_resources") or []
    workload = resources[0]["name"] if resources else "workload"
    diagnosis = run.get("diagnosis") or {}
    cause = (diagnosis.get("classification") or {}).get("failure_class") or "deployment failure"
    cause = str(cause).replace("_", " ")
    return f"[Raphael] Fix {workload} deployment failure: {cause}"
