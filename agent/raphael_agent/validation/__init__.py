"""Correctness and silent-failure validation signals."""

from raphael_agent.validation.signals import evaluate_validation_signals


def rollout_resource(signature: dict) -> str:
    normalized = signature.get("normalized") or {}
    kind, name = normalized.get("resource_kind"), normalized.get("resource_name")
    if not isinstance(kind, str) or not kind or not isinstance(name, str) or not name:
        raise ValueError("Observed resource identity is required for rollout validation")
    return f"{kind.lower()}/{name}"


__all__ = ["evaluate_validation_signals", "rollout_resource"]
