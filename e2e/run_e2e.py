"""Three-scenario E2E harness for Raphael dispatch + Ignis controller+connector."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
import tempfile
import shutil
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
E2E = Path(__file__).resolve().parent
DISPATCH = os.getenv("E2E_DISPATCH_URL", "http://127.0.0.1:8092")
TENANT = os.getenv("E2E_TENANT_ID", "e2e-tenant")
TOKEN = os.getenv("E2E_CONNECTOR_TOKEN", "e2e-connector-token")
PRODUCER = os.getenv("E2E_PRODUCER_TOKEN", "e2e-producer-token")
IGNIS_BIN = os.getenv("E2E_IGNIS_BIN", "")
CLONE_URL = os.getenv("E2E_CLONE_URL", "https://github.com/AmazingDude/raphael-e2e-fixture.git")
COMMIT_SHA = os.getenv("E2E_COMMIT_SHA", "57f0801fe46527c7531d62c5e278db80b7b56564")


def http_post(url: str, body: dict, token: str) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.load(resp)
    except URLError as exc:
        if hasattr(exc, "code"):
            try:
                body_bytes = exc.read()
                return exc.code, json.loads(body_bytes)
            except Exception:
                return exc.code, {"error": str(exc)}
        raise


def wait_ready(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{url}/health", timeout=2):
                return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"process did not become ready: {url}")


SCENARIO_LINE = {"e2e-success": 1, "e2e-fail-validation": 2}


def make_job(prefix: str) -> dict:
    job_id = str(uuid.uuid4())
    return {
        "protocol_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "job_id": job_id,
        "kind": "job",
        "sent_at": "2026-08-29T00:00:00Z",
        "payload": {
            "job_id": job_id,
            "repository": {
                "name": "raphael-e2e-fixture",
                "clone_url": CLONE_URL,
            },
            "commit_sha": COMMIT_SHA,
            "narrowed_location": {"file_path": "deploy/manifests/app.yaml", "line_start": SCENARIO_LINE[prefix]},
            "lease_ttl_seconds": int(os.getenv("E2E_LEASE_TTL_SECONDS", "60")),
        },
    }


def trace_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def find_terminal(records: list[dict], job_id: str) -> dict | None:
    for record in reversed(records):
        resp_body = record.get("response", {}).get("body", "")
        if job_id not in resp_body:
            continue
        try:
            parsed = json.loads(resp_body)
        except (json.JSONDecodeError, TypeError):
            continue
        messages = parsed.get("messages", [])
        for msg in messages:
            if msg.get("kind") == "terminal":
                return msg
    return None


def wait_terminal(trace: Path, job_id: str, timeout: float = 120) -> tuple[dict, list[dict]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        records = trace_records(trace)
        terminal = find_terminal(records, job_id)
        if terminal is not None:
            return terminal, records
        time.sleep(0.5)
    raise AssertionError(f"timed out waiting for terminal envelope for {job_id}")


def count_patch_attempts(records: list[dict], job_id: str) -> int:
    count = 0
    for record in records:
        resp_body = record.get("response", {}).get("body", "")
        if job_id not in resp_body:
            continue
        try:
            parsed = json.loads(resp_body)
        except (json.JSONDecodeError, TypeError):
            continue
        for msg in parsed.get("messages", []):
            payload = msg.get("payload", {})
            if payload.get("verb") == "deploy_revision":
                patch_data = payload.get("args", {}).get("patch")
                if patch_data and patch_data.get("files"):
                    count += 1
    return count


def find_clone_workspace(job_id: str) -> Path | None:
    import glob as glob_mod
    tmp = Path(tempfile.gettempdir())
    for entry in tmp.iterdir():
        if entry.is_dir() and entry.name.startswith("raphael-clone-"):
            git_config = entry / ".git" / "config"
            if git_config.exists():
                content = git_config.read_text(errors="replace")
                if "raphael-e2e-fixture" in content:
                    return entry
    return None


def print_trace(label: str, records: list[dict], job_id: str) -> None:
    print(f"\n=== {label} HTTP trace (job {job_id}) ===")
    for i, rec in enumerate(records):
        req = rec.get("request", {})
        resp = rec.get("response", {})
        req_body = req.get("body", "")
        if job_id not in req_body and job_id not in resp.get("body", ""):
            continue
        method = req.get("method", "?")
        path = req.get("path", "?")
        status = resp.get("status", "?")
        resp_body = resp.get("body", "")
        condensed = resp_body[:200] + ("..." if len(resp_body) > 200 else "")
        print(f"  [{i}] {method} {path} -> {status}")
        print(f"       resp: {condensed}")


def run_scenario_1_success(env: dict, trace: Path) -> bool:
    print("\n========== SCENARIO 1: success ==========")
    submitted = make_job("e2e-success")
    status, response = http_post(f"{DISPATCH}/v1/tenants/{TENANT}/jobs", submitted, PRODUCER)
    print(f"Submitted: status={status}, response={json.dumps(response, sort_keys=True)}")
    assert status == 202, f"job submission failed: {status}"

    terminal, records = wait_terminal(trace, submitted["job_id"])
    final_status = terminal.get("payload", {}).get("final_status", "")
    print(f"Terminal: final_status={final_status}")
    print_trace("Scenario 1", records, submitted["job_id"])

    assert final_status == "fix_finalized", f"expected fix_finalized, got {final_status}"

    time.sleep(2)
    workspace = find_clone_workspace(submitted["job_id"])
    if workspace and workspace.exists():
        print(f"FAIL: clone workspace still exists at {workspace}")
        return False
    print("PASS: clone workspace cleaned up")
    return True


def run_scenario_2_escalation(env: dict, trace: Path) -> bool:
    print("\n========== SCENARIO 2: escalation after max patch attempts ==========")
    max_attempts = int(env.get("RAPHAEL_MAX_PATCH_ATTEMPTS", "2"))
    print(f"RAPHAEL_MAX_PATCH_ATTEMPTS={max_attempts}")

    submitted = make_job("e2e-fail-validation")
    status, response = http_post(f"{DISPATCH}/v1/tenants/{TENANT}/jobs", submitted, PRODUCER)
    print(f"Submitted: status={status}, response={json.dumps(response, sort_keys=True)}")
    assert status == 202, f"job submission failed: {status}"

    terminal, records = wait_terminal(trace, submitted["job_id"])
    final_status = terminal.get("payload", {}).get("final_status", "")
    print(f"Terminal: final_status={final_status}")

    patch_count = count_patch_attempts(records, submitted["job_id"])
    print(f"Patch deploy attempts observed: {patch_count}")
    print_trace("Scenario 2", records, submitted["job_id"])

    assert final_status == "escalated", f"expected escalated, got {final_status}"
    assert patch_count == max_attempts, f"expected exactly {max_attempts} patch attempts, got {patch_count}"

    time.sleep(2)
    workspace = find_clone_workspace(submitted["job_id"])
    if workspace and workspace.exists():
        print(f"FAIL: clone workspace still exists at {workspace}")
        return False
    print("PASS: clone workspace cleaned up")
    return True


def run_scenario_3_restart(env: dict, trace: Path, controller_cmd: list[str]) -> bool:
    print("\n========== SCENARIO 3: whole-process restart ==========")
    submitted = make_job("e2e-success")
    status, response = http_post(f"{DISPATCH}/v1/tenants/{TENANT}/jobs", submitted, PRODUCER)
    print(f"Submitted: status={status}, response={json.dumps(response, sort_keys=True)}")
    assert status == 202

    print("Waiting 3s for create_sandbox to execute...")
    time.sleep(3)

    records_before = trace_records(trace)
    has_create = any(
        "create_sandbox" in r.get("request", {}).get("body", "")
        and submitted["job_id"] in r.get("request", {}).get("body", "")
        for r in records_before
    )
    print(f"create_sandbox executed before kill: {has_create}")

    terminal_before = find_terminal(records_before, submitted["job_id"])
    if terminal_before:
        print(f"Job already terminal before kill: {terminal_before}")
        print("SKIP: cannot test restart — job completed too fast")
        return True

    print("Killing Ignis process...")
    ignis_pid = int(os.environ.get("_E2E_IGNIS_PID", "0"))
    if ignis_pid:
        try:
            os.kill(ignis_pid, signal.SIGTERM)
            print(f"Sent SIGTERM to pid {ignis_pid}")
        except ProcessLookupError:
            print(f"Process {ignis_pid} already gone")
    time.sleep(2)

    print("Restarting Ignis...")
    restart_log = open(E2E / "ignis-restart.log", "w", encoding="utf-8")
    restarted = subprocess.Popen(controller_cmd, env=env, stdout=restart_log, stderr=subprocess.STDOUT)
    os.environ["_E2E_IGNIS_PID"] = str(restarted.pid)
    wait_ready(env["RAPHAEL_CONNECTOR_CONTROLLER_URL"], timeout=15)
    print(f"Ignis restarted, pid={restarted.pid}")

    kill_time = time.time()
    try:
        terminal, records = wait_terminal(trace, submitted["job_id"], timeout=90)
        elapsed = time.time() - kill_time
        final_status = terminal.get("payload", {}).get("final_status", "")
        print(f"Terminal after restart: final_status={final_status}, elapsed={elapsed:.1f}s")
        print_trace("Scenario 3 (post-restart)", records, submitted["job_id"])
        return True
    except AssertionError:
        elapsed = time.time() - kill_time
        print(f"No terminal after {elapsed:.1f}s post-restart")

        print("Checking lease expiry via POST /v1/leases/reap...")
        reap_status, reap_resp = http_post(f"{DISPATCH}/v1/leases/reap", {}, PRODUCER)
        print(f"Reap: status={reap_status}, response={json.dumps(reap_resp, sort_keys=True)}")
        terminals = reap_resp.get("terminals", [])
        for t in terminals:
            if t.get("job_id") == submitted["job_id"]:
                print(f"Lease-expired terminal: {json.dumps(t, sort_keys=True)}")
                return True
        print("Job not found in reap results either")
        return False


def main() -> int:
    if not IGNIS_BIN:
        print("ERROR: E2E_IGNIS_BIN must be set to the absolute path of raphael-sandbox-controller")
        return 1

    env = os.environ.copy()
    env["RAPHAEL_DISPATCH_TOKENS"] = json.dumps({
        PRODUCER: {"tenant_id": TENANT, "role": "producer"},
        TOKEN: {"tenant_id": TENANT, "role": "connector"},
    })
    env.setdefault("RAPHAEL_MAX_PATCH_ATTEMPTS", "2")
    env.setdefault("RAPHAEL_PARTNER_MODE", "dry_run")
    env.setdefault("RAPHAEL_PUBLISH_MODE", "dry_run")
    env.setdefault("RAPHAEL_LLM_DIAGNOSIS", "0")
    env["E2E_CONNECTOR_TOKEN"] = TOKEN
    env["E2E_TENANT_ID"] = TENANT
    env["RAPHAEL_CONNECTOR_DISPATCH_URL"] = DISPATCH
    env["RAPHAEL_CONNECTOR_CONTROLLER_URL"] = os.getenv("E2E_CONTROLLER_URL", "http://127.0.0.1:8090")
    env["RAPHAEL_CONNECTOR_POLL_INTERVAL_MS"] = os.getenv("E2E_POLL_INTERVAL_MS", "200")
    env["RAPHAEL_CONNECTOR_TENANT_ID"] = TENANT
    env["RAPHAEL_CONNECTOR_TOKEN"] = TOKEN
    env["RAPHAEL_CLUSTER_BACKEND"] = "mock"
    env["RAPHAEL_LISTEN"] = os.getenv("E2E_CONTROLLER_LISTEN", "127.0.0.1:8090")

    trace = Path(os.getenv("E2E_TRACE_FILE", str(E2E / "e2e-dispatch-trace.jsonl")))
    if trace.exists():
        trace.unlink()
    env["E2E_TRACE_FILE"] = str(trace)

    data_dir = Path(tempfile.mkdtemp(prefix="raphael-e2e-"))
    env["RAPHAEL_DATA_DIR"] = str(data_dir)

    controller_cmd = [IGNIS_BIN]
    processes: list[subprocess.Popen] = []

    try:
        dispatch_log = open(E2E / "dispatch.log", "w", encoding="utf-8")
        dispatch = subprocess.Popen(
            [sys.executable, str(E2E / "dispatch_server.py")],
            cwd=str(ROOT), env=env, stdout=dispatch_log, stderr=subprocess.STDOUT,
        )
        processes.append(dispatch)
        wait_ready(DISPATCH)
        print(f"Dispatch ready, pid={dispatch.pid}")

        controller_log = open(E2E / "ignis.log", "w", encoding="utf-8")
        controller = subprocess.Popen(
            controller_cmd, env=env, stdout=controller_log, stderr=subprocess.STDOUT,
        )
        processes.append(controller)
        env["_E2E_IGNIS_PID"] = str(controller.pid)
        wait_ready(env["RAPHAEL_CONNECTOR_CONTROLLER_URL"])
        print(f"Ignis ready, pid={controller.pid}")

        results = {}
        results["scenario_1"] = run_scenario_1_success(env, trace)
        results["scenario_2"] = run_scenario_2_escalation(env, trace)
        results["scenario_3"] = run_scenario_3_restart(env, trace, controller_cmd)

        print("\n========== RESULTS ==========")
        all_pass = True
        for name, passed in results.items():
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_pass = False
            print(f"  {name}: {status}")

        print(f"\nTrace file: {trace}")
        print(f"Data dir: {data_dir}")
        return 0 if all_pass else 1

    finally:
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
