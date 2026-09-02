"""Bridge from ingest to dispatch orchestrator.

Translates a normalized ingest seed into a dispatch job envelope and submits
it via direct Python method call on the Orchestrator instance. No HTTP, no
bearer token — ingest and dispatch share the same process and trust domain.
Auth on the dispatch HTTP endpoints exists for *external* callers (connectors,
producers) crossing a network trust boundary; that boundary does not apply
to same-process calls within raphael-core. Do not add an internal token here.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any


def bridge_enabled() -> bool:
    return os.environ.get("RAPHAEL_DISPATCH_BRIDGE_ENABLED", "0").strip() in {
        "1",
        "true",
        "yes",
    }


def _default_file_path() -> str:
    return os.environ.get("RAPHAEL_BRIDGE_DEFAULT_FILE_PATH", ".").strip() or "."


def build_job_envelope(seed: dict[str, Any]) -> dict[str, Any] | None:
    """Construct a dispatch job envelope from an ingest seed.

    Returns None if the seed lacks required fields (e.g. clone_url).
    The caller should record the skip reason and fall back to existing
    behavior rather than crashing the webhook response.
    """
    repository = seed.get("repository") or {}
    clone_url = repository.get("clone_url")
    if not clone_url:
        return None

    commit_sha = seed.get("commit_sha")
    if not commit_sha:
        return None

    correlation = seed.get("correlation") or {}
    config_path = correlation.get("deployment_config_path")
    file_path = config_path if config_path else _default_file_path()
    narrowed_location_source = "correlation" if config_path else "default"

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    envelope: dict[str, Any] = {
        "protocol_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "job_id": job_id,
        "kind": "job",
        "sent_at": now,
        "payload": {
            "job_id": job_id,
            "repository": {"clone_url": str(clone_url)},
            "commit_sha": str(commit_sha),
            "narrowed_location": {"file_path": str(file_path)},
        },
    }

    # Attach bridge metadata to the seed's run record (not the envelope,
    # which has additionalProperties: false). The caller stores these on
    # the run dict so run_id and dispatch_job_id are correlatable.
    seed["_bridge_metadata"] = {
        "dispatch_job_id": job_id,
        "narrowed_location_source": narrowed_location_source,
    }

    return envelope


def submit_to_dispatch(
    seed: dict[str, Any],
    run: dict[str, Any],
) -> dict[str, Any]:
    """Submit an accepted ingest event to the dispatch orchestrator.

    Returns a result dict with 'submitted' (bool) and optional 'reason'.
    Never raises — failures are returned as {'submitted': False, 'reason': ...}
    so the webhook handler can fall back to existing behavior.
    """
    envelope = build_job_envelope(seed)
    if envelope is None:
        missing = []
        repo = seed.get("repository") or {}
        if not repo.get("clone_url"):
            missing.append("clone_url")
        if not seed.get("commit_sha"):
            missing.append("commit_sha")
        return {
            "submitted": False,
            "reason": f"bridge_skipped: missing {', '.join(missing)}",
        }

    try:
        orchestrator = _get_orchestrator()
        tenant_id = seed.get("tenant_id", "local-dev")
        result = orchestrator.intake(envelope, tenant_id=tenant_id)

        # Store correlation metadata on the run record
        bridge_meta = seed.get("_bridge_metadata", {})
        run["dispatch_job_id"] = bridge_meta.get("dispatch_job_id")
        run["narrowed_location_source"] = bridge_meta.get(
            "narrowed_location_source", "default"
        )

        return {
            "submitted": True,
            "dispatch_job_id": bridge_meta.get("dispatch_job_id"),
            "intake_result": result,
        }
    except Exception as exc:  # noqa: BLE001
        return {"submitted": False, "reason": f"bridge_error: {exc}"}


_orchestrator_instance = None


def set_orchestrator(orchestrator) -> None:
    """Inject the Orchestrator instance the bridge should submit jobs to.

    Must be called at startup before any webhook can trigger the bridge.
    In the standard single-process deployment (run.py), this is called
    automatically during app creation. If you see a RuntimeError about
    the bridge not being wired, it means the entrypoint did not call
    this function — fix the startup code, do not add a fallback here.
    """
    global _orchestrator_instance
    _orchestrator_instance = orchestrator


def _get_orchestrator():
    """Return the wired Orchestrator instance, or raise if not yet wired."""
    if _orchestrator_instance is None:
        raise RuntimeError(
            "dispatch bridge not wired: set_orchestrator() was not called at startup. "
            "In the standard deployment (run.py), this happens automatically. "
            "If running agent and dispatch as separate processes, the bridge cannot "
            "work — use HTTP POST to /v1/tenants/{tenant_id}/jobs instead."
        )
    return _orchestrator_instance
