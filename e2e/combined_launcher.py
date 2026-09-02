"""Combined launcher: agent HTTP API + dispatch orchestrator in one process.

Mounts the agent's webhook endpoints and dispatch's job queue endpoints
on the same Starlette app so the ingest bridge can call the orchestrator
in-process while also serving webhook HTTP requests.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "dispatch"), str(ROOT / "agent")]

from starlette.applications import Starlette  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.routing import Mount  # noqa: E402
import uvicorn  # noqa: E402


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        body = await request.body()
        response = await call_next(request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        payload = b"".join(chunks)
        trace_path = os.environ.get("E2E_TRACE_FILE", "full-chain-trace.jsonl")
        with open(trace_path, "a", encoding="utf-8") as stream:
            import json
            stream.write(json.dumps({
                "request": {"method": request.method, "path": request.url.path, "body": body.decode(errors="replace")},
                "response": {"status": response.status_code, "body": payload.decode(errors="replace")},
            }) + "\n")
        from starlette.responses import Response
        return Response(payload, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)


# Build dispatch app with real hooks
from raphael_dispatch.app import create_app as create_dispatch_app  # noqa: E402
from raphael_dispatch.orchestrator import Orchestrator  # noqa: E402

dispatch_app = create_dispatch_app(Orchestrator())

# Wire the bridge to use the SAME orchestrator instance as the HTTP endpoints.
from raphael_agent.ingest.dispatch_bridge import set_orchestrator  # noqa: E402
set_orchestrator(dispatch_app.state.orchestrator)

# Build agent app
from raphael_agent.http_api.app import app as agent_app  # noqa: E402

# Combine: agent routes at /, dispatch routes also at /
# Since both use /health and different /v1/* paths, we merge routes
combined = Starlette(
    debug=False,
    routes=list(agent_app.routes) + list(dispatch_app.routes),
)
combined.state.orchestrator = dispatch_app.state.orchestrator
combined.state.claimed_jobs = dispatch_app.state.claimed_jobs

combined.add_middleware(TraceMiddleware)

if __name__ == "__main__":
    port = int(os.getenv("DISPATCH_PORT", "8092"))
    uvicorn.run(combined, host=os.getenv("DISPATCH_HOST", "127.0.0.1"), port=port)
