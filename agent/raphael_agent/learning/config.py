"""Learning configuration (Post-MVP loop; off by default)."""

from __future__ import annotations

import os
from pathlib import Path


def learning_enabled() -> bool:
    return os.environ.get("RAPHAEL_LEARNING", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def min_samples() -> int:
    raw = os.environ.get("RAPHAEL_LEARNING_MIN_SAMPLES", "3")
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(50, value))


def snapshot_path() -> Path:
    explicit = os.environ.get("RAPHAEL_LEARNING_SNAPSHOT", "").strip()
    if explicit:
        return Path(explicit)
    root = Path(os.environ.get("RAPHAEL_AGENT_DATA_DIR") or ".raphael-agent-data")
    return root / "learning_snapshot.json"


def max_confidence_delta() -> float:
    return 0.25
