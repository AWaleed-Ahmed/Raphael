"""Owned qualification dispatcher: deny renewal only after real static work starts."""
from datetime import timedelta
import os
from pathlib import Path

from dispatch_server import hooks, TraceMiddleware
from raphael_dispatch.app import create_app
from raphael_dispatch.orchestrator import Orchestrator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn


class SlowValidation(Orchestrator):
    def _claim_action(self, state, connector_id):
        if state["dispatch"].get("pending_action", {}).get("payload", {}).get("verb") == "run_validation":
            state["budget_snapshot"]["deadline_at"] = (self.clock() + timedelta(seconds=94)).isoformat()
        return super()._claim_action(state, connector_id)

    @staticmethod
    def _validation_args(state):
        return {"plan": {"commands": [os.environ["E2E_SLOW_COMMAND"]], "health_checks": []}}


class DenyRenewal(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path.endswith("/lease") and Path(os.environ["E2E_SLOW_STARTED"]).exists():
            Path(os.environ["E2E_DENIAL_FILE"]).write_text("renewal denied during static validation\n")
            return JSONResponse({"error": "owned renewal denial fixture"}, status_code=409)
        return await call_next(request)


app = create_app(SlowValidation(hooks=hooks))
app.add_middleware(DenyRenewal)
app.add_middleware(TraceMiddleware)
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8092)
