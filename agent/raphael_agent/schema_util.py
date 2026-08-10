"""JSON Schema helpers for agent + sandbox contracts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_ROOT = REPO_ROOT / "contracts"
AGENT_CONTRACTS = CONTRACTS_ROOT / "agent"
SANDBOX_CONTRACTS = CONTRACTS_ROOT / "sandbox"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def schema_registry() -> Registry:
    """Registry covering contracts/agent and contracts/sandbox for $ref resolution."""
    resources: list[tuple[str, Resource]] = []
    for directory in (AGENT_CONTRACTS, SANDBOX_CONTRACTS):
        for path in directory.glob("*.json"):
            contents = _load_json(path)
            uri = contents.get("$id") or path.as_uri()
            resources.append((uri, Resource.from_contents(contents, default_specification=DRAFT202012)))
            # Also register by file URI so relative ../sandbox/... refs resolve.
            resources.append((path.as_uri(), Resource.from_contents(contents, default_specification=DRAFT202012)))
    registry: Registry = Registry()
    for uri, resource in resources:
        registry = registry.with_resource(uri, resource)
    return registry


def load_agent_schema(name: str) -> dict[str, Any]:
    return _load_json(AGENT_CONTRACTS / name)


def load_sandbox_schema(name: str) -> dict[str, Any]:
    return _load_json(SANDBOX_CONTRACTS / name)


def validate_against(schema: dict[str, Any], instance: Any) -> None:
    """Validate instance; raises jsonschema.ValidationError on failure."""
    schema_id = schema.get("$id")
    if schema_id:
        Draft202012Validator({"$ref": schema_id}, registry=schema_registry()).validate(instance)
    else:
        Draft202012Validator(schema, registry=schema_registry()).validate(instance)


def validate_agent(name: str, instance: Any) -> None:
    validate_against(load_agent_schema(name), instance)


def validate_sandbox(name: str, instance: Any) -> None:
    validate_against(load_sandbox_schema(name), instance)


def for_run_record_validation(state: dict[str, Any]) -> dict[str, Any]:
    """Drop optional None fields so run_record schema validation succeeds."""
    skip_if_none = {
        "failure_signature",
        "diagnosis",
        "reproduction_result",
        "validated_fix_record",
        "escalation_report",
        "redaction_report",
        "token_and_cost_usage",
        "manifests",
        "workspace_path",
        "target_environment",
        "current_node",
        "pull_request_url",
        "pull_request_branch",
        "publish",
        "budget_snapshot",
        "terminal_reason",
        "sandbox_id",
        "result_id",
        "active_patch_id",
        "audit_id",
        "failure_fingerprint",
        "correlation",
    }
    out: dict[str, Any] = {}
    ephemeral = {"validation_retryable"}
    for key, value in state.items():
        if key in ephemeral:
            continue
        if key in skip_if_none and value is None:
            continue
        out[key] = value
    repo = dict(out.get("repository") or {})
    if repo.get("clone_url") is None:
        repo.pop("clone_url", None)
    out["repository"] = repo
    return out
