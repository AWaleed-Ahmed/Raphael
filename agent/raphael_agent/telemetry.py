"""Redacted, normalized local telemetry for model calls and run outcomes."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

from raphael_agent.evidence.redaction import redact_text
from raphael_agent.schema_util import validate_agent
from raphael_agent.timeutil import utc_now


def _data_dir() -> Path:
    return Path(os.environ.get("RAPHAEL_AGENT_DATA_DIR", ".raphael-agent-data"))


def _excerpt(value: Any, limit: int = 2000) -> str | None:
    if value is None:
        return None
    text, _notes = redact_text(str(value))
    return text[:limit]


def _sha(value: Any) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _identity(run: dict[str, Any]) -> tuple[str, str]:
    client = str(run.get("client_name") or os.environ.get("RAPHAEL_CLIENT_NAME") or "local")
    repo = run.get("repository") or {}
    project = str(repo.get("name") or os.environ.get("RAPHAEL_PROJECT_NAME") or "unknown")
    return client, project


def record_event(event: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    normalized = dict(event)
    normalized.setdefault("event_id", f"telemetry-{uuid.uuid4().hex[:16]}")
    normalized.setdefault("recorded_at", utc_now())
    normalized.setdefault("client_name", "local")
    normalized.setdefault("project_name", "unknown")
    for key in ("input_excerpt", "output_excerpt"):
        normalized[key] = _excerpt(normalized.get(key))
    validate_agent("telemetry_event.json", normalized)
    target = (root or _data_dir()) / "telemetry.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, sort_keys=True) + "\n")
    return normalized


def record_model_call(
    run: dict[str, Any],
    *,
    model_name: str,
    model_version: str,
    input_payload: Any,
    output_payload: Any = None,
    success: bool,
    token_usage: dict[str, Any] | None = None,
    error_type: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    client, project = _identity(run)
    input_text = json.dumps(input_payload, sort_keys=True, default=str)
    output_text = None if output_payload is None else json.dumps(output_payload, sort_keys=True, default=str)
    return record_event({
        "event_type": "model_call",
        "run_id": str(run.get("run_id") or "unknown"),
        "client_name": client,
        "project_name": project,
        "repository": run.get("repository"),
        "model_name": model_name,
        "model_version": model_version,
        "success": success,
        "input_excerpt": input_text,
        "output_excerpt": output_text,
        "input_sha256": _sha(input_text),
        "output_sha256": _sha(output_text),
        "token_usage": token_usage,
        "error_type": error_type,
    }, root=root)


def record_run_outcome(run: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    client, project = _identity(run)
    return record_event({
        "event_type": "run_outcome",
        "run_id": str(run.get("run_id") or "unknown"),
        "client_name": client,
        "project_name": project,
        "repository": run.get("repository"),
        "status": run.get("status"),
        "success": str(run.get("status") or "") in {"success_draft_pr_ready", "success_fix_proposed"},
    }, root=root)
