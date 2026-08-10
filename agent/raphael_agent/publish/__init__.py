"""Publish stubs — Phase 3 will open draft GitHub PRs from result_id."""

from __future__ import annotations

from typing import Any


def stub_publish(run: dict[str, Any]) -> dict[str, Any]:
    """No-op publish placeholder. Requires a sandbox ``result_id``; never opens a PR."""
    result_id = run.get("result_id")
    if not result_id:
        return {
            "ok": False,
            "error": "result_id_required",
            "message": "Publish stub refuses to proceed without a frozen sandbox result_id",
            "pull_request_url": None,
        }
    return {
        "ok": True,
        "error": None,
        "message": f"Phase 0 placeholder: draft PR not opened; would use result_id={result_id}",
        "pull_request_url": None,
    }
