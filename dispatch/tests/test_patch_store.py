from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from raphael_dispatch.orchestrator import AgentHooks, Orchestrator
from raphael_dispatch.patch_store import EphemeralPatchStore
from raphael_agent.store import RunStore, SqliteRunStore
from tests.test_orchestrator import (
    create_result,
    deploy_result,
    envelope,
    fake_publish,
    job_envelope,
    observe_result,
    result_for,
    validation_result,
)


def test_ephemeral_patch_store_lifecycle() -> None:
    store = EphemeralPatchStore()
    job_id = "job-123"
    files = [{"path": "deploy/manifests/app.yaml", "content": "secret: token-123"}]

    assert not store.has_manifests(job_id)
    assert store.get_manifests(job_id) == []

    store.save_manifests(job_id, files)
    assert store.has_manifests(job_id)
    stored = store.get_manifests(job_id)
    assert len(stored) == 1
    assert stored[0]["content"] == "secret: token-123"

    # Purge at terminal
    store.purge(job_id)
    assert not store.has_manifests(job_id)
    assert store.get_manifests(job_id) == []


def test_rendered_files_isolated_from_run_store_and_purged_at_terminal(tmp_path: Path) -> None:
    run_store = RunStore(tmp_path / "runs")
    patch_store = EphemeralPatchStore()

    diagnose_states: list[dict] = []
    patch_states: list[dict] = []

    def spy_diagnose(state: dict) -> dict:
        diagnose_states.append(dict(state))
        return {
            "status": "running",
            "diagnosis": {"classification": {"failure_class": "probe_misconfiguration"}},
        }

    def spy_patch(state: dict) -> dict:
        patch_states.append(dict(state))
        active_id = "patch-1"
        return {
            "status": "running",
            "candidate_patches": [{"patch_id": active_id, "files": [{"path": "deploy/app.yaml", "content": "fixed"}]}],
            "active_patch_id": active_id,
        }

    hooks = AgentHooks(
        diagnose=spy_diagnose,
        patch=spy_patch,
        publish=fake_publish,
    )
    orchestrator = Orchestrator(store=run_store, hooks=hooks, patch_store=patch_store)

    job = job_envelope()
    job_id = job["payload"]["job_id"]
    action = orchestrator.intake(job)["messages"][0]

    # Create sandbox
    action = orchestrator.receive_result(result_for(action, result=create_result(job_id)))["messages"][0]
    assert action["payload"]["verb"] == "deploy_revision"

    # Initial deploy discloses secret-bearing manifests
    secret_manifest = [{"path": "deploy/manifests/app.yaml", "content": "apiKey: RAW_SECRET_12345\nport: 8080"}]
    initial_deploy = deploy_result()
    initial_deploy["rendered_files"] = secret_manifest

    action = orchestrator.receive_result(result_for(action, result=initial_deploy))["messages"][0]
    assert action["payload"]["verb"] == "observe_failure"

    # Check 1: manifests in patch_store, but NOT in orchestrator.jobs state
    assert patch_store.has_manifests(job_id)
    assert "rendered_files" not in orchestrator.jobs[job_id]

    # Check 2: persisted RunStore JSON on disk does NOT contain rendered_files or the secret
    persisted_run = run_store.get_run(job_id)
    assert persisted_run is not None
    assert "rendered_files" not in persisted_run
    raw_json = (tmp_path / "runs" / "runs" / f"{job_id}.json").read_text(encoding="utf-8")
    assert "RAW_SECRET_12345" not in raw_json
    assert "rendered_files" not in raw_json

    # Observe failure -> diagnose -> localize -> patch
    action = orchestrator.receive_result(result_for(action, result=observe_result()))["messages"][0]
    assert action["payload"]["verb"] == "deploy_revision"

    # Check 3: diagnose hook never saw rendered_files
    assert len(diagnose_states) == 1
    assert "rendered_files" not in diagnose_states[0]

    # Check 4: patch hook DID receive rendered_files in its execution context
    assert len(patch_states) == 1
    assert "rendered_files" in patch_states[0]
    assert patch_states[0]["rendered_files"][0]["content"] == "apiKey: RAW_SECRET_12345\nport: 8080"

    # Check 5: orchestrator.jobs[job_id] still does not retain rendered_files
    assert "rendered_files" not in orchestrator.jobs[job_id]

    # Finish job to terminal (deploy_patch -> validation -> finalize -> terminal)
    patch_deploy = deploy_result()
    action = orchestrator.receive_result(result_for(action, result=patch_deploy))["messages"][0]
    assert action["payload"]["verb"] == "run_validation"

    action = orchestrator.receive_result(result_for(action, result=validation_result()))["messages"][0]
    assert action["payload"]["verb"] == "finalize_result"

    terminal = orchestrator.receive_result(result_for(action))["messages"][0]
    assert terminal["kind"] == "terminal"
    assert terminal["payload"]["final_status"] == "fix_finalized"

    # Check 6: EphemeralPatchStore is completely purged at terminal cleanup
    assert not patch_store.has_manifests(job_id)
    assert patch_store.get_manifests(job_id) == []


