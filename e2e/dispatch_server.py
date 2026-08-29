"""Run dispatch as a real process with deterministic E2E AgentHooks."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "dispatch"), str(ROOT / "agent")]

from raphael_dispatch.app import create_app  # noqa: E402
from raphael_dispatch.orchestrator import AgentHooks, Orchestrator  # noqa: E402
import uvicorn  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

FIXTURE_YAML = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    spec:
      containers:
        - name: app
          ports:
            - containerPort: 8080
          readinessProbe:
            httpGet:
              path: /healthz
              port: 9090
"""

HEALTHY_YAML = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  labels:
    raphael.scenario/state: healthy
spec:
  template:
    spec:
      containers:
        - name: app
          ports:
            - containerPort: 8080
"""


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        body = await request.body()
        response = await call_next(request)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        payload = b"".join(chunks)
        with open(os.environ.get("E2E_TRACE_FILE", "e2e-dispatch-trace.jsonl"), "a", encoding="utf-8") as stream:
            import json
            stream.write(json.dumps({"request": {"method": request.method, "path": request.url.path, "body": body.decode(errors="replace")}, "response": {"status": response.status_code, "body": payload.decode(errors="replace")}}) + "\n")
        from starlette.responses import Response
        return Response(payload, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)


def diagnose(state: dict) -> dict:
    return {"diagnosis": {"root_cause": "e2e fixture probe_port_mismatch", "confidence": 1.0}}


def localize(state: dict) -> dict:
    existing = state.get("narrowed_location") or {}
    return {
        "narrowed_location": {"file_path": "deploy/manifests/app.yaml", "line_start": existing.get("line_start", 1)},
        "manifests": {"type": "yaml", "path": "deploy/manifests/app.yaml"},
    }


def patch(state: dict) -> dict:
    line_start = (state.get("narrowed_location") or {}).get("line_start", 1)
    failing = line_start == 2
    content = FIXTURE_YAML if failing else HEALTHY_YAML
    attempt = int((state.get("attempt_count") or {}).get("patch", 0)) + 1
    candidate = {
        "patch_id": f"e2e-patch-{state['run_id']}-{attempt}",
        "attempt": attempt,
        "files": [{"path": "deploy/manifests/app.yaml", "action": "update", "content": content}],
    }
    attempts = dict(state.get("attempt_count") or {"diagnosis": 0, "patch": 0})
    attempts["patch"] = attempt
    return {
        "candidate_patches": [candidate],
        "active_patch_id": candidate["patch_id"],
        "attempt_count": attempts,
    }


def publish(state: dict) -> dict:
    return {"publish": {"ok": True, "dry_run": True}}


hooks = AgentHooks(diagnose=diagnose, localize=localize, patch=patch, publish=publish)
app = create_app(Orchestrator(hooks=hooks))
app.add_middleware(TraceMiddleware)


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("DISPATCH_HOST", "127.0.0.1"), port=int(os.getenv("DISPATCH_PORT", "8092")))
