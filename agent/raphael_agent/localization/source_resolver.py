"""Source-map/debug-symbol provenance adapters for runtime anchors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raphael_agent.localization.anchors import RuntimeAnchor


def required_oci_labels(labels: dict[str, Any]) -> list[str]:
    """Return required OCI provenance labels missing from an image metadata map."""
    return [
        key for key in ("org.opencontainers.image.revision", "org.opencontainers.image.source")
        if not str(labels.get(key) or "").strip()
    ]


def _load_json(root: Path, names: tuple[str, ...]) -> dict[str, Any]:
    for name in names:
        path = root / name
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            return value
    return {}


def resolve_anchor(anchor: RuntimeAnchor, workspace: str | Path | None) -> RuntimeAnchor:
    """Resolve explicit repository source maps/debug symbol maps when present.

    Supported local metadata files are ``.raphael/source-map.json`` and
    ``.raphael/debug-symbols.json``. This is deliberately explicit and
    deterministic; missing metadata leaves the original anchor untouched.
    """
    if not workspace:
        return anchor
    root = Path(workspace)
    source_map = _load_json(root, (".raphael/source-map.json", "source-map.json"))
    symbols = _load_json(root, (".raphael/debug-symbols.json", "debug-symbols.json"))
    key = f"{anchor.file_path}:{anchor.line_number}:{anchor.symbol_name}"
    entry = symbols.get(key) or symbols.get(anchor.file_path) or source_map.get(anchor.file_path)
    if not isinstance(entry, dict):
        return anchor
    return RuntimeAnchor(
        signal_type=anchor.signal_type,
        file_path=str(entry.get("source_file") or entry.get("file") or anchor.file_path).lstrip("/"),
        line_number=int(entry.get("source_line") or entry.get("line") or anchor.line_number),
        symbol_name=str(entry.get("source_symbol") or entry.get("symbol") or anchor.symbol_name),
        confidence=min(1.0, anchor.confidence + 0.05),
        evidence_ref=anchor.evidence_ref,
        raw_details={**anchor.raw_details, "source_map_resolved": True},
    )
