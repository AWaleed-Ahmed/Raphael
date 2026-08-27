from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from starlette.testclient import TestClient

from raphael_dispatch.app import create_app
from raphael_dispatch.orchestrator import AgentHooks, Orchestrator
from raphael_dispatch.protocol import PROTOCOL_VERSION, get_schemas
from raphael_agent.budgets import max_patch_attempts_budget
from raphael_agent.graph.nodes import node_diagnose, node_localize, node_patch, node_publish_or_escalate
from raphael_agent.store import RunStore


def envelope(kind: str, payload: dict, job_id: str | None = None) -> dict:
    value = {
        "protocol_version": PROTOCOL_VERSION,
        "message_id": str(uuid4()),
        "kind": kind,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    if job_id is not None:
        value["job_id"] = job_id
    return value


def job_envelope(*, lease_ttl_seconds: int = 60) -> dict:
    job_id = str(uuid4())
    return envelope(
        "job",
        {
            "job_id": job_id,
            "repository": {"clone_url": "https://github.com/example/service.git", "name": "service"},
            "commit_sha": "0123456789abcdef0123456789abcdef01234567",
            "narrowed_location": {"file_path": "deploy/deployment.yaml", "line_start": 12},
            "lease_ttl_seconds": lease_ttl_seconds,
        },
        job_id,
    )


def result_for(action: dict, *, status: str = "ok", result: dict | None = None, error: dict | None = None) -> dict:
    payload = {
        "job_id": action["payload"]["job_id"],
        "action_id": action["payload"]["action_id"],
        "verb": action["payload"]["verb"],
        "status": status,
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    return envelope("result", payload, action["payload"]["job_id"])


def create_result(job_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "sandbox_id": "sb-1",
        "namespace": "raphael-run",
        "status": "ready",
        "created_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
        "run_id": job_id,
        "cluster_backend": "mock",
    }


def fidelity() -> dict:
    return {
        "score": 1.0,
        "checklist": {
            "same_commit": True,
            "same_render_path": True,
            "same_image_digest_or_tag": True,
            "equivalent_non_secret_config": True,
            "dependencies_available": True,
        },
        "material_gaps": [],
    }


def deploy_result() -> dict:
    return {
        "sandbox_id": "sb-1",
        "status": "deployed",
        "rendered_artifact_ids": [],
        "fidelity": fidelity(),
        "deployed_at": datetime.now(timezone.utc).isoformat(),
    }


def observe_result() -> dict:
    return {
        "sandbox_id": "sb-1",
        "signature": {
            "class": "service_port_mismatch",
            "key": "probe_port_mismatch:service:8080!=9090",
            "normalized": {
                "reason": "readiness_probe_port",
                "resource_kind": "Deployment",
                "resource_name": "service",
            },
            "reproduced": True,
            "evidence_refs": [{"kind": "artifact", "id": "artifact-1"}],
            "observed_at": datetime.now(timezone.utc).isoformat(),
        },
        "artifact_ids": ["artifact-1"],
    }


def validation_result() -> dict:
    return {
        "sandbox_id": "sb-1",
        "passed": True,
        "checks": [{"name": "rollout", "kind": "rollout", "status": "passed", "duration_ms": 1}],
        "fail_closed": False,
        "full_validation": True,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def fake_diagnose(state: dict) -> dict:
    attempts = dict(state.get("attempt_count") or {})
    attempts["diagnosis"] = int(attempts.get("diagnosis") or 0) + 1
    return {
        "status": "running",
        "attempt_count": attempts,
        "diagnosis": {
            "classification": {"category": "supported", "failure_class": "probe_misconfiguration", "blocked_reason": None},
            "hypotheses": [],
            "selected_hypothesis_id": "hyp-probe-port",
            "confidence": 0.95,
            "confidence_threshold": 0.7,
        },
    }


def fake_localize(_: dict) -> dict:
    return {"localization_result": {"status": "localized", "candidates": []}}


def fake_publish(_: dict) -> dict:
    return {"status": "success_draft_pr_ready", "terminal_reason": "draft_pr_dry_run", "publish": {"ok": True, "dry_run": True}}


def fake_patch(state: dict) -> dict:
    attempts = dict(state.get("attempt_count") or {})
    attempts["patch"] = int(attempts.get("patch") or 0) + 1
    return {
        "status": "running",
        "attempt_count": attempts,
        "candidate_patches": [{"patch_id": f"patch-{attempts['patch']}", "policy_status": "allowed", "files": [{"path": "deploy/deployment.yaml", "content": "port: 8080\n"}]}],
        "active_patch_id": f"patch-{attempts['patch']}",
    }


def make_orchestrator(tmp_path: Path, *, clock=None) -> Orchestrator:
    return Orchestrator(
        store=RunStore(tmp_path),
        hooks=AgentHooks(diagnose=fake_diagnose, localize=fake_localize, patch=fake_patch, publish=fake_publish),
        clock=clock,
    )


def test_default_hooks_reuse_agent_nodes() -> None:
    hooks = AgentHooks()
    assert hooks.diagnose is node_diagnose
    assert hooks.localize is node_localize
    assert hooks.patch is node_patch
    assert hooks.publish is node_publish_or_escalate


def test_successful_multistep_job_reaches_fix_finalized(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path)
    job = job_envelope()
    messages = orchestrator.intake(job)["messages"]
    assert messages[0]["kind"] == "action"
    assert messages[0]["payload"]["verb"] == "create_sandbox"

    action = messages[0]
    messages = orchestrator.receive_result(result_for(action, result=create_result(job["payload"]["job_id"]))) ["messages"]
    assert messages[0]["payload"]["verb"] == "deploy_revision"
    messages = orchestrator.receive_result(result_for(messages[0], result=deploy_result()))["messages"]
    assert messages[0]["payload"]["verb"] == "observe_failure"
    messages = orchestrator.receive_result(result_for(messages[0], result=observe_result()))["messages"]
    assert messages[0]["payload"]["verb"] == "deploy_revision"
    messages = orchestrator.receive_result(result_for(messages[0], result=deploy_result()))["messages"]
    assert messages[0]["payload"]["verb"] == "run_validation"
    messages = orchestrator.receive_result(result_for(messages[0], result=validation_result()))["messages"]
    assert messages[0]["payload"]["verb"] == "finalize_result"
    messages = orchestrator.receive_result(result_for(messages[0]))["messages"]
    assert messages[0]["kind"] == "terminal"
    assert messages[0]["payload"]["final_status"] == "fix_finalized"


def test_patch_attempt_budget_escalates_without_looping(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAPHAEL_MAX_PATCH_ATTEMPTS", "1")
    orchestrator = make_orchestrator(tmp_path)
    job = job_envelope()
    action = orchestrator.intake(job)["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job["payload"]["job_id"]))) ["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=deploy_result()))["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=observe_result()))["messages"][0]
    failed = result_for(action, status="failed", error={"code": "internal_error", "message": "deploy rejected"})
    messages = orchestrator.receive_result(failed)["messages"]
    assert len(messages) == 1
    assert messages[0]["kind"] == "terminal"
    assert messages[0]["payload"]["final_status"] == "escalated"
    assert orchestrator.jobs[job["payload"]["job_id"]]["attempt_count"]["patch"] == 1
    assert max_patch_attempts_budget() == 1


def test_two_failed_patch_attempts_do_not_exhaust_three_attempt_budget(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAPHAEL_MAX_PATCH_ATTEMPTS", "3")
    orchestrator = make_orchestrator(tmp_path)
    job = job_envelope()
    action = orchestrator.intake(job)["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job["payload"]["job_id"]))) ["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=deploy_result()))["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=observe_result()))["messages"][0]

    action = orchestrator.receive_result(
        result_for(action, status="failed", error={"code": "internal_error", "message": "first deploy rejected"})
    )["messages"][0]
    assert action["kind"] == "action"
    assert action["payload"]["verb"] == "deploy_revision"

    action = orchestrator.receive_result(
        result_for(action, status="failed", error={"code": "internal_error", "message": "second deploy rejected"})
    )["messages"][0]
    assert action["kind"] == "action"
    assert action["payload"]["verb"] == "deploy_revision"
    assert orchestrator.jobs[job["payload"]["job_id"]]["attempt_count"]["patch"] == 3
    assert max_patch_attempts_budget() == 3


def test_diagnosis_failures_count_once_and_exhaust_existing_budget(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAPHAEL_MAX_DIAGNOSIS_ATTEMPTS", "2")
    orchestrator = make_orchestrator(tmp_path)
    job = job_envelope()
    action = orchestrator.intake(job)["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job["payload"]["job_id"]))) ["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=deploy_result()))["messages"][0]

    action = orchestrator.receive_result(
        result_for(action, status="failed", error={"code": "timeout", "message": "observation timed out"})
    )["messages"][0]
    assert action["kind"] == "action"
    assert action["payload"]["verb"] == "observe_failure"

    terminal = orchestrator.receive_result(
        result_for(action, status="failed", error={"code": "timeout", "message": "observation timed out again"})
    )["messages"][0]
    assert terminal["kind"] == "terminal"
    assert terminal["payload"]["final_status"] == "escalated"
    assert orchestrator.jobs[job["payload"]["job_id"]]["attempt_count"]["diagnosis"] == 2

def test_existing_http_timeout_env_caps_actions(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RAPHAEL_SANDBOX_HTTP_TIMEOUT", "7")
    orchestrator = make_orchestrator(tmp_path)
    job = job_envelope()
    action = orchestrator.intake(job)["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job["payload"]["job_id"]))) ["messages"][0]
    assert action["payload"]["args"]["wait_seconds"] == 7
    action = orchestrator.receive_result(result_for(action, result=deploy_result()))["messages"][0]
    assert action["payload"]["args"]["timeout_seconds"] == 7


def test_replayed_result_is_noop(tmp_path: Path) -> None:
    orchestrator = make_orchestrator(tmp_path)
    job = job_envelope()
    action = orchestrator.intake(job)["messages"][0]
    result = result_for(action, result=create_result(job["payload"]["job_id"]))
    first = orchestrator.receive_result(result)
    second = orchestrator.receive_result(result)
    assert first["idempotent_replay"] is False
    assert second == {"messages": [], "idempotent_replay": True}


def test_expired_lease_fails_closed(tmp_path: Path) -> None:
    current = [datetime(2026, 8, 27, tzinfo=timezone.utc)]
    orchestrator = make_orchestrator(tmp_path, clock=lambda: current[0])
    job = job_envelope(lease_ttl_seconds=30)
    orchestrator.intake(job)
    current[0] += timedelta(seconds=31)
    terminals = orchestrator.reap_expired()
    assert len(terminals) == 1
    assert terminals[0]["payload"]["final_status"] == "failed"
    assert orchestrator.jobs[job["payload"]["job_id"]]["terminal_reason"] == "job_lease_expired"


def test_http_endpoints_use_orchestrator(tmp_path: Path) -> None:
    client = TestClient(create_app(make_orchestrator(tmp_path)))
    job = job_envelope()
    response = client.post("/v1/jobs", json=job)
    assert response.status_code == 200
    assert response.json()["messages"][0]["payload"]["verb"] == "create_sandbox"
    assert client.get("/health").json()["status"] == "ok"
