from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .orchestrator import OrchestrationError, Orchestrator
from .protocol import ProtocolValidationError, get_schemas


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
        result = request.app.state.orchestrator.receive_result(await _json_body(request))
    except (ProtocolValidationError, OrchestrationError) as exc:
        return _error(exc)
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


def create_app(orchestrator: Orchestrator | None = None) -> Starlette:
    application = Starlette(
        debug=False,
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/v1/validate", validate, methods=["POST"]),
            Route("/v1/jobs", intake_job, methods=["POST"]),
            Route("/v1/results", receive_result, methods=["POST"]),
            Route("/v1/leases/reap", reap_leases, methods=["POST"]),
            Route("/v1/choose-next-action", choose_next_action, methods=["POST"]),
        ],
    )
    application.state.orchestrator = orchestrator or Orchestrator()
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
