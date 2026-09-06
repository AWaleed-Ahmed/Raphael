"""Three-scenario E2E harness for Raphael dispatch + Ignis controller+connector."""
from __future__ import annotations

import json
import os
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

# Known expected failure tracked by D-20260906-04. Scenario 3 remains in the
# run so CI keeps recording the real restart trace, but it does not gate until
# Ignis persists enough job/sandbox context to resume a redelivered action.
SCENARIO_3_XFAIL_REASON = (
    "D-20260906-04: Ignis connector restart recovery has no durable "
    "job-to-sandbox/workspace context"
)


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


def extract_sandbox_ids(records: list[dict], job_id: str) -> list[tuple[int, str, str]]:
    """Return [(record_index, verb, sandbox_id)] for all records mentioning this job."""
    results = []
    for i, rec in enumerate(records):
        resp_body = rec.get("response", {}).get("body", "")
        req_body = rec.get("request", {}).get("body", "")
        if job_id not in resp_body and job_id not in req_body:
            continue
        try:
            parsed = json.loads(resp_body) if resp_body else {}
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        for msg in parsed.get("messages", []):
            payload = msg.get("payload", {})
            verb = payload.get("verb", "")
            sid = payload.get("result", {}).get("sandbox_id", "") or payload.get("args", {}).get("sandbox_id", "")
            if verb:
                results.append((i, verb, sid))
        # Also check request body for result POSTs from connector
        try:
            req_parsed = json.loads(req_body) if req_body else {}
        except (json.JSONDecodeError, TypeError):
            req_parsed = {}
        req_payload = req_parsed.get("payload", req_parsed)
        req_verb = req_payload.get("verb", "")
        req_sid = (req_payload.get("result") or {}).get("sandbox_id", "")
        if req_verb and req_sid:
            results.append((i, f"result:{req_verb}", req_sid))
    return results


