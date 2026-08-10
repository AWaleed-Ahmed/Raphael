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
    verify_github_signature,
)
from raphael_agent.ingest.policy import IngestPolicyConfig
from raphael_agent.store import open_run_store


def _store():
    return open_run_store()


def _ignored_trigger_kind(event_name: str) -> str:
    return {
        "workflow_run": "github_workflow_run",
        "check_run": "github_check_run",
        "deployment_status": "github_deployment_status",
        "issues": "github_issue",
    }.get(event_name, "manual")


async def health(_: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "service": "raphael-agent", "phase": "phase6-dual-path"})


async def metrics(_: Request) -> JSONResponse:
    from raphael_agent.metrics import summarize_store

    return JSONResponse(summarize_store(_store()))


async def go_nogo(_: Request) -> JSONResponse:
    from raphael_agent.guardrails import go_nogo_verdict

    verdict = go_nogo_verdict()
    return JSONResponse(verdict, status_code=200 if verdict["go"] else 409)


async def post_feedback(request: Request) -> JSONResponse:
    from raphael_agent.feedback import default_feedback_recorder, normalize_feedback_event

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body_must_be_object"}, status_code=400)
    try:
        body = dict(body)
        body.setdefault("source", "http")
        event = normalize_feedback_event(body)
        recorded = default_feedback_recorder().record(event)
    except ValueError as exc:
        return JSONResponse({"error": "invalid_feedback", "message": str(exc)}, status_code=400)
    return JSONResponse(recorded, status_code=201)


async def github_webhook(request: Request) -> JSONResponse:
    body = await request.body()
    event_name = request.headers.get("x-github-event", "")
    delivery_id = request.headers.get("x-github-delivery")
    signature = request.headers.get("x-hub-signature-256")

    # FR-065: pull_request outcomes → feedback jsonl (still HMAC-checked).
    if event_name == "pull_request":
        from raphael_agent.feedback import (
            default_feedback_recorder,
            feedback_from_pull_request_webhook,
        )

        try:
            verify_github_signature(body, signature)
            payload = json.loads(body.decode("utf-8"))
        except WebhookAuthError as exc:
            return JSONResponse({"error": "unauthorized", "message": str(exc)}, status_code=401)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            return JSONResponse({"error": "invalid", "message": str(exc)}, status_code=400)
        event = feedback_from_pull_request_webhook(payload if isinstance(payload, dict) else {})
        if event is None:
            return JSONResponse(
                {"decision": "ignored", "reason": "pull_request action not mapped"},
                status_code=202,
            )
        event["raw_ref"] = _store().save_raw_event(
            delivery_id or event["event_id"], payload
        )
        recorded = default_feedback_recorder().record(event)
        return JSONResponse({"feedback": recorded}, status_code=202)

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


async def k8s_webhook(request: Request) -> JSONResponse:
    """FR-002: accept workload-health failure events (sidecar / file forwarder)."""
    from raphael_agent.ingest.k8s_watcher import k8s_watcher_enabled, normalize_k8s_workload

    if not k8s_watcher_enabled():
        return JSONResponse(
            {
                "decision": "ignored",
                "reason": "RAPHAEL_K8S_WATCHER is off (set to 1 to enable)",
                "trigger_kind": "k8s_workload",
            },
            status_code=202,
        )
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    if not isinstance(payload, dict):
        return JSONResponse({"error": "body_must_be_object"}, status_code=400)

    store = _store()
    delivery_id = request.headers.get("x-raphael-delivery") or f"k8s-{utc_now()}"
    try:
        seed = normalize_k8s_workload(
            payload,
            raw_ref=f"k8s:{delivery_id}",
            received_at=utc_now(),
        )
    except ValueError as exc:
        decision = {
            "decision": "ignored",
            "event_id": delivery_id,
            "fingerprint": f"ignored|k8s_workload",
            "decided_at": utc_now(),
            "reason": str(exc),
            "trigger_kind": "k8s_workload",
        }
        store.append_decision(decision)
        return JSONResponse(decision, status_code=202)

    sandbox_mode = os.environ.get("RAPHAEL_AGENT_SANDBOX_MODE", "skipped")
    if should_auto_run_graph():
        mode = sandbox_mode if sandbox_mode != "skipped" else "recorded_stub"
        decision, run = accept_normalized_event(
            seed,
            store=store,
            policy=IngestPolicyConfig.from_env(),
            raw_payload=payload,
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
        raw_payload=payload,
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
            Route("/v1/pilot/go-nogo", go_nogo, methods=["GET"]),
            Route("/v1/feedback", post_feedback, methods=["POST"]),
            Route("/v1/webhooks/github", github_webhook, methods=["POST"]),
            Route("/v1/webhooks/k8s", k8s_webhook, methods=["POST"]),
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
