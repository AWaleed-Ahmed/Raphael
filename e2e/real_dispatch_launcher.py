"""Launch dispatch with REAL default hooks + trace middleware for observability."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "dispatch"), str(ROOT / "agent")]

from e2e.trace_redaction import redacted_body  # noqa: E402

from raphael_dispatch.app import create_app  # noqa: E402
from raphael_dispatch.orchestrator import Orchestrator  # noqa: E402
import uvicorn  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        body = await request.body()
        response = await call_next(request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        payload = b"".join(chunks)
        trace_path = os.environ.get("E2E_TRACE_FILE", "real-job-trace.jsonl")
        with open(trace_path, "a", encoding="utf-8") as stream:
            import json
            stream.write(json.dumps({
                "request": {"method": request.method, "path": request.url.path, "body": redacted_body(body)},
                "response": {"status": response.status_code, "body": redacted_body(payload)},
            }) + "\n")
        from starlette.responses import Response
        return Response(payload, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)


# Production defaults — NO hook overrides
app = create_app(Orchestrator())
app.add_middleware(TraceMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("DISPATCH_HOST", "127.0.0.1"), port=int(os.getenv("DISPATCH_PORT", "8092")))