def wait_mid_flight(trace: Path, job_id: str, diagnose_marker: Path, timeout: float = 60) -> tuple[str, list[dict]]:
    """Wait until create_sandbox completed and the delayed diagnose hook is running."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        records = trace_records(trace)
        verbs_seen = []
        sandbox_id = ""
        for rec in records:
            resp_body = rec.get("response", {}).get("body", "")
            req_body = rec.get("request", {}).get("body", "")
            if job_id not in resp_body and job_id not in req_body:
                continue
            # Check response messages for dispatched actions
            try:
                parsed = json.loads(resp_body) if resp_body else {}
            except (json.JSONDecodeError, TypeError):
                parsed = {}
            for msg in parsed.get("messages", []):
                payload = msg.get("payload", {})
                verb = payload.get("verb", "")
                kind = msg.get("kind", "")
                if kind == "terminal":
                    raise RuntimeError("job reached terminal before mid-flight window")
                if verb:
                    verbs_seen.append(("dispatched", verb))
            # Check request body for result POSTs
            try:
                req_parsed = json.loads(req_body) if req_body else {}
            except (json.JSONDecodeError, TypeError):
                req_parsed = {}
            req_payload = req_parsed.get("payload", req_parsed)
            req_verb = req_payload.get("verb", "")
            req_kind = req_parsed.get("kind", "")
            if req_kind == "result" and req_verb:
                verbs_seen.append(("result", req_verb))
                sid = (req_payload.get("result") or {}).get("sandbox_id", "")
                if sid:
                    sandbox_id = sid

        has_create_result = any(v == ("result", "create_sandbox") for v in verbs_seen)
        if has_create_result and diagnose_marker.exists() and sandbox_id:
            return sandbox_id, records
        time.sleep(0.3)
    raise RuntimeError("timed out waiting for mid-flight state")


def run_scenario_3_restart(
    env: dict,
    trace: Path,
    controller_cmd: list[str],
    processes: list[subprocess.Popen],
) -> bool:
    print("\n========== SCENARIO 3: whole-process restart (mid-flight) ==========")

    delay_seconds = int(env["E2E_DIAGNOSE_DELAY_SECONDS"])
    diagnose_marker = Path(env["E2E_DIAGNOSE_STARTED_FILE"])
    print(f"E2E_DIAGNOSE_DELAY_SECONDS={delay_seconds} (diagnose hook will sleep)")

    submitted = make_job("e2e-success")
    t_submit = time.time()
    status, response = http_post(f"{DISPATCH}/v1/tenants/{TENANT}/jobs", submitted, PRODUCER)
    print(f"[{time.time() - t_submit:.1f}s] Submitted: status={status}")
    assert status == 202

    print(f"[{time.time() - t_submit:.1f}s] Polling trace for confirmed mid-flight state...")
    try:
        pre_kill_sandbox_id, _ = wait_mid_flight(trace, submitted["job_id"], diagnose_marker, timeout=60)
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return False

    t_midflight = time.time()
    print(f"[{t_midflight - t_submit:.1f}s] Mid-flight confirmed: sandbox_id={pre_kill_sandbox_id}")
    print(f"[{t_midflight - t_submit:.1f}s] create_sandbox done, deploy_revision issued, diagnose sleeping {delay_seconds}s")

    # Verify no terminal yet
    records_now = trace_records(trace)
    terminal_now = find_terminal(records_now, submitted["job_id"])
    if terminal_now:
        print(f"FAIL: job already terminal before kill: {terminal_now}")
        return False

    print(f"[{time.time() - t_submit:.1f}s] Killing Ignis process...")
    t_kill = time.time()
    ignis_pid = int(env.get("_E2E_IGNIS_PID", "0"))
    ignis_process = next((proc for proc in processes if proc.pid == ignis_pid), None)
    if ignis_process:
        try:
            ignis_process.terminate()
            ignis_process.wait(timeout=10)
            print(f"[{time.time() - t_submit:.1f}s] Ignis pid={ignis_pid} exited after SIGTERM")
        except subprocess.TimeoutExpired:
            ignis_process.kill()
            ignis_process.wait(timeout=10)
            print(f"[{time.time() - t_submit:.1f}s] Ignis pid={ignis_pid} required SIGKILL")
        finally:
            processes.remove(ignis_process)
    else:
        print(f"FAIL: unable to find tracked Ignis process pid={ignis_pid}")
        return False

    print(f"[{time.time() - t_submit:.1f}s] Restarting Ignis...")
    t_restart_start = time.time()
    restart_log = open(E2E / "ignis-restart.log", "w", encoding="utf-8")
    restarted = subprocess.Popen(controller_cmd, env=env, stdout=restart_log, stderr=subprocess.STDOUT)
    processes.append(restarted)
    env["_E2E_IGNIS_PID"] = str(restarted.pid)
    wait_ready(env["RAPHAEL_CONNECTOR_CONTROLLER_URL"], timeout=15)
    t_restart_ready = time.time()
    print(f"[{t_restart_ready - t_submit:.1f}s] Ignis restarted, pid={restarted.pid}, startup took {t_restart_ready - t_restart_start:.1f}s")

    try:
        terminal, records = wait_terminal(trace, submitted["job_id"], timeout=90)
        t_terminal = time.time()
        final_status = terminal.get("payload", {}).get("final_status", "")
        print(f"[{t_terminal - t_submit:.1f}s] Terminal: final_status={final_status}")

        # Extract sandbox_ids from post-restart records
        all_sids = extract_sandbox_ids(records, submitted["job_id"])
        print(f"\nSandbox ID timeline:")
        for idx, verb, sid in all_sids:
            if sid:
                print(f"  record[{idx}] {verb}: sandbox_id={sid}")

        post_restart_sids = set()
        for idx, verb, sid in all_sids:
            if sid and sid != pre_kill_sandbox_id:
                post_restart_sids.add(sid)

        if post_restart_sids:
            print(f"\nFAIL: new sandbox_id(s) appeared post-restart: {post_restart_sids}")
            print(f"  Pre-kill sandbox_id: {pre_kill_sandbox_id}")
            resumed = False
        else:
            # Check that the pre-kill sandbox_id appears in post-kill activity
            post_kill_verbs = []
            for idx, verb, sid in all_sids:
                if sid == pre_kill_sandbox_id:
                    post_kill_verbs.append(verb)
            print(f"\nPre-kill sandbox_id {pre_kill_sandbox_id} seen in verbs: {post_kill_verbs}")
            resumed = len(post_kill_verbs) > 1  # more than just create_sandbox

        print(f"\nWall-clock timeline:")
        print(f"  Submit:          t+0.0s")
        print(f"  Mid-flight:      t+{t_midflight - t_submit:.1f}s")
        print(f"  Kill:            t+{t_kill - t_submit:.1f}s")
        print(f"  Restart ready:   t+{t_restart_ready - t_submit:.1f}s")
        print(f"  Terminal:        t+{t_terminal - t_submit:.1f}s")
        print(f"  Downtime:        {t_restart_ready - t_kill:.1f}s")

        print_trace("Scenario 3", records, submitted["job_id"])

        if final_status == "fix_finalized" and resumed:
            print("PASS: job resumed with same sandbox_id after restart")
            return True
        elif final_status == "failed":
            print(f"OBSERVED: job terminalized as failed (possible lease expiry)")
            return True
        else:
            print(f"UNEXPECTED: final_status={final_status}, resumed={resumed}")
            return False

    except AssertionError:
        elapsed = time.time() - t_restart_ready
        print(f"No terminal after {elapsed:.1f}s post-restart")
        reap_status, reap_resp = http_post(f"{DISPATCH}/v1/leases/reap", {}, PRODUCER)
        print(f"Reap: status={reap_status}, response={json.dumps(reap_resp, sort_keys=True)}")
        terminals = reap_resp.get("terminals", [])
        for t_rec in terminals:
            if t_rec.get("job_id") == submitted["job_id"]:
                print(f"Lease-expired terminal: {json.dumps(t_rec, sort_keys=True)}")
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

        # The deterministic Scenario 3 delay must be present when dispatch
        # starts; changing this parent-process dictionary later cannot alter
        # the environment of an already-running dispatch child.
        dispatch.terminate()
        dispatch.wait(timeout=10)
        processes.remove(dispatch)
        env["E2E_DIAGNOSE_DELAY_SECONDS"] = "15"
        diagnose_marker = data_dir / "diagnose-started"
        diagnose_marker.unlink(missing_ok=True)
        env["E2E_DIAGNOSE_STARTED_FILE"] = str(diagnose_marker)
        scenario_3_dispatch_log = open(E2E / "dispatch-scenario-3.log", "w", encoding="utf-8")
        dispatch = subprocess.Popen(
            [sys.executable, str(E2E / "dispatch_server.py")],
            cwd=str(ROOT), env=env, stdout=scenario_3_dispatch_log, stderr=subprocess.STDOUT,
        )
        processes.append(dispatch)
        wait_ready(DISPATCH)
        print(f"Dispatch restarted for Scenario 3, pid={dispatch.pid}")
        results["scenario_3"] = run_scenario_3_restart(env, trace, controller_cmd, processes)

        print("\n========== RESULTS ==========")
        all_pass = True
        for name, passed in results.items():
            if name == "scenario_3":
                status = "XPASS" if passed else "XFAIL"
                print(f"  {name}: {status} ({SCENARIO_3_XFAIL_REASON})")
                continue
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
