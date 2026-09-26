"""Remove executable patch bytes from durable records; keep live payloads intact."""

from __future__ import annotations

from typing import Any


PATCH_CONTENT_KEYS = {"rendered_files", "content", "unified_diff", "unified_diff_hunk"}


def without_patch_content(value: Any) -> Any:
    """Copy nested patch containers without raw file bodies or diffs.

    This deliberately strips bodies rather than guessing which values are secrets.
    Evidence excerpts are a separate redaction boundary, not patch payloads.
    """
    if isinstance(value, dict):
        return {
            key: without_patch_content(item)
            for key, item in value.items()
            if key not in PATCH_CONTENT_KEYS
        }
    if isinstance(value, list):
        return [without_patch_content(item) for item in value]
    return value


def durable_run_record(run: dict[str, Any]) -> dict[str, Any]:
    """Project connector runs to metadata; never mutate the live execution state."""
    out = {key: value for key, value in run.items() if key != "rendered_files"}
    if not isinstance(run.get("dispatch"), dict):
        return out
    out = without_patch_content(out)
    # An in-flight action/proposal cannot be reconstructed from metadata alone.
    # Make that loss explicit so rehydration never executes a stripped payload.
    changed = any(
        out.get(key) != run.get(key)
        for key in ("candidate_patches", "dispatch", "validated_fix_record")
    )
    if changed and out["dispatch"].get("stage") != "terminal":
        out["dispatch"]["patch_payloads_omitted"] = True
    return out
