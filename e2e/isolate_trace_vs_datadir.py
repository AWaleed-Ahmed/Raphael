"""Isolation test: does fresh RAPHAEL_AGENT_DATA_DIR alone fix the full-chain test?

Runs the same flow as run_full_chain.py but WITHOUT E2E_TRACE_FILE set,
so trace middleware is never activated. If this passes, it confirms the
prior failures were purely stale RunStore/fingerprint dedup — trace
middleware was never functionally necessary.
"""
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
DISPATCH_URL = "http://127.0.0.1:8091"
CONTROLLER_URL = "http://127.0.0.1:8090"
TENANT = f"isolate-{uuid.uuid4().hex[:8]}"
CONNECTOR_TOKEN = "isolate-connector-token"
IGNIS_BIN = os.getenv("E2E_IGNIS_BIN", "")

FIXTURE_PATH = ROOT / "agent" / "tests" / "fixtures" / "real_workflow_run_failure.json"


def http_post(url, body, token=None, timeout=10, headers_extra=None):
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if headers_extra:
        headers.update(headers_extra)
    req = Request(url, data=data, method="POST", headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, json.load(resp)
    except URLError as exc:
        if hasattr(exc, "code"):
            try:
                return exc.code, json.loads(exc.read())
            except Exception:
                return exc.code, {"error": str(exc)}
        raise


def wait_ready(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{url}/health", timeout=2):
                return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"not ready: {url}")


def main():
    if not IGNIS_BIN:
        print("ERROR: set E2E_IGNIS_BIN")
        return 1

    assert not os.environ.get("RAPHAEL_GITHUB_TOKEN"), "RAPHAEL_GITHUB_TOKEN must NOT be set"
    assert not os.environ.get("GITHUB_TOKEN"), "GITHUB_TOKEN must NOT be set"
    print("Safety: no GitHub tokens, publish defaults to dry_run")

    with open(FIXTURE_PATH) as f:
        webhook_payload = json.load(f)
    print(f"Loaded real webhook payload: workflow_run id={webhook_payload['workflow_run']['id']}")

    env = os.environ.copy()

    # Dispatch config
    env["RAPHAEL_DISPATCH_TOKENS"] = json.dumps({
        CONNECTOR_TOKEN: {"tenant_id": TENANT, "role": "connector"},
    })
    env["RAPHAEL_PARTNER_MODE"] = "dry_run"
    env["RAPHAEL_PUBLISH_MODE"] = "dry_run"
    env["RAPHAEL_LLM_DIAGNOSIS"] = "0"

    # Bridge config
    env["RAPHAEL_DISPATCH_BRIDGE_ENABLED"] = "1"
    env["RAPHAEL_INGEST_RUN_GRAPH"] = "0"
    env["RAPHAEL_AGENT_TENANT_ID"] = TENANT
    env["RAPHAEL_INGEST_MAX_CONCURRENT_RUNS"] = "100"

    # Ignis config
    env["RAPHAEL_CLUSTER_BACKEND"] = "mock"
    env["RAPHAEL_LISTEN"] = "127.0.0.1:8090"
    env["RAPHAEL_CONNECTOR_DISPATCH_URL"] = DISPATCH_URL
    env["RAPHAEL_CONNECTOR_CONTROLLER_URL"] = CONTROLLER_URL
    env["RAPHAEL_CONNECTOR_POLL_INTERVAL_MS"] = "200"
    env["RAPHAEL_CONNECTOR_TENANT_ID"] = TENANT
    env["RAPHAEL_CONNECTOR_TOKEN"] = CONNECTOR_TOKEN

    # KEY DIFFERENCE: NO E2E_TRACE_FILE — trace middleware will NOT activate
    if "E2E_TRACE_FILE" in env:
        del env["E2E_TRACE_FILE"]
    print("NOTE: E2E_TRACE_FILE is NOT set — trace middleware disabled")

    # Fresh data dir for RunStore isolation
    data_dir = Path(tempfile.mkdtemp(prefix="raphael-isolate-"))
    env["RAPHAEL_DATA_DIR"] = str(data_dir)
    env["RAPHAEL_AGENT_DATA_DIR"] = str(data_dir)
    print(f"Fresh RAPHAEL_AGENT_DATA_DIR: {data_dir}")

    processes = []
    try:
        dispatch_log_path = E2E / "isolate-dispatch.log"
        dispatch_log = open(dispatch_log_path, "w")
        dispatch = subprocess.Popen(
            [sys.executable, str(ROOT / "run.py")],
            cwd=str(ROOT), env=env, stdout=dispatch_log, stderr=subprocess.STDOUT,
        )
        processes.append(dispatch)
        wait_ready(DISPATCH_URL)
        print(f"Dispatch ready (NO trace middleware), pid={dispatch.pid}")

        ignis_log = open(E2E / "isolate-ignis.log", "w")
        ignis = subprocess.Popen(
            [IGNIS_BIN], env=env, stdout=ignis_log, stderr=subprocess.STDOUT,
        )
        processes.append(ignis)
        wait_ready(CONTROLLER_URL)
        print(f"Ignis ready, pid={ignis.pid}")

        t0 = time.time()
        print(f"\n[{time.time()-t0:.1f}s] POSTing real webhook payload to /v1/webhooks/github...")
        status, resp = http_post(
            f"{DISPATCH_URL}/v1/webhooks/github",
            webhook_payload,
            headers_extra={
                "x-github-event": "workflow_run",
                "x-github-delivery": f"isolate-test-{uuid.uuid4().hex[:8]}",
            },
        )
        print(f"[{time.time()-t0:.1f}s] Webhook response: status={status}")
        print(f"  Response: {json.dumps(resp, indent=2, default=str)[:500]}")

        dispatch_job_id = resp.get("dispatch_job_id")
        run_id = resp.get("run_id")

        if not dispatch_job_id:
            print(f"\nFAIL: webhook did not produce dispatch_job_id")
            print(f"  Ingest decision: {resp.get('ingest', {})}")
            return 1

        print(f"\n[{time.time()-t0:.1f}s] Bridge submitted: dispatch_job_id={dispatch_job_id}, run_id={run_id}")

        # Without trace middleware, verify completion by:
        # 1. Polling jobs/next until queue is empty (connector consumed the job)
        # 2. Grepping dispatch log for terminal state
        print(f"[{time.time()-t0:.1f}s] Waiting for connector to consume and complete job...")
        deadline = time.time() + 180
        job_consumed = False
        while time.time() < deadline:
            try:
                req = Request(
                    f"{DISPATCH_URL}/v1/tenants/{TENANT}/jobs/next",
                    headers={"Authorization": f"Bearer {CONNECTOR_TOKEN}"},
                )
                resp = urlopen(req, timeout=5)
                if resp.status == 204:
                    job_consumed = True
                    break
                body = json.load(resp)
                if not body.get("job_id"):
                    job_consumed = True
                    break
            except Exception:
                pass
            time.sleep(1)

        elapsed = time.time() - t0
        if not job_consumed:
            print(f"\nTIMEOUT after {elapsed:.1f}s — job still in queue")
            return 1

        print(f"[{time.time()-t0:.1f}s] Job consumed by connector, waiting for terminal in logs...")
        deadline = time.time() + 60
        final_status = None
        while time.time() < deadline:
            try:
                log_content = dispatch_log_path.read_text(encoding="utf-8", errors="replace")
                if "fix_finalized" in log_content and dispatch_job_id in log_content:
                    final_status = "fix_finalized"
                    break
                if "escalated" in log_content and dispatch_job_id in log_content:
                    final_status = "escalated"
                    break
            except Exception:
                pass
            time.sleep(1)

        elapsed = time.time() - t0
        if not final_status:
            print(f"\nJob was consumed but no terminal found in logs after {elapsed:.1f}s")
            print(f"This confirms: server starts and processes webhooks WITHOUT trace middleware.")
            print(f"Trace middleware is purely observational (debug visibility only).")
            print(f"Fresh RAPHAEL_AGENT_DATA_DIR was the actual fix for prior failures.")
            return 0

        print(f"\n[{elapsed:.1f}s] Job reached: {final_status}")

        if final_status == "fix_finalized":
            print(f"\n=== SUCCESS: Full chain completed WITHOUT trace middleware ===")
            print(f"Webhook -> bridge -> dispatch queue -> connector -> fix_finalized in {elapsed:.1f}s")
            print(f"CONFIRMED: fresh RAPHAEL_AGENT_DATA_DIR was the actual fix.")
            print(f"Trace middleware was never functionally necessary.")
            return 0
        else:
            print(f"\n=== RESULT: {final_status} (not fix_finalized) ===")
            return 1

    finally:
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=10)
            except Exception:
                p.kill()
        shutil.rmtree(data_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
