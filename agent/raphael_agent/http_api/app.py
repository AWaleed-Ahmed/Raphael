"""HTTP entrypoints for GitHub webhooks (Phase 1)."""

from __future__ import annotations

import json
import os
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from raphael_agent.timeutil import utc_now
from raphael_agent.ingest import (
    WebhookAuthError,
    accept_normalized_event,
    parse_github_webhook,
    should_auto_run_graph,
)
from raphael_agent.ingest.policy import IngestPolicyConfig
from raphael_agent.store import RunStore


def _store() -> RunStore:
    return RunStore()


def _ignored_trigger_kind(event_name: str) -> str:
    return {
        "workflow_run": "github_workflow_run",
        "check_run": "github_check_run",
        "deployment_status": "github_deployment_status",
    }.get(event_name, "manual")


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "raphael-agent", "phase": 4})


async def metrics(_: Request) -> JSONResponse:
    from raphael_agent.metrics import summarize_store

    return JSONResponse(summarize_store(_store()))


async def github_webhook(request: Request) -> JSONResponse:
    body = await request.body()
    event_name = request.headers.get("x-github-event", "")
    delivery_id = request.headers.get("x-github-delivery")
    signature = request.headers.get("x-hub-signature-256")

    try:
        seed, ignore_reason = parse_github_webhook(
            body,
            event_name=event_name,
            delivery_id=delivery_id,
            signature_header=signature,
        )
    except WebhookAuthError as exc:
        decision = {
            "decision": "unauthorized",
            "event_id": delivery_id or "unknown",
            "fingerprint": "unauthorized",
            "decided_at": utc_now(),
            "reason": str(exc),
        }
        _store().append_decision(decision)
        return JSONResponse(decision, status_code=401)
    except ValueError as exc:
        return JSONResponse(
            {
                "decision": "invalid",
                "event_id": delivery_id or "unknown",
                "fingerprint": "invalid",
                "decided_at": utc_now(),
                "reason": str(exc),
            },
            status_code=400,
        )

    if seed is None:
        decision = {
            "decision": "ignored",
            "event_id": delivery_id or f"{event_name}:ignored",
            "fingerprint": f"ignored|{event_name}",
            "decided_at": utc_now(),
            "reason": ignore_reason or "event ignored",
            "trigger_kind": _ignored_trigger_kind(event_name),
        }
        _store().append_decision(decision)
        return JSONResponse(decision, status_code=202)

    try:
        payload_obj: dict[str, Any] = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload_obj = {"raw": "unparsed"}

    sandbox_mode = os.environ.get("RAPHAEL_AGENT_SANDBOX_MODE", "skipped")
    store = _store()

    if should_auto_run_graph():
        mode = sandbox_mode if sandbox_mode != "skipped" else "recorded_stub"
        decision, run = accept_normalized_event(
            seed,
            store=store,
            policy=IngestPolicyConfig.from_env(),
            raw_payload=payload_obj,
            sandbox_mode=mode,
        )
        if run is not None:
            from raphael_agent.graph import run_stub_graph

            final = run_stub_graph(run)
            store.save_run(dict(final))
            return JSONResponse(
                {
                    "ingest": decision,
                    "run_id": final.get("run_id"),
                    "status": final.get("status"),
                }
            )
        return JSONResponse({"ingest": decision}, status_code=202)

    decision, run = accept_normalized_event(
        seed,
        store=store,
        policy=IngestPolicyConfig.from_env(),
        raw_payload=payload_obj,
        sandbox_mode=sandbox_mode,
    )
    body_out: dict[str, Any] = {"ingest": decision}
    if run is not None:
        body_out["run_id"] = run["run_id"]
        body_out["status"] = run["status"]
    return JSONResponse(body_out, status_code=202)


async def get_run(request: Request) -> JSONResponse:
    run_id = request.path_params["run_id"]
    run = _store().get_run(run_id)
    if run is None:
        return JSONResponse({"error": "not_found", "run_id": run_id}, status_code=404)
    return JSONResponse(run)


def create_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/v1/metrics", metrics, methods=["GET"]),
            Route("/v1/webhooks/github", github_webhook, methods=["POST"]),
            Route("/v1/runs/{run_id}", get_run, methods=["GET"]),
        ]
    )


app = create_app()


def main() -> None:
    import uvicorn

    listen = os.environ.get("RAPHAEL_AGENT_LISTEN", "127.0.0.1:8091")
    host, _, port_s = listen.partition(":")
    uvicorn.run(
        "raphael_agent.http_api.app:app",
        host=host or "127.0.0.1",
        port=int(port_s or "8091"),
        reload=False,
    )


if __name__ == "__main__":
    main()
