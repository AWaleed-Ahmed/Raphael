"""Raphael-core production entrypoint.

Runs the agent webhook server and dispatch orchestrator in a single process,
sharing one Orchestrator instance. This is the intended deployment model:
agent and dispatch are one trust domain (raphael-core), opposed to the
external Ignis executor which runs separately.

Usage:
    python run.py

Configuration:
    RAPHAEL_AGENT_LISTEN  Host:port for the combined server (default 127.0.0.1:8091)
    RAPHAEL_DISPATCH_BRIDGE_ENABLED  Set to "1" to enable ingest→dispatch bridge

Multi-process / multi-instance deployment is explicitly deferred future work.
See handoff.md and D-20260830-01 for context. Do not run multiple instances
of this entrypoint without first implementing startup rehydration and durable
lease ownership (tracked separately).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "dispatch"), str(ROOT / "agent")]


def create_app():
    """Build the combined agent + dispatch Starlette application.

    Creates ONE Orchestrator instance shared by:
    - The dispatch HTTP endpoints (/v1/tenants/*/jobs/next, /v1/results, etc.)
    - The ingest→dispatch bridge (same-process Python call, no HTTP)
    - The agent webhook endpoints (/v1/webhooks/github, etc.)
    """
    from starlette.applications import Starlette
    from starlette.routing import Mount

    # 1. Create the orchestrator — single source of truth for job state
    from raphael_dispatch.orchestrator import Orchestrator
    from raphael_dispatch.app import create_app as create_dispatch_app, dispatch_lifespan

    orchestrator = Orchestrator()
    dispatch_app = create_dispatch_app(orchestrator)

    # 2. Wire the bridge to use THIS orchestrator instance explicitly.
    #    Without this, the bridge would fail loudly (by design) because
    #    it refuses to create its own implicit singleton.
    from raphael_agent.ingest.dispatch_bridge import set_orchestrator
    set_orchestrator(orchestrator)

    # 3. Build the agent app (webhook handlers, metrics, etc.)
    from raphael_agent.http_api.app import app as agent_app

    # 4. Combine routes from both apps onto one Starlette instance
    combined = Starlette(
        debug=False,
        routes=list(agent_app.routes) + list(dispatch_app.routes),
        lifespan=dispatch_lifespan,
    )
    combined.state.orchestrator = orchestrator
    combined.state.claimed_jobs = dispatch_app.state.claimed_jobs

    # Optional trace middleware for debugging (active when E2E_TRACE_FILE is set)
    trace_path = os.environ.get("E2E_TRACE_FILE")
    if trace_path:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import Response as StarletteResponse

        class _TraceMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                body = await request.body()
                response = await call_next(request)
                chunks = []
                async for chunk in response.body_iterator:
                    chunks.append(chunk)
                payload = b"".join(chunks)
                with open(trace_path, "a", encoding="utf-8") as stream:
                    import json as _json
                    stream.write(_json.dumps({
                        "request": {"method": request.method, "path": request.url.path, "body": body.decode(errors="replace")},
                        "response": {"status": response.status_code, "body": payload.decode(errors="replace")},
                    }) + "\n")
                return StarletteResponse(payload, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)

        combined.add_middleware(_TraceMiddleware)

    return combined


def main():
    import uvicorn

    listen = os.environ.get("RAPHAEL_AGENT_LISTEN", "127.0.0.1:8091")
    if ":" in listen:
        host, port_str = listen.rsplit(":", 1)
        port = int(port_str)
    else:
        host = listen
        port = 8091

    app = create_app()
    print(f"Raphael-core listening on {host}:{port}")
    print(f"  Agent webhooks: http://{host}:{port}/v1/webhooks/github")
    print(f"  Dispatch queue: http://{host}:{port}/v1/tenants/{{tenant_id}}/jobs/next")
    print(f"  Health:         http://{host}:{port}/health")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
