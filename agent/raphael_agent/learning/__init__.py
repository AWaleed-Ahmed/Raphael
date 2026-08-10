"""Post-MVP learning loop: offline feedback → priors → diagnosis/patch nudges."""

from __future__ import annotations

from raphael_agent.learning.apply import (
    apply_learning_to_diagnosis,
    template_weight_for_run,
)
from raphael_agent.learning.config import learning_enabled, snapshot_path
from raphael_agent.learning.engine import (
    build_learning_snapshot,
    load_learning_snapshot,
    save_learning_snapshot,
)

__all__ = [
    "apply_learning_to_diagnosis",
    "build_learning_snapshot",
    "learning_enabled",
    "load_learning_snapshot",
    "save_learning_snapshot",
    "snapshot_path",
    "template_weight_for_run",
]
