from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from json import JSONDecodeError
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .orchestrator import ActionCompleted, OrchestrationError, Orchestrator
from .protocol import ProtocolValidationError, get_schemas
from .auth import AuthError, principal_from_request


def lease_reap_interval_seconds() -> float:
    """Return a bounded, configurable cadence for automatic abandoned-job cleanup."""
    raw = os.environ.get("RAPHAEL_LEASE_REAP_INTERVAL_SECONDS", "10")
    try:
        return max(0.1, float(raw))
    except ValueError:
        return 10.0


@asynccontextmanager
async def dispatch_lifespan(application: Starlette):
    """Restore persisted routing before serving, then continuously reap expired leases."""
    orchestrator = application.state.orchestrator
    orchestrator.rehydrate()

    async def reap_loop() -> None:
        while True:
            await asyncio.sleep(lease_reap_interval_seconds())
            await asyncio.to_thread(orchestrator.reap_expired)

    task = asyncio.create_task(reap_loop(), name="raphael-dispatch-lease-reaper")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


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
    return JSONResponse({"valid": False, "error": str(exc)}, status_code=getattr(exc, "status_code", 422))


async def intake_job(request: Request) -> JSONResponse:
    try:
        result = await asyncio.to_thread(request.app.state.orchestrator.intake, await _json_body(request))
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
    return JSONResponse(result)


async def receive_result(request: Request) -> JSONResponse:
    try:
        principal = principal_from_request(request.headers.get("authorization"), "connector")
        envelope = await _json_body(request)
        get_schemas().validate_envelope(envelope)
        job_id = envelope.get("payload", {}).get("job_id")
        state = request.app.state.orchestrator.jobs.get(job_id)
        if state is None or state.get("tenant_id") != principal.tenant_id:
            return JSONResponse({"valid": False, "error": "tenant does not own job"}, status_code=403)
        # Graph hooks can block for seconds (for example model-backed diagnosis).
        # Keep the event loop available to authenticate and process lease heartbeats.
        result = await asyncio.to_thread(
            request.app.state.orchestrator.receive_result, envelope, principal.connector_id
        )
        if result.get("claim"):
            result["claim"] = request.app.state.orchestrator.public_claim(result["claim"])
    except AuthError as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=getattr(exc, "status_code", 401))
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
    return JSONResponse(result)


async def reap_leases(request: Request) -> JSONResponse:
    try:
        terminals = await asyncio.to_thread(request.app.state.orchestrator.reap_expired)
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
    return JSONResponse({"terminals": terminals})


async def choose_next_action(request: Request) -> JSONResponse:
    """Compatibility endpoint backed by the real intake state machine."""
    try:
        result = await asyncio.to_thread(request.app.state.orchestrator.intake, await _json_body(request))
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
        result = await asyncio.to_thread(request.app.state.orchestrator.intake, envelope, tenant_id=principal.tenant_id)
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
        result = await asyncio.to_thread(
            request.app.state.orchestrator.next_tenant_action, principal.tenant_id, principal.connector_id
        )
        return JSONResponse(result)
    except AuthError as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=getattr(exc, "status_code", 401))


async def renew_tenant_job_lease(request: Request) -> JSONResponse:
    try:
        principal = principal_from_request(request.headers.get("authorization"), "connector")
        if request.path_params["tenant_id"] != principal.tenant_id:
            return JSONResponse({"valid": False, "error": "tenant does not match bearer token"}, status_code=403)
        body = await _json_body(request)
        get_schemas().validate_payload("lease_renewal", body)
        result = await asyncio.to_thread(
            request.app.state.orchestrator.renew_action_lease,
            principal.tenant_id, request.path_params["job_id"], body, principal.connector_id
        )
        return JSONResponse(request.app.state.orchestrator.public_claim(result))
    except AuthError as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=getattr(exc, "status_code", 401))
    except ActionCompleted as exc:
        return JSONResponse({"valid": False, "error": str(exc), "code": "action_completed", "claim": exc.claim}, status_code=409)
    except OrchestrationError as exc:
        status = 403 if "tenant" in str(exc) else 409
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=status)
    except ProtocolValidationError as exc:
        return _error(exc)


def create_app(orchestrator: Orchestrator | None = None) -> Starlette:
    application = Starlette(
        debug=False,
        lifespan=dispatch_lifespan,
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/v1/validate", validate, methods=["POST"]),
            Route("/v1/jobs", intake_job, methods=["POST"]),
            Route("/v1/tenants/{tenant_id}/jobs", submit_tenant_job, methods=["POST"]),
            Route("/v1/tenants/{tenant_id}/jobs/next", next_tenant_job, methods=["GET"]),
            Route("/v1/tenants/{tenant_id}/jobs/{job_id}/lease", renew_tenant_job_lease, methods=["POST"]),
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