def test_ephemeral_patch_store_purged_on_lease_expiry(tmp_path: Path) -> None:
    run_store = RunStore(tmp_path / "runs")
    patch_store = EphemeralPatchStore()
    orchestrator = Orchestrator(store=run_store, patch_store=patch_store)

    job = job_envelope(lease_ttl_seconds=30)
    job_id = job["payload"]["job_id"]
    action = orchestrator.intake(job)["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job_id)))["messages"][0]

    deploy_res = deploy_result()
    deploy_res["rendered_files"] = [{"path": "deploy.yaml", "content": "raw content"}]
    orchestrator.receive_result(result_for(action, result=deploy_res))

    assert patch_store.has_manifests(job_id)

    # Fast forward past lease TTL
    from datetime import datetime, timedelta, timezone
    future = datetime.now(timezone.utc) + timedelta(seconds=40)
    terminals = orchestrator.reap_expired(now=future)

    assert len(terminals) == 1
    assert terminals[0]["payload"]["final_status"] == "failed"
    assert not patch_store.has_manifests(job_id)


def test_run_store_defense_in_depth_sanitizes_rendered_files(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs")
    job_id = "test-sanitization"
    store.save_run({
        "run_id": job_id,
        "status": "running",
        "rendered_files": [{"path": "secret.yaml", "content": "SUPER_SECRET_PAYLOAD"}],
    })

    saved = store.get_run(job_id)
    assert saved is not None
    assert "rendered_files" not in saved
    raw_text = (tmp_path / "runs" / "runs" / f"{job_id}.json").read_text(encoding="utf-8")
    assert "SUPER_SECRET_PAYLOAD" not in raw_text
    assert "rendered_files" not in raw_text


def assert_no_secret_in_persisted_run(store, job_id):
    # Inspect the ENTIRE serialized record, not a selected field or only the
    # pre-patch checkpoint. The SQLite implementation also writes a JSON mirror.
    assert "UNREDACTED_API_SECRET_TOKEN" not in json.dumps(store.get_run(job_id))
    assert "UNREDACTED_API_SECRET_TOKEN" not in (
        store.runs_dir / f"{job_id}.json"
    ).read_text(encoding="utf-8")
    if isinstance(store, SqliteRunStore):
        with sqlite3.connect(store.db_path) as connection:
            payload = connection.execute("SELECT payload FROM runs WHERE run_id = ?", (job_id,)).fetchone()[0]
        assert "UNREDACTED_API_SECRET_TOKEN" not in payload


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
def test_durable_projection_strips_all_patch_copies_without_mutating_live_state(tmp_path, store_type):
    secret = "UNREDACTED_API_SECRET_TOKEN"
    proposal = {
        "patch_id": "patch-1",
        "files": [{"path": "deploy/app.yaml", "content": secret,
                   "unified_diff_hunk": f"+{secret}"}],
        "unified_diff": f"+{secret}",
    }
    live = {
        "run_id": "projection-test",
        "candidate_patches": [proposal],
        "validated_fix_record": {"patch": proposal},
        "dispatch": {
            "stage": "deploy_patch",
            "pending_action": {"payload": {"args": {"patch": proposal}}},
        },
    }
    before = json.dumps(live)
    store = store_type(tmp_path / "runs")
    store.save_run(live)
    assert_no_secret_in_persisted_run(store, live["run_id"])
    assert json.dumps(live) == before
    saved = store.get_run(live["run_id"])
    assert saved["dispatch"]["patch_payloads_omitted"] is True
    assert saved["validated_fix_record"]["patch"]["files"] == [{"path": "deploy/app.yaml"}]
    store.save_run(saved)
    assert store.get_run(live["run_id"]) == saved


@pytest.mark.parametrize("store_type", [RunStore, SqliteRunStore])
@pytest.mark.parametrize("scenario", [
    "normal", "restart_before_patch", "restart_during_refetch",
    "policy_rejected", "missing_refetch", "restart_after_patch",
])
def test_real_node_patch_consumes_ephemeral_store_and_keeps_state_clean(tmp_path: Path, monkeypatch, store_type, scenario) -> None:
    from raphael_agent.graph.nodes import node_patch

    monkeypatch.setenv("RAPHAEL_MODEL_ENABLED", "0")
    run_store = store_type(tmp_path / "runs")
    patch_store = EphemeralPatchStore()

    def checked_real_patch(state):
        updates = node_patch(state)
        if scenario == "policy_rejected":
            # Check the actual node output BEFORE orchestrator terminal cleanup:
            # rejecting a proposal must never append its raw body in the first place.
            assert updates["candidate_patches"][-1]["policy_status"] == "rejected"
            assert "UNREDACTED_API_SECRET_TOKEN" not in json.dumps(updates)
        return updates

    hooks = AgentHooks(
        diagnose=lambda state: {
            "status": "running",
            "diagnosis": {
                "classification": {"category": "supported", "failure_class": "probe_misconfiguration", "blocked_reason": None},
                "selected_hypothesis_id": "hyp-probe-port",
                "confidence": 0.95,
            },
        },
        localize=lambda state: {"localization_result": {"status": "localized", "candidates": []}},
        patch=checked_real_patch,
        publish=fake_publish,
    )
    orchestrator = Orchestrator(store=run_store, hooks=hooks, patch_store=patch_store)

    job = job_envelope()
    job_id = job["payload"]["job_id"]
    action = orchestrator.intake(job)["messages"][0]
    action = orchestrator.receive_result(result_for(action, result=create_result(job_id)))["messages"][0]

    manifest_yaml = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: service\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "        - name: app\n"
        "          env:\n"
        "            - name: API_SECRET\n"
        "              value: UNREDACTED_API_SECRET_TOKEN\n"
        "          ports:\n"
        "            - containerPort: 8080\n"
        "          readinessProbe:\n"
        "            httpGet:\n"
        "              port: 9090\n"
    )
    if scenario == "policy_rejected":
        manifest_yaml += "# token: UNREDACTED_API_SECRET_TOKEN\n"
    deploy_res = deploy_result()
    deploy_res["rendered_files"] = [{"path": "deploy/manifests/app.yaml", "content": manifest_yaml}]
    action = orchestrator.receive_result(result_for(action, result=deploy_res))["messages"][0]

    if scenario in {"restart_before_patch", "restart_during_refetch", "missing_refetch"}:
        old_observation = action
        orchestrator = Orchestrator(store=run_store, hooks=hooks)
        assert orchestrator.rehydrate() == []
        assert not orchestrator.patch_store.has_manifests(job_id)
        assert orchestrator.jobs[job_id]["dispatch"]["pending_action"] == old_observation
        assert orchestrator.jobs[job_id]["sandbox_id"] == "sb-1"

    observe_res = observe_result()
    observe_res["signature"]["normalized"]["attributes"] = {"container_port": 8080, "probe_port": 9090}
    action = orchestrator.receive_result(result_for(action, result=observe_res))["messages"][0]

    if scenario in {"restart_before_patch", "restart_during_refetch", "missing_refetch"}:
        assert action["payload"]["verb"] == "deploy_revision"
        assert "patch" not in action["payload"]["args"]
        assert orchestrator.jobs[job_id]["dispatch"]["stage"] == "refresh_patch_input"
        assert orchestrator.jobs[job_id]["attempt_count"]["patch"] == 0
        if scenario == "restart_during_refetch":
            old_refresh = action
            orchestrator = Orchestrator(store=run_store, hooks=hooks)
            assert orchestrator.rehydrate() == []
            assert orchestrator.jobs[job_id]["dispatch"]["pending_action"] == old_refresh
        refreshed = deploy_result() if scenario == "missing_refetch" else deploy_res
        action = orchestrator.receive_result(result_for(action, result=refreshed))["messages"][0]
        assert orchestrator.jobs[job_id]["sandbox_id"] == "sb-1"

    if scenario in {"policy_rejected", "missing_refetch"}:
        assert action["kind"] == "terminal"
        assert action["payload"]["final_status"] == "escalated"
        assert_no_secret_in_persisted_run(run_store, job_id)
        assert not orchestrator.patch_store.has_manifests(job_id)
        if scenario == "policy_rejected":
            proposal = orchestrator.jobs[job_id]["candidate_patches"][-1]
            assert proposal["policy_status"] == "rejected"
            assert any(item["rule"] == "secret_like_content" for item in proposal["policy_violations"])
            assert "UNREDACTED_API_SECRET_TOKEN" not in json.dumps(proposal)
            assert all("content" not in item for item in proposal["files"])
        else:
            assert orchestrator.jobs[job_id]["terminal_reason"] == "patch_input_unavailable"
        return

    assert action["payload"]["verb"] == "deploy_revision"
    patch_args = action["payload"]["args"]["patch"]
    assert "files" in patch_args
    patched_file = patch_args["files"][0]
    assert patched_file["path"] == "deploy/manifests/app.yaml"
    assert "port: 8080" in patched_file["content"]
    assert "UNREDACTED_API_SECRET_TOKEN" in patched_file["content"]

    assert "rendered_files" not in orchestrator.jobs[job_id]
    persisted_run = run_store.get_run(job_id)
    assert "rendered_files" not in persisted_run
    assert_no_secret_in_persisted_run(run_store, job_id)
    assert "content" not in persisted_run["candidate_patches"][-1]["files"][0]
    assert "content" not in persisted_run["dispatch"]["pending_action"]["payload"]["args"]["patch"]["files"][0]

    if scenario == "restart_after_patch":
        restarted = Orchestrator(store=run_store, hooks=hooks)
        terminals = restarted.rehydrate()
        assert terminals[0]["payload"]["final_status"] == "failed"
        assert run_store.get_run(job_id)["terminal_reason"] == "patch_context_lost_on_restart"
        assert restarted.tenant_jobs("connector") == []
        assert_no_secret_in_persisted_run(run_store, job_id)
        # The producer retry path must also refuse a stripped action.
        run_store.save_run(persisted_run)
        retry = Orchestrator(store=run_store, hooks=hooks).intake(job)
        assert retry["messages"][0]["payload"]["final_status"] == "failed"
        return

    for outcome in (deploy_res, validation_result()):
        action = orchestrator.receive_result(result_for(action, result=outcome))["messages"][0]
        assert_no_secret_in_persisted_run(run_store, job_id)
    assert action["payload"]["verb"] == "finalize_result"
    terminal = orchestrator.receive_result(result_for(action))["messages"][0]
    assert terminal["payload"]["final_status"] == "fix_finalized"
    assert orchestrator.jobs[job_id]["attempt_count"]["patch"] == 1
    assert not orchestrator.patch_store.has_manifests(job_id)
    assert_no_secret_in_persisted_run(run_store, job_id)
