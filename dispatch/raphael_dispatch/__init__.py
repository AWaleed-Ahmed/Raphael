"""Raphael dispatch orchestration and connector protocol boundaries."""

from .orchestrator import AgentHooks, OrchestrationError, Orchestrator
from .patch_store import EphemeralPatchStore
from .protocol import (
    ALLOWED_VERBS,
    ContractSchemas,
    ProtocolValidationError,
    choose_next_action,
    get_schemas,
    validate_envelope,
)

__all__ = [
    "ALLOWED_VERBS",
    "AgentHooks",
    "ContractSchemas",
    "EphemeralPatchStore",
    "OrchestrationError",
    "Orchestrator",
    "ProtocolValidationError",
    "choose_next_action",
    "get_schemas",
    "validate_envelope",
]
