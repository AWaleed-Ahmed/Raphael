"""Full-chain test: webhook → bridge → dispatch → connector → terminal.

Combines ingest bridge + dispatch orchestrator + Ignis connector in one
process tree. No manual job submission — the webhook event flows all the
way through to a completed job via the connector's polling loop.
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
TENANT = f"fullchain-{uuid.uuid4().hex[:8]}"
CONNECTOR_TOKEN = "full-chain-connector-token"
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


def trace_records(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def find_terminal(records, job_id):
    for rec in reversed(records):
        body = rec.get("response", {}).get("body", "")
        if job_id not in body:
            continue
        try:
            parsed = json.loads(body)
        except Exception:
            continue
        for msg in parsed.get("messages", []):
            if msg.get("kind") == "terminal":
                return msg
    return None


def main():
    if not IGNIS_BIN:
        print("ERROR: set E2E_IGNIS_BIN")
        return 1

    # Safety
    assert not os.environ.get("RAPHAEL_GITHUB_TOKEN"), "RAPHAEL_GITHUB_TOKEN must NOT be set"
    assert not os.environ.get("GITHUB_TOKEN"), "GITHUB_TOKEN must NOT be set"
    print("Safety: no GitHub tokens, publish defaults to dry_run")

    # Load real webhook payload
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

    trace = E2E / "full-chain-trace.jsonl"
    if trace.exists():
        trace.unlink()
    env["E2E_TRACE_FILE"] = str(trace)

    data_dir = Path(tempfile.mkdtemp(prefix="raphael-fullchain-"))
    env["RAPHAEL_DATA_DIR"] = str(data_dir)
    env["RAPHAEL_AGENT_DATA_DIR"] = str(data_dir)

    processes = []
    try:
        # Start dispatch with REAL hooks + trace middleware
        dispatch_log = open(E2E / "fullchain-dispatch.log", "w")
        dispatch = subprocess.Popen(
            [sys.executable, str(ROOT / "run.py")],
            cwd=str(ROOT), env=env, stdout=dispatch_log, stderr=subprocess.STDOUT,
        )
        processes.append(dispatch)
        wait_ready(DISPATCH_URL)
        print(f"Dispatch ready (REAL hooks + bridge), pid={dispatch.pid}")

        # Start Ignis
        ignis_log = open(E2E / "fullchain-ignis.log", "w")
        ignis = subprocess.Popen(
            [IGNIS_BIN], env=env, stdout=ignis_log, stderr=subprocess.STDOUT,
        )
        processes.append(ignis)
        wait_ready(CONTROLLER_URL)
        print(f"Ignis ready, pid={ignis.pid}")

        # POST the real webhook payload — this is the ONLY trigger
        t0 = time.time()
        print(f"\n[{time.time()-t0:.1f}s] POSTing real webhook payload to /v1/webhooks/github...")
        status, resp = http_post(
            f"{DISPATCH_URL}/v1/webhooks/github",
            webhook_payload,
            headers_extra={
                "x-github-event": "workflow_run",
                "x-github-delivery": "full-chain-test-delivery",
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

        # Wait for terminal — connector drives the job from here
        print(f"[{time.time()-t0:.1f}s] Waiting for connector to drive job to terminal...")
        deadline = time.time() + 180
        terminal = None
        while time.time() < deadline:
            records = trace_records(trace)
            terminal = find_terminal(records, dispatch_job_id)
            if terminal:
                break
            time.sleep(1)

        elapsed = time.time() - t0
        if not terminal:
            print(f"\nTIMEOUT after {elapsed:.1f}s — no terminal for {dispatch_job_id}")
            records = trace_records(trace)
            print(f"  Trace has {len(records)} records")
            # Show last few records for debugging
            for rec in records[-5:]:
                req = rec.get("request", {})
                resp_r = rec.get("response", {})
                print(f"  [{req.get('method','?')}] {req.get('path','?')} -> {resp_r.get('status','?')}")
            return 1

        final_status = terminal.get("payload", {}).get("final_status", "")
        print(f"\n[{elapsed:.1f}s] Terminal: final_status={final_status}")

        # Print full trace
        records = trace_records(trace)
        print(f"\n=== Full HTTP trace ({len(records)} records) ===")
        for i, rec in enumerate(records):
            req = rec.get("request", {})
            resp_r = rec.get("response", {})
            req_body = req.get("body", "")
            resp_body = resp_r.get("body", "")
            if dispatch_job_id not in req_body and dispatch_job_id not in resp_body:
                continue
            method = req.get("method", "?")
            path = req.get("path", "?")
            status_code = resp_r.get("status", "?")

            verb = ""
            patch_content = ""
            for text in [req_body, resp_body]:
                if not text:
                    continue
                try:
                    p = json.loads(text)
                    msgs = p.get("messages", [])
                    for m in msgs:
                        pl = m.get("payload", {})
                        if "verb" in pl:
                            verb = pl["verb"]
                        patch = pl.get("args", {}).get("patch", {})
                        if patch.get("files"):
                            for pf in patch["files"]:
                                patch_content = pf.get("content", "")[:150]
                    rp = p.get("payload", p)
                    if isinstance(rp, dict) and rp.get("verb"):
                        verb = rp["verb"]
                except Exception:
                    pass

            line = f"  [{i}] {method} {path} -> {status_code}"
            if verb:
                line += f"  verb={verb}"
            print(line)
            if patch_content:
                print(f"       patch: {patch_content}...")

        # Extract patch content if fix_finalized
        if final_status == "fix_finalized":
            print(f"\n=== SUCCESS: Full chain completed ===")
            print(f"Webhook → bridge → dispatch queue → connector → fix_finalized in {elapsed:.1f}s")
            for rec in records:
                resp_body = rec.get("response", {}).get("body", "")
                if dispatch_job_id in resp_body:
                    try:
                        p = json.loads(resp_body)
                        for m in p.get("messages", []):
                            pl = m.get("payload", {})
                            if pl.get("verb") == "deploy_revision":
                                patch = pl.get("args", {}).get("patch", {})
                                if patch.get("files"):
                                    for pf in patch["files"]:
                                        if pf.get("content", "").strip() and not pf["content"].startswith("#"):
                                            print(f"\nGenerated patch ({pf['path']}):")
                                            print(pf["content"])
                    except Exception:
                        pass
        else:
            print(f"\n=== RESULT: {final_status} ===")

        return 0 if final_status == "fix_finalized" else 1

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
