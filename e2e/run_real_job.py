"""Run one real job through dispatch with REAL agent hooks (no mocks)."""
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
TENANT = "real-test"
PRODUCER_TOKEN = "real-producer-token"
CONNECTOR_TOKEN = "real-connector-token"
IGNIS_BIN = os.getenv("E2E_IGNIS_BIN", "")

CLONE_URL = "https://github.com/AmazingDude/raphael-e2e-fixture.git"
COMMIT_SHA = "268d7b781f3849dab5694a8161789099555ebc76"


def http_post(url, body, token):
    data = json.dumps(body).encode()
    req = Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    try:
        with urlopen(req, timeout=30) as resp:
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

    # Safety check
    assert not os.environ.get("RAPHAEL_GITHUB_TOKEN"), "RAPHAEL_GITHUB_TOKEN must NOT be set"
    assert not os.environ.get("GITHUB_TOKEN"), "GITHUB_TOKEN must NOT be set"
    print("Safety: no GitHub tokens, publish defaults to dry_run")

    env = os.environ.copy()
    env["RAPHAEL_DISPATCH_TOKENS"] = json.dumps({
        PRODUCER_TOKEN: {"tenant_id": TENANT, "role": "producer"},
        CONNECTOR_TOKEN: {"tenant_id": TENANT, "role": "connector"},
    })
    env["RAPHAEL_PARTNER_MODE"] = "dry_run"
    env["RAPHAEL_PUBLISH_MODE"] = "dry_run"
    env["RAPHAEL_LLM_DIAGNOSIS"] = "0"
    env["RAPHAEL_CLUSTER_BACKEND"] = "mock"
    env["RAPHAEL_LISTEN"] = "127.0.0.1:8090"
    env["RAPHAEL_CONNECTOR_DISPATCH_URL"] = DISPATCH
    env["RAPHAEL_CONNECTOR_CONTROLLER_URL"] = "http://127.0.0.1:8090"
    env["RAPHAEL_CONNECTOR_POLL_INTERVAL_MS"] = "200"
    env["RAPHAEL_CONNECTOR_TENANT_ID"] = TENANT
    env["RAPHAEL_CONNECTOR_TOKEN"] = CONNECTOR_TOKEN

    trace = E2E / "real-job-trace.jsonl"
    if trace.exists():
        trace.unlink()
    env["E2E_TRACE_FILE"] = str(trace)

    data_dir = Path(tempfile.mkdtemp(prefix="raphael-real-"))
    env["RAPHAEL_DATA_DIR"] = str(data_dir)

    processes = []
    try:
        # Start dispatch with REAL hooks (production entrypoint, no overrides)
        dispatch_log = open(E2E / "real-dispatch.log", "w")
        dispatch = subprocess.Popen(
            [sys.executable, str(E2E / "real_dispatch_launcher.py")],
            cwd=str(ROOT), env=env, stdout=dispatch_log, stderr=subprocess.STDOUT,
        )
        processes.append(dispatch)
        wait_ready(DISPATCH)
        print(f"Dispatch ready (REAL hooks), pid={dispatch.pid}")

        # Start Ignis
        ignis_log = open(E2E / "real-ignis.log", "w")
        ignis = subprocess.Popen(
            [IGNIS_BIN], env=env, stdout=ignis_log, stderr=subprocess.STDOUT,
        )
        processes.append(ignis)
        wait_ready("http://127.0.0.1:8090")
        print(f"Ignis ready, pid={ignis.pid}")

        # Submit job
        job_id = str(uuid.uuid4())
        job_envelope = {
            "protocol_version": "1.0",
            "message_id": str(uuid.uuid4()),
            "job_id": job_id,
            "kind": "job",
            "sent_at": "2026-08-30T00:00:00Z",
            "payload": {
                "job_id": job_id,
                "repository": {
                    "name": "raphael-e2e-fixture",
                    "clone_url": CLONE_URL,
                },
                "commit_sha": COMMIT_SHA,
                "narrowed_location": {
                    "file_path": "deploy/manifests/service-port-mismatch.yaml",
                },
                "lease_ttl_seconds": 120,
            },
        }

        t0 = time.time()
        status, resp = http_post(f"{DISPATCH}/v1/tenants/{TENANT}/jobs", job_envelope, PRODUCER_TOKEN)
        print(f"[{time.time()-t0:.1f}s] Submitted: status={status}, job_id={job_id}")
        assert status == 202, f"submission failed: {status} {resp}"

        # Wait for terminal
        print("Waiting for terminal envelope...")
        deadline = time.time() + 180
        terminal = None
        while time.time() < deadline:
            records = trace_records(trace)
            terminal = find_terminal(records, job_id)
            if terminal:
                break
            time.sleep(1)

        elapsed = time.time() - t0
        if not terminal:
            print(f"TIMEOUT after {elapsed:.1f}s — no terminal")
            # Dump what we have
            records = trace_records(trace)
            for i, rec in enumerate(records):
                req = rec.get("request", {})
                resp = rec.get("response", {})
                body = req.get("body", "") + resp.get("body", "")
                if job_id in body:
                    print(f"  [{i}] {req.get('method','?')} {req.get('path','?')} -> {resp.get('status','?')}")
            return 1

        final_status = terminal.get("payload", {}).get("final_status", "")
        print(f"[{elapsed:.1f}s] Terminal: final_status={final_status}")

        # Print full trace for this job
        records = trace_records(trace)
        print(f"\n=== Full HTTP trace ({len(records)} records) ===")
        for i, rec in enumerate(records):
            req = rec.get("request", {})
            resp = rec.get("response", {})
            req_body = req.get("body", "")
            resp_body = resp.get("body", "")
            if job_id not in req_body and job_id not in resp_body:
                continue
            method = req.get("method", "?")
            path = req.get("path", "?")
            status_code = resp.get("status", "?")

            # Extract key info
            verb = ""
            sandbox_id = ""
            patch_content = ""
            diagnosis = ""
            publish_info = ""

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
                        args = pl.get("args", {})
                        if "sandbox_id" in args:
                            sandbox_id = args["sandbox_id"]
                        patch = args.get("patch", {})
                        if patch.get("files"):
                            for f in patch["files"]:
                                patch_content = f.get("content", "")[:200]
                    # Check result payloads
                    rp = p.get("payload", p)
                    if isinstance(rp, dict):
                        result = rp.get("result", {})
                        if isinstance(result, dict):
                            if "sandbox_id" in result:
                                sandbox_id = result["sandbox_id"]
                            if "diagnosis" in result:
                                diagnosis = json.dumps(result["diagnosis"])[:300]
                            if "publish" in result:
                                publish_info = json.dumps(result["publish"])[:300]
                except Exception:
                    pass

            line = f"[{i}] {method} {path} -> {status_code}"
            if verb:
                line += f"  verb={verb}"
            if sandbox_id:
                line += f"  sandbox={sandbox_id}"
            print(line)
            if patch_content:
                print(f"     patch: {patch_content}...")
            if diagnosis:
                print(f"     diagnosis: {diagnosis}")
            if publish_info:
                print(f"     publish: {publish_info}")

        # Check dispatch log for agent node output
        dispatch_log.flush()
        dispatch_log.close()
        log_content = Path(E2E / "real-dispatch.log").read_text(errors="replace")
        if log_content.strip():
            print(f"\n=== Dispatch log ({len(log_content)} chars) ===")
            print(log_content[-3000:] if len(log_content) > 3000 else log_content)

        return 0

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
