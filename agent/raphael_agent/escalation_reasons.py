"""Private escalation-report vocabulary, distinct from free-form terminal details.

The checked-in JSON schema must match this vocabulary exactly. Source-drift
tests cover graph literals and their analyzer, budget and template producers.
This module adds no runtime rejection or persistence enforcement.
"""

from typing import Literal, get_args


EscalationReason = Literal[
    "insufficient_evidence",
    "production_secret_required",
    "privileged_or_host_access",
    "diagnosis_only",
    "unresolved_secret_dependency",
    "patch_target_unavailable",
    "patch_value_unavailable",
    "patch_unavailable",
    "low_confidence",
    "blocked_category",
    "reproduction_failed",
    "fidelity_gap",
    "policy_blocked",
    "validation_failed",
    "budget_exhausted",
    "system_error",
    "cancelled",
    "model_required",
]

ESCALATION_REASON_CODES = frozenset(get_args(EscalationReason))
