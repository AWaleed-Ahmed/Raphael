from __future__ import annotations

import json
from json import JSONDecodeError
from datetime import datetime, timezone
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .orchestrator import OrchestrationError, Orchestrator
from .protocol import ProtocolValidationError, get_schemas
from .auth import AuthError, principal_from_request


def health(_: Request) -> JSONResponse:
    schemas = get_schemas()
    return JSONResponse(
        {
            "status": "ok",
            "service": "raphael-dispatch",
            "protocol_version": "1.0",
            "contracts_version": schemas.version,
            "schemas_loaded": sorted(schemas.schemas),
        }
    )


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        value = json.loads(await request.body())
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolValidationError("request body must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolValidationError("request body must be a JSON object")
    return value


async def validate(request: Request) -> JSONResponse:
    try:
        envelope = await _json_body(request)
        get_schemas().validate_envelope(envelope)
    except ProtocolValidationError as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=422)
    return JSONResponse({"valid": True, "kind": envelope["kind"]})


def _error(exc: Exception) -> JSONResponse:
    return JSONResponse({"valid": False, "error": str(exc)}, status_code=422)


async def intake_job(request: Request) -> JSONResponse:
    try:
        result = request.app.state.orchestrator.intake(await _json_body(request))
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
    return JSONResponse(result)


async def receive_result(request: Request) -> JSONResponse:
    try:
        envelope = await _json_body(request)
        if request.headers.get("authorization"):
            principal = principal_from_request(request.headers.get("authorization"), "connector")
            job_id = envelope.get("payload", {}).get("job_id")
            state = request.app.state.orchestrator.jobs.get(job_id)
            if state is None or state.get("tenant_id") != principal.tenant_id:
                return JSONResponse({"valid": False, "error": "tenant does not own job"}, status_code=403)
        result = request.app.state.orchestrator.receive_result(envelope)
    except (ProtocolValidationError, OrchestrationError, AuthError) as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=getattr(exc, "status_code", 422))
    return JSONResponse(result)


async def reap_leases(request: Request) -> JSONResponse:
    try:
        terminals = request.app.state.orchestrator.reap_expired()
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
    return JSONResponse({"terminals": terminals})


async def choose_next_action(request: Request) -> JSONResponse:
    """Compatibility endpoint backed by the real intake state machine."""
    try:
        result = request.app.state.orchestrator.intake(await _json_body(request))
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
    messages = result.get("messages") or []
    if not messages:
        return JSONResponse({"valid": True, "messages": [], "idempotent_replay": True})
    return JSONResponse(messages[0])


async def submit_tenant_job(request: Request) -> JSONResponse:
    try:
        principal = principal_from_request(request.headers.get("authorization"), "producer")
        if request.path_params["tenant_id"] != principal.tenant_id:
            return JSONResponse({"valid": False, "error": "tenant does not match bearer token"}, status_code=403)
        envelope = await _json_body(request)
        result = request.app.state.orchestrator.intake(envelope, tenant_id=principal.tenant_id)
        job_id = envelope["payload"]["job_id"]
        return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)
    except (ProtocolValidationError, OrchestrationError, AuthError, KeyError) as exc:
        status = getattr(exc, "status_code", 401) if isinstance(exc, AuthError) else 422
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=status)


async def next_tenant_job(request: Request) -> JSONResponse:
    try:
        principal = principal_from_request(request.headers.get("authorization"), "connector")
        if request.path_params["tenant_id"] != principal.tenant_id:
            return JSONResponse({"valid": False, "error": "tenant does not match bearer token"}, status_code=403)
        states = request.app.state.orchestrator.tenant_jobs(principal.tenant_id)
        if not states:
            return JSONResponse({"messages": [], "pending": False})
        state = min(states, key=lambda item: item.get("created_at") or item["run_id"])
        now = datetime.now(timezone.utc)
        claimed = request.app.state.claimed_jobs
        prior = claimed.get(state["run_id"])
        if prior:
            claimed_at = datetime.fromisoformat(prior["claimed_at"])
            ttl = int(state["dispatch"].get("lease_ttl_seconds") or 0)
            if ttl <= 0 or (now - claimed_at).total_seconds() <= ttl:
                return JSONResponse({"messages": [], "pending": False})
        claimed[state["run_id"]] = {"tenant_id": principal.tenant_id, "claimed_at": now.isoformat()}
        return JSONResponse({"messages": [state["dispatch"]["pending_action"]], "pending": True})
    except AuthError as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=getattr(exc, "status_code", 401))


def create_app(orchestrator: Orchestrator | None = None) -> Starlette:
    application = Starlette(
        debug=False,
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/v1/validate", validate, methods=["POST"]),
            Route("/v1/jobs", intake_job, methods=["POST"]),
            Route("/v1/tenants/{tenant_id}/jobs", submit_tenant_job, methods=["POST"]),
            Route("/v1/tenants/{tenant_id}/jobs/next", next_tenant_job, methods=["GET"]),
            Route("/v1/results", receive_result, methods=["POST"]),
            Route("/v1/leases/reap", reap_leases, methods=["POST"]),
            Route("/v1/choose-next-action", choose_next_action, methods=["POST"]),
        ],
    )
    application.state.orchestrator = orchestrator or Orchestrator()
    application.state.claimed_jobs: dict[str, dict[str, str]] = {}
    return application


app = create_app()


def main() -> None:
    import os

    import uvicorn

    uvicorn.run(
        "raphael_dispatch.app:app",
        host=os.getenv("DISPATCH_HOST", "127.0.0.1"),
        port=int(os.getenv("DISPATCH_PORT", "8092")),
    )
