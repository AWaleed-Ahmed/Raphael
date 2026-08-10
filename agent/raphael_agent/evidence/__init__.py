"""Evidence collection facade — adapters + stub fallback (FR-010–014 skeleton)."""

from __future__ import annotations

from typing import Any

from raphael_agent.evidence.github_actions import collect_github_actions_evidence
from raphael_agent.evidence.issue import collect_issue_evidence
from raphael_agent.evidence.stub import collect_fixture_evidence, stub_collect_evidence

__all__ = [
    "collect_evidence",
    "collect_fixture_evidence",
    "stub_collect_evidence",
]


def collect_evidence(run: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect evidence via adapters; fall back to fixture stub when empty."""
    issue_items = collect_issue_evidence(run)
    if issue_items:
        return issue_items
    items = collect_github_actions_evidence(run)
    if items:
        return items
    return collect_fixture_evidence(run)
