from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

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
    except (ProtocolValidationError, JSONDecodeError) as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=422)
    return JSONResponse({"valid": True, "kind": envelope["kind"]})


async def choose_next_action(request: Request) -> JSONResponse:
    try:
        job_envelope = await _json_body(request)
        action = get_schemas().choose_next_action(job_envelope)
    except (ProtocolValidationError, JSONDecodeError) as exc:
        return JSONResponse({"valid": False, "error": str(exc)}, status_code=422)
    return JSONResponse(action)


app = Starlette(
    debug=False,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/v1/validate", validate, methods=["POST"]),
        Route("/v1/choose-next-action", choose_next_action, methods=["POST"]),
    ],
)


def main() -> None:
    import os

    import uvicorn

    uvicorn.run(
        "raphael_dispatch.app:app",
        host=os.getenv("DISPATCH_HOST", "127.0.0.1"),
        port=int(os.getenv("DISPATCH_PORT", "8092")),
    )
