"""Real dispatch, with a test-only barrier before consuming deploy results.

The barrier keeps terminal cleanup from racing the independent Kubernetes
inspection. No actions, results, or hooks are replaced or fabricated.
"""
import asyncio
import json
import os
import time
from pathlib import Path

import uvicorn
from starlette.middleware.base import BaseHTTPMiddleware
from real_dispatch_launcher import app


class InspectDeployment(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/v1/results":
            body = json.loads(await request.body())
            payload = body.get("payload", {})
            if payload.get("verb") == "deploy_revision":
                gate = Path(os.environ["E2E_INSPECT_GATE"])
                gate.with_suffix(".received.json").write_text(json.dumps(body), encoding="utf-8")
                deadline = time.monotonic() + 180
                while not gate.exists():
                    if time.monotonic() > deadline:
                        raise TimeoutError("Kubernetes inspection did not release deploy-result barrier")
                    await asyncio.sleep(0.1)
        return await call_next(request)


app.add_middleware(InspectDeployment)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8092)
